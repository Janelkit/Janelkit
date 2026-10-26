"""Instancia de un componente: ejecuta su script, evalúa bindings y atiende eventos.

Cada instancia ejecuta el `<script>` en un espacio de nombres propio, de modo
que dos instancias del mismo componente nunca comparten estado local.

Semántica de las expresiones de plantilla: los nombres que apuntan a un
`state` o `computed` se sustituyen por su valor (`{count}` equivale a
`count.value`). Las lecturas se registran como dependencias del binding.
"""
from __future__ import annotations

import ast
import builtins
import inspect
import logging
import textwrap
from pathlib import Path
from types import CodeType
from typing import Any

from ..compiler import CompiledComponent
from ..compiler.ast_nodes import Expression
from ..compiler.ir import Binding, ExprBinding, Guard, TextBinding, VisibilityBinding
from ..diagnostics import Diagnostic
from ..reactivity import Computed, Effect, Scope, State, batch, untracked
from .qt_bridge import make_bridge_class

log = logging.getLogger("fluxui")


class _CompiledExpr:
    __slots__ = ("code", "names", "expression")

    def __init__(self, expression: Expression, file: str):
        text = expression.code.strip()
        # Saltos de línea iniciales: los tracebacks apuntan a la línea real del .flux.
        src = "\n" * (expression.loc.line - 1) + "(" + text + "\n)"
        self.code: CodeType = compile(src, file, "eval")
        tree = ast.parse("(" + text + "\n)", mode="eval")
        self.names = tuple(sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}))
        self.expression = expression


def _runtime_tables(compiled: CompiledComponent) -> dict[str, Any]:
    """Código compilado y clase puente, calculados una vez por componente."""
    cache = compiled.cache
    if "exprs" not in cache:
        file = compiled.file
        exprs: dict[int, _CompiledExpr] = {}

        def add(expr: Expression | None) -> None:
            if expr is not None and id(expr) not in exprs:
                exprs[id(expr)] = _CompiledExpr(expr, file)

        for b in compiled.ir.bindings:
            if isinstance(b, ExprBinding):
                add(b.expression)
            elif isinstance(b, TextBinding):
                for part in b.parts:
                    if isinstance(part, Expression):
                        add(part)
            elif isinstance(b, VisibilityBinding):
                for guard in b.guards:
                    for cond in guard.conditions:
                        add(cond)
                add(b.extra)
        for h in compiled.ir.handlers:
            add(h.expression)

        script_code = None
        script = compiled.ir.script
        if script is not None:
            body = textwrap.dedent(script.content)
            script_code = compile("\n" * (script.loc.line - 1) + body, file, "exec")

        cache["exprs"] = exprs
        cache["script"] = script_code
        cache["bridge_class"] = make_bridge_class(
            [b.id for b in compiled.ir.bindings], f"FluxBridge_{Path(file).stem}"
        )
    return cache


def _unwrap(value: Any) -> Any:
    return value.value if isinstance(value, (State, Computed)) else value


def _display(value: Any) -> str:
    return "" if value is None else str(value)


class ComponentInstance:
    def __init__(self, compiled: CompiledComponent):
        self.compiled = compiled
        self.disposed = False
        tables = _runtime_tables(compiled)
        self._exprs: dict[int, _CompiledExpr] = tables["exprs"]
        self._handlers = {h.id: h for h in compiled.ir.handlers}
        self._writes = {w.binding_id: w for w in compiled.ir.writes}
        self.scope = Scope()
        self.namespace: dict[str, Any] = {
            "__name__": f"fluxui.components.{Path(compiled.file).stem}",
            "__file__": compiled.file,
            "__builtins__": builtins,
        }
        self.bridge = tables["bridge_class"](self._invoke, self._write)
        with self.scope.active():
            if tables["script"] is not None:
                exec(tables["script"], self.namespace)
            for binding in compiled.ir.bindings:
                self._bind(binding)

    # -- bindings ------------------------------------------------------------
    def _bind(self, binding: Binding) -> None:
        def update() -> None:
            self.bridge.set_value(binding.id, self._evaluate(binding))

        def on_error(exc: BaseException) -> None:
            self._report(f"error al evaluar el binding: {type(exc).__name__}: {exc}", binding.loc, exc)
            if self.bridge.value(binding.id) is None and isinstance(binding, TextBinding):
                self.bridge.set_value(binding.id, "")

        Effect(update, on_error=on_error)

    def _evaluate(self, binding: Binding) -> Any:
        if isinstance(binding, ExprBinding):
            return self.eval(binding.expression)
        if isinstance(binding, TextBinding):
            return "".join(p if isinstance(p, str) else _display(self.eval(p)) for p in binding.parts)
        return all(self._guard_active(g) for g in binding.guards) and (
            binding.extra is None or bool(self.eval(binding.extra))
        )

    def _guard_active(self, guard: Guard) -> bool:
        for i, cond in enumerate(guard.conditions):
            if i == guard.index:
                return bool(self.eval(cond))
            if self.eval(cond):
                return False
        return True  # rama {:else}

    def eval(self, expression: Expression) -> Any:
        """Evalúa una expresión de plantilla desenvolviendo state/computed."""
        compiled = self._exprs[id(expression)]
        ns = self.namespace
        local = {name: _unwrap(ns[name]) for name in compiled.names if name in ns}
        return eval(compiled.code, ns, local)

    # -- eventos desde Qt ----------------------------------------------------
    def _invoke(self, handler_id: str, args: list) -> None:
        if self.disposed:
            return
        handler = self._handlers[handler_id]
        try:
            with untracked():
                fn = eval(self._exprs[id(handler.expression)].code, self.namespace)
            if not callable(fn):
                self._report(
                    f"on:{handler.event} debe recibir una función, se obtuvo {type(fn).__name__}",
                    handler.loc,
                )
                return
            with batch():
                fn(*_fit_args(fn, args))
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe cerrar la app
            self._report(f"error en el manejador on:{handler.event}: {type(exc).__name__}: {exc}", handler.loc, exc)

    def _write(self, binding_id: str, value: Any) -> None:
        if self.disposed:
            return
        write = self._writes[binding_id]
        name = write.target.code.strip()
        target = self.namespace.get(name)
        if not isinstance(target, State):
            kind = "no está definido" if target is None else f"es {type(target).__name__}, no un state"
            self._report(f"bind: '{name}' {kind}", write.loc)
            return
        target.value = value

    # -- ciclo de vida -------------------------------------------------------
    def dispose(self) -> None:
        """Libera bindings y efectos: el estado deja de notificar a esta instancia."""
        if not self.disposed:
            self.disposed = True
            self.scope.dispose()

    def _report(self, message: str, loc, exc: BaseException | None = None) -> None:
        diag = Diagnostic(message, loc, source=self.compiled.ir.source)
        log.error(diag.format(), exc_info=exc if exc is not None and log.isEnabledFor(logging.DEBUG) else None)


def _fit_args(fn: Any, args: list) -> list:
    """Pasa al manejador solo los argumentos que acepta (`def guardar():` o `def guardar(texto):`)."""
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return args
    if any(p.kind is p.VAR_POSITIONAL for p in params):
        return args
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return args[: len(positional)]
