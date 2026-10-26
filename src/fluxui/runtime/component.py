"""Instancias de componentes y fragmentos: ejecutan el script, evalúan bindings y gestionan regiones dinámicas.

- `ComponentInstance` ejecuta el `<script>` en un espacio de nombres propio,
  de modo que dos instancias del mismo componente nunca comparten estado local.
- `TemplateInstance` da vida a una plantilla: el componente completo o una
  fila de `{#each}` / rama de `{#if}`. Tiene su propio puente `fx` y su propio
  ámbito reactivo, que se libera al desmontarla.
- Los nombres de las expresiones se resuelven en cadena: variables de la fila
  (`item`, `i`), luego las de los fragmentos que la contienen, luego el script
  y por último los builtins. `state`, `computed` y props se desenvuelven.
"""
from __future__ import annotations

import builtins
import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from types import CodeType
from typing import Any, Protocol

from PySide6.QtCore import QObject

from ..compiler import CompiledComponent
from ..compiler.ast_nodes import Expression
from ..compiler.expressions import GETTER, compile_expression
from ..compiler.ir import (
    Binding,
    ComponentSlot,
    ComponentUse,
    ConstArg,
    EachSlot,
    ExprBinding,
    Fragment,
    Handler,
    IfSlot,
    IRTemplate,
    KeySlot,
    TextBinding,
)
from ..compiler.script_analysis import EVENT_FACTORY, PROP_FACTORY
from ..diagnostics import Diagnostic, SourceLocation
from ..reactivity import Computed, Effect, Event, Prop, PropError, Scope, State, batch, untracked
from ..reactivity.props import REQUIRED
from ..reactivity.state import _same
from .list_model import SlotModel
from .qt_bridge import make_bridge_class

log = logging.getLogger("fluxui")


class Host(Protocol):
    """Lo que el runtime necesita del motor Qt: el componente QML de un hijo."""

    def delegate_for(self, compiled: CompiledComponent) -> QObject: ...


@dataclass(frozen=True)
class ComponentRef:
    """Valor que recibe el script al importar un componente .flux."""

    name: str
    path: str

    def __repr__(self) -> str:
        return f"<componente {self.name} ({Path(self.path).name})>"


# -- tablas compiladas una vez por componente -----------------------------------
def _code(compiled: CompiledComponent, expr: Expression) -> CodeType:
    table = compiled.cache.setdefault("code", {})
    code = table.get(id(expr))
    if code is None:
        code = table[id(expr)] = compile_expression(expr, compiled.file)
    return code


def _bridge_class(compiled: CompiledComponent, template: IRTemplate) -> type[QObject]:
    table = compiled.cache.setdefault("bridges", {})
    cls = table.get(template.id)
    if cls is None:
        cls = table[template.id] = make_bridge_class(
            [b.id for b in template.bindings],
            template.model_ids,
            f"FluxBridge_{Path(compiled.file).stem}_{template.id}",
        )
    return cls


def _script_code(compiled: CompiledComponent) -> CodeType | None:
    if "script" not in compiled.cache:
        info = compiled.ir.script_info
        tree = info.tree if info is not None else None
        compiled.cache["script"] = compile(tree, compiled.file, "exec") if tree is not None else None
    return compiled.cache["script"]


def _unwrap(value: Any) -> Any:
    return value.value if isinstance(value, (State, Computed, Prop)) else value


def _display(value: Any) -> str:
    return "" if value is None else str(value)


# -- plantillas ------------------------------------------------------------------
class TemplateInstance:
    def __init__(
        self,
        component: "ComponentInstance",
        template: IRTemplate,
        names: dict[str, Any],
        parent: "TemplateInstance | None",
        bridge_parent: QObject | None = None,
        scope: Scope | None = None,
        with_bridge: bool = True,
    ):
        self.component = component
        self.template = template
        self.names = names
        self.parent = parent
        self.scope = scope or Scope()
        self._globals = {GETTER: self._get, "__builtins__": builtins}
        self._handlers = {h.id: h for h in template.handlers}
        self._writes = {w.binding_id: w for w in template.writes}
        self.bridge = (
            _bridge_class(component.compiled, template)(self._invoke, self._write, bridge_parent) if with_bridge else None
        )
        self.regions: list[_Region] = []

    def start(self) -> None:
        with self.scope.active():
            for binding in self.template.bindings:
                self._bind(binding)
            for slot in self.template.slots:
                if isinstance(slot, EachSlot):
                    self.regions.append(_EachRegion(self, slot))
                elif isinstance(slot, IfSlot):
                    self.regions.append(_IfRegion(self, slot))
                elif isinstance(slot, KeySlot):
                    self.regions.append(_KeyRegion(self, slot))
                else:
                    self.regions.append(_ComponentRegion(self, slot))

    @property
    def disposed(self) -> bool:
        return self.scope.disposed

    def dispose(self) -> None:
        self.scope.dispose()

    # -- nombres y expresiones ------------------------------------------------
    def resolve(self, name: str) -> Any:
        """Valor sin desenvolver de `name` en la cadena de ámbitos."""
        inst: TemplateInstance | None = self
        while inst is not None:
            if name in inst.names:
                return inst.names[name]
            inst = inst.parent
        try:
            return getattr(builtins, name)
        except AttributeError:
            raise NameError(f"name {name!r} is not defined") from None

    def _get(self, name: str) -> Any:
        return _unwrap(self.resolve(name))

    def eval(self, expression: Expression, extra: dict[str, Any] | None = None) -> Any:
        """Evalúa una expresión de plantilla; `extra` añade nombres temporales (p. ej. la clave de una fila)."""
        code = _code(self.component.compiled, expression)
        if not extra:
            return eval(code, self._globals)

        def get(name: str) -> Any:
            return _unwrap(extra[name]) if name in extra else self._get(name)

        return eval(code, {GETTER: get, "__builtins__": builtins})

    # -- bindings ------------------------------------------------------------
    def _bind(self, binding: Binding) -> None:
        bridge = self.bridge

        def update() -> None:
            bridge.set_value(binding.id, self._evaluate(binding))

        def on_error(exc: BaseException) -> None:
            self.report(f"error al evaluar el binding: {type(exc).__name__}: {exc}", binding.loc, exc)
            if bridge.value(binding.id) is None and isinstance(binding, TextBinding):
                bridge.set_value(binding.id, "")

        Effect(update, on_error=on_error)

    def _evaluate(self, binding: Binding) -> Any:
        if isinstance(binding, ExprBinding):
            return self.eval(binding.expression)
        return "".join(p if isinstance(p, str) else _display(self.eval(p)) for p in binding.parts)

    # -- eventos desde Qt ----------------------------------------------------
    def _invoke(self, handler_id: str, args: list) -> None:
        self.call_handler(self._handlers[handler_id], args)

    def call_handler(self, handler: Handler, args: list, kwargs: dict[str, Any] | None = None) -> None:
        if self.disposed:
            return
        try:
            with untracked():
                fn = self.eval(handler.expression)
            if not callable(fn):
                self.report(f"on:{handler.event} debe recibir una función, se obtuvo {type(fn).__name__}", handler.loc)
                return
            with batch():
                fn(*_fit_args(fn, args), **(kwargs or {}))
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe cerrar la app
            hint = None
            if isinstance(exc, AttributeError) and any(f"'{m}'" in str(exc) for m in ("set", "value", "update")):
                hint = "en la plantilla los state ya están desenvueltos; cambia el estado desde una función del script"
            self.report(f"error en el manejador on:{handler.event}: {type(exc).__name__}: {exc}", handler.loc, exc, hint)

    def _write(self, binding_id: str, value: Any) -> None:
        if self.disposed:
            return
        write = self._writes[binding_id]
        name = write.target.code.strip()
        try:
            target = self.resolve(name)
        except NameError:
            target = None
        if isinstance(target, State):
            target.value = value
        elif isinstance(target, Prop):
            self.report(f"bind: la prop '{name}' es de solo lectura", write.loc)
        else:
            kind = "no está definido" if target is None else f"es {type(target).__name__}, no un state"
            self.report(f"bind: '{name}' {kind}", write.loc)

    # -- componentes hijos ---------------------------------------------------
    def delegate_for(self, fragment: Fragment | None) -> QObject | None:
        if fragment is None or fragment.component is None:
            return None
        return self.component.require_host().delegate_for(self.component.compiled.component(fragment.component.path))

    def create_child(self, use: ComponentUse, bridge_parent: QObject | None) -> "ComponentInstance":
        compiled = self.component.compiled.component(use.path)
        incoming: dict[str, State] = {}
        with self.scope.active():
            for name, arg in use.props.items():
                if isinstance(arg, ConstArg):
                    incoming[name] = State(arg.value)
                    continue
                source: State = State(None)

                def push(arg: Expression = arg, source: State = source) -> None:
                    source.value = self.eval(arg)

                def on_error(exc: BaseException, name: str = name, arg: Expression = arg) -> None:
                    self.report(f"error al evaluar la prop '{name}' de <{use.tag}>: {type(exc).__name__}: {exc}", arg.loc, exc)

                Effect(push, on_error=on_error)
                incoming[name] = source
            events = {
                name: (lambda *args, _h=handler, **kwargs: self.call_handler(_h, list(args), kwargs))
                for name, handler in use.events.items()
            }
            child = ComponentInstance(compiled, self.component.host, incoming, events, bridge_parent)
        self.scope.add(child.scope)
        return child

    def report(self, message: str, loc: SourceLocation | None, exc: BaseException | None = None, hint: str | None = None) -> None:
        self.component.report(message, loc, exc, hint)


# -- regiones dinámicas ----------------------------------------------------------
@dataclass
class _Row:
    key: Any
    item: State | None
    index: State | None
    instance: TemplateInstance
    bridge: QObject


class _Region:
    """Base de las regiones: monta y desmonta fragmentos en un modelo."""

    def __init__(self, owner: TemplateInstance):
        self.owner = owner

    def new_model(self, model_id: str, fragment: Fragment | None) -> SlotModel:
        model = SlotModel(self.owner.delegate_for(fragment), parent=self.owner.bridge)
        self.owner.bridge.set_model(model_id, model)
        return model

    def mount(self, fragment: Fragment, model: SlotModel, position: int, names: dict[str, Any], key: Any = None) -> _Row | None:
        owner = self.owner
        inst = TemplateInstance(
            owner.component,
            fragment.template,
            names,
            parent=owner,
            bridge_parent=model,
            with_bridge=fragment.root is not None,
        )
        owner.scope.add(inst.scope)
        try:
            inst.start()
            if fragment.component is not None:
                bridge = inst.create_child(fragment.component, bridge_parent=model).bridge
            else:
                bridge = inst.bridge
        except Exception as exc:  # noqa: BLE001 - p. ej. un error en el script de un hijo
            inst.dispose()
            owner.scope.discard(inst.scope)
            loc = fragment.component.loc if fragment.component else (fragment.root.loc if fragment.root else None)
            owner.report(f"no se pudo crear el contenido: {type(exc).__name__}: {exc}", loc, exc)
            return None
        model.insert(position, bridge)
        return _Row(key, None, None, inst, bridge)

    def unmount(self, model: SlotModel, position: int, row: _Row) -> None:
        # Primero la vista (QML deja de leer el puente), después efectos y puente.
        model.remove(position)
        row.instance.dispose()
        self.owner.scope.discard(row.instance.scope)
        row.bridge.deleteLater()


class _EachRegion(_Region):
    def __init__(self, owner: TemplateInstance, slot: EachSlot):
        super().__init__(owner)
        self.slot = slot
        self.rows: list[_Row] = []
        self.model = self.new_model(slot.model_id, slot.fragment)
        self.empty_model = self.new_model(slot.empty_model_id, slot.empty_fragment) if slot.empty_model_id else None
        self.empty_row: _Row | None = None
        self._reported_keys = False

        def on_error(exc: BaseException) -> None:
            owner.report(f"error en {{#each}}: {type(exc).__name__}: {exc}", slot.iterable.loc, exc)

        Effect(self.update, on_error=on_error)

    def update(self) -> None:
        value = self.owner.eval(self.slot.iterable)
        items = [] if value is None else list(value)
        with untracked():
            if not self.slot.fragment.empty:
                self.reconcile(items)
            self.update_empty(not items)

    def keys_for(self, items: list) -> list:
        slot = self.slot
        if slot.key is None:
            return list(range(len(items)))
        keys: list = []
        seen: set = set()
        problem: str | None = None
        for i, value in enumerate(items):
            extra = {slot.item: value}
            if slot.index:
                extra[slot.index] = i
            key = self.owner.eval(slot.key, extra)
            try:
                hash(key)
            except TypeError:
                problem = problem or f"la clave de {{#each}} debe ser hashable (número, texto o tupla), se obtuvo {type(key).__name__}"
                key = ("__fx_index__", i)
            if key in seen:
                problem = problem or f"clave repetida en {{#each}}: {key!r}; cada elemento necesita una clave única"
                key = ("__fx_dup__", key, i)
            seen.add(key)
            keys.append(key)
        if problem and not self._reported_keys:
            self._reported_keys = True
            self.owner.report(problem, slot.key.loc)
        return keys

    def reconcile(self, items: list) -> None:
        keys = self.keys_for(items)
        wanted = set(keys)
        for pos in range(len(self.rows) - 1, -1, -1):
            if self.rows[pos].key not in wanted:
                self.unmount(self.model, pos, self.rows.pop(pos))

        pos = 0
        for index, (key, value) in enumerate(zip(keys, items)):
            if pos < len(self.rows) and self.rows[pos].key == key:
                row = self.rows[pos]
            else:
                found = next((p for p in range(pos + 1, len(self.rows)) if self.rows[p].key == key), None)
                if found is None:
                    row = self.create(key, value, index, pos)
                    if row is not None:
                        self.rows.insert(pos, row)
                        pos += 1
                    continue
                self.model.move(found, pos)
                self.rows.insert(pos, self.rows.pop(found))
                row = self.rows[pos]
            row.item.value = value
            if row.index is not None:
                row.index.value = index
            pos += 1

    def create(self, key: Any, value: Any, index: int, pos: int) -> _Row | None:
        slot = self.slot
        item = State(value)
        names: dict[str, Any] = {slot.item: item}
        index_state = None
        if slot.index:
            index_state = names[slot.index] = State(index)
        row = self.mount(slot.fragment, self.model, pos, names, key)
        if row is not None:
            row.item, row.index = item, index_state
        return row

    def update_empty(self, is_empty: bool) -> None:
        if self.empty_model is None:
            return
        if is_empty and self.empty_row is None:
            self.empty_row = self.mount(self.slot.empty_fragment, self.empty_model, 0, {})
        elif not is_empty and self.empty_row is not None:
            self.unmount(self.empty_model, 0, self.empty_row)
            self.empty_row = None


class _IfRegion(_Region):
    def __init__(self, owner: TemplateInstance, slot: IfSlot):
        super().__init__(owner)
        self.slot = slot
        self.models = [self.new_model(b.model_id, b.fragment) if b.model_id else None for b in slot.branches]
        self.active: int | None = None
        self.row: _Row | None = None

        def on_error(exc: BaseException) -> None:
            owner.report(f"error al evaluar la condición de {{#if}}: {type(exc).__name__}: {exc}", slot.loc, exc)

        Effect(self.update, on_error=on_error)

    def update(self) -> None:
        index = None
        for i, branch in enumerate(self.slot.branches):
            if branch.condition is None or self.owner.eval(branch.condition):
                index = i
                break
        if index == self.active:
            return
        with untracked():
            if self.row is not None:
                self.unmount(self.models[self.active], 0, self.row)
                self.row = None
            self.active = index
            if index is not None and self.models[index] is not None:
                self.row = self.mount(self.slot.branches[index].fragment, self.models[index], 0, {})


class _KeyRegion(_Region):
    _UNSET = object()

    def __init__(self, owner: TemplateInstance, slot: KeySlot):
        super().__init__(owner)
        self.slot = slot
        self.model = self.new_model(slot.model_id, slot.fragment)
        self.value: Any = self._UNSET
        self.row: _Row | None = None

        def on_error(exc: BaseException) -> None:
            owner.report(f"error al evaluar {{#key}}: {type(exc).__name__}: {exc}", slot.expression.loc, exc)

        Effect(self.update, on_error=on_error)

    def update(self) -> None:
        value = self.owner.eval(self.slot.expression)
        if self.value is not self._UNSET and _same(value, self.value):
            return
        self.value = value
        with untracked():
            if self.row is not None:
                self.unmount(self.model, 0, self.row)
            self.row = self.mount(self.slot.fragment, self.model, 0, {})


class _ComponentRegion(_Region):
    def __init__(self, owner: TemplateInstance, slot: ComponentSlot):
        super().__init__(owner)
        compiled = owner.component.compiled.component(slot.use.path)
        self.model = SlotModel(owner.component.require_host().delegate_for(compiled), parent=owner.bridge)
        owner.bridge.set_model(slot.model_id, self.model)
        self.child = owner.create_child(slot.use, bridge_parent=self.model)
        self.model.insert(0, self.child.bridge)


# -- componentes -----------------------------------------------------------------
class ComponentInstance:
    def __init__(
        self,
        compiled: CompiledComponent,
        host: Host | None = None,
        props: dict[str, State] | None = None,
        events: dict[str, Any] | None = None,
        bridge_parent: QObject | None = None,
    ):
        self.compiled = compiled
        self.host = host
        self.scope = Scope()
        self._incoming = props or {}
        self._event_handlers = events or {}
        self.props: dict[str, Prop] = {}
        self.events: dict[str, Event] = {}
        self.namespace: dict[str, Any] = {
            "__name__": f"fluxui.components.{Path(compiled.file).stem}",
            "__file__": compiled.file,
            "__builtins__": builtins,
            PROP_FACTORY: self._make_prop,
            EVENT_FACTORY: self._make_event,
        }
        info = compiled.ir.script_info
        if info is not None:
            for name, imp in info.components.items():
                self.namespace[name] = ComponentRef(name, str(imp.path))
        code = _script_code(compiled)
        with self.scope.active():
            if code is not None:
                exec(code, self.namespace)
            self.root = TemplateInstance(self, compiled.ir.template, self.namespace, None, bridge_parent, scope=self.scope)
            self.root.start()

    @property
    def bridge(self) -> QObject:
        return self.root.bridge

    @property
    def disposed(self) -> bool:
        return self.scope.disposed

    def eval(self, expression: Expression) -> Any:
        return self.root.eval(expression)

    def dispose(self) -> None:
        """Libera bindings, efectos, filas e hijos: el estado deja de notificar a esta instancia."""
        self.scope.dispose()

    def require_host(self) -> Host:
        if self.host is None:
            raise RuntimeError("los componentes hijos necesitan un motor Qt (Application) para crearse")
        return self.host

    def _make_prop(self, name: str, default: Any = REQUIRED) -> Prop:
        if name in self._incoming:
            source = self._incoming[name]
        elif default is REQUIRED:
            raise PropError(f"la prop '{name}' es obligatoria y nadie la ha pasado (¿es el componente raíz?)")
        else:
            source = State(default)
        prop = self.props[name] = Prop(name, source)
        return prop

    def _make_event(self, name: str) -> Event:
        event = self.events[name] = Event(name, self._event_handlers.get(name))
        return event

    def report(self, message: str, loc: SourceLocation | None, exc: BaseException | None = None, hint: str | None = None) -> None:
        source = self.compiled.ir.source if loc is None or loc.file == self.compiled.file else None
        if source is None and loc is not None:
            other = next((c for c in self.compiled.registry.values() if c.file == loc.file), None)
            source = other.ir.source if other else None
        diag = Diagnostic(message, loc, hint, source=source)
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
