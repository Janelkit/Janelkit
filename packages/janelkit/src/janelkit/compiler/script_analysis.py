"""Análisis estático del `<script>` de un componente.

Obtiene, sin ejecutar nada:

- los nombres que define el script (para avisar de nombres mal escritos en la plantilla);
- las props (`titulo = prop("x")`) y eventos (`guardado = event()`) que declara;
- los imports de componentes `.janel` (`from components.TodoItem import TodoItem`).

Devuelve además el árbol del script listo para ejecutarse: los imports de
componentes se eliminan (el runtime inyecta los componentes) y las llamadas
`prop(...)`/`event()` reciben el nombre de la variable.
"""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..diagnostics import Diagnostic, JanelError, SourceLocation
from .ast_nodes import ScriptBlock

PROP_FACTORY = "__jk_prop__"
EVENT_FACTORY = "__jk_event__"

# (módulo, nombre importado, nivel de import relativo) -> ruta del .janel o None
Resolver = Callable[[str | None, str, int], "Path | None"]


@dataclass
class PropDecl:
    name: str
    required: bool
    loc: SourceLocation
    annotation: str | None = None  # `edad: int = prop(0)` -> "int"
    # Tipos admitidos según la anotación, si solo usa tipos básicos ("int", "str", "None"…).
    # None: sin anotación o con tipos que solo se pueden comprobar al ejecutar.
    type_names: frozenset[str] | None = None


_BASIC = {"int", "float", "str", "bool", "list", "dict", "set", "tuple", "None"}


def basic_type_names(node: ast.expr) -> frozenset[str] | None:
    """Nombres de tipos básicos que admite una anotación, o None si no se puede saber sin ejecutar."""
    if isinstance(node, ast.Constant) and node.value is None:
        return frozenset({"None"})
    if isinstance(node, ast.Name):
        if node.id == "Any" or node.id == "object":
            return None
        return frozenset({node.id}) if node.id in _BASIC else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = basic_type_names(node.left), basic_type_names(node.right)
        return left | right if left is not None and right is not None else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        base = node.value.id
        if base == "Optional":
            inner = basic_type_names(node.slice)
            return inner | {"None"} if inner is not None else None
        if base == "Union" and isinstance(node.slice, ast.Tuple):
            parts = [basic_type_names(e) for e in node.slice.elts]
            return frozenset().union(*parts) if all(p is not None for p in parts) else None
        if base in _BASIC:  # list[str] -> list
            return frozenset({base})
    return None


@dataclass
class EventDecl:
    name: str
    loc: SourceLocation


@dataclass
class ComponentImport:
    name: str  # nombre de la etiqueta en la plantilla
    path: Path
    loc: SourceLocation


@dataclass
class ScriptInfo:
    tree: ast.Module | None = None
    # None si no puede saberse (p. ej. `from x import *`)
    defined: frozenset[str] | None = frozenset()
    props: dict[str, PropDecl] = field(default_factory=dict)
    events: dict[str, EventDecl] = field(default_factory=dict)
    components: dict[str, ComponentImport] = field(default_factory=dict)
    # `inherit_attrs = False`: los atributos de la etiqueta no pasan a la raíz (docs/flex.md)
    inherit_attrs: bool = True


def analyze_script(script: ScriptBlock | None, file: str, source: str, resolve: Resolver) -> ScriptInfo:
    if script is None:
        return ScriptInfo()
    return _Analyzer(script, file, source, resolve).run()


class _Analyzer:
    def __init__(self, script: ScriptBlock, file: str, source: str, resolve: Resolver):
        self.script = script
        self.file = file
        self.source = source
        self.resolve = resolve
        self.errors: list[Diagnostic] = []
        self.info = ScriptInfo()
        self.prop_names: set[str] = set()  # alias locales de janelkit.prop
        self.event_names: set[str] = set()
        self.module_aliases: set[str] = set()  # `import janelkit [as f]`
        self.rewritten: set[int] = set()  # id() de las llamadas ya transformadas

    def loc(self, node: ast.AST) -> SourceLocation:
        line = getattr(node, "lineno", self.script.loc.line)
        col = getattr(node, "col_offset", 0) + 1 + self.indent
        return SourceLocation(self.file, line, col)

    def error(self, msg: str, node: ast.AST, hint: str | None = None) -> None:
        self.errors.append(Diagnostic(msg, self.loc(node), hint, source=self.source))

    def run(self) -> ScriptInfo:
        content = self.script.content
        body = textwrap.dedent(content)
        first = next((ln for ln in content.splitlines() if ln.strip()), "")
        self.indent = len(first) - len(first.lstrip()) if body != content else 0
        try:
            tree = ast.parse(body, self.file, "exec")
        except SyntaxError as exc:
            line = self.script.loc.line + (exc.lineno or 1) - 1
            col = (exc.offset or 1) + self.indent
            raise JanelError(
                Diagnostic(f"error de sintaxis en el script: {exc.msg}", SourceLocation(self.file, line, col), source=self.source)
            ) from None
        ast.increment_lineno(tree, self.script.loc.line - 1)

        self.collect_api_aliases(tree)
        for stmt in tree.body:
            if (
                isinstance(stmt, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "inherit_attrs" for t in stmt.targets)
                and isinstance(stmt.value, ast.Constant)
            ):
                self.info.inherit_attrs = bool(stmt.value.value)
        tree.body = [stmt for stmt in (self.top_level(s) for s in tree.body) if stmt is not None]
        self.check_misplaced_factories(tree)
        ast.fix_missing_locations(tree)

        self.info.tree = tree
        self.info.defined = _defined_names(tree, extra=self.info.components)
        if self.errors:
            raise JanelError(self.errors)
        return self.info

    # -- janelkit.prop / janelkit.event ---------------------------------------------
    def collect_api_aliases(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "janelkit" and not node.level:
                for alias in node.names:
                    if alias.name == "prop":
                        self.prop_names.add(alias.asname or "prop")
                    elif alias.name == "event":
                        self.event_names.add(alias.asname or "event")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "janelkit":
                        self.module_aliases.add(alias.asname or "janelkit")

    def factory_kind(self, call: ast.AST) -> str | None:
        if not isinstance(call, ast.Call):
            return None
        func = call.func
        if isinstance(func, ast.Name):
            if func.id in self.prop_names:
                return "prop"
            if func.id in self.event_names:
                return "event"
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in self.module_aliases:
            if func.attr in ("prop", "event"):
                return func.attr
        return None

    # -- sentencias de nivel superior -----------------------------------------
    def top_level(self, stmt: ast.stmt) -> ast.stmt | None:
        if isinstance(stmt, ast.ImportFrom):
            return self.component_import(stmt)
        target = value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        kind = self.factory_kind(value) if value is not None else None
        if kind is None:
            return stmt
        if not isinstance(target, ast.Name):
            self.error(f"{kind}() debe asignarse a un nombre simple", stmt, f"usa nombre = {kind}(...)")
            return stmt
        annotation = stmt.annotation if isinstance(stmt, ast.AnnAssign) else None
        self.declare(kind, target.id, value, stmt, annotation)
        return stmt

    def declare(self, kind: str, name: str, call: ast.Call, stmt: ast.stmt, annotation: ast.expr | None = None) -> None:
        if name in self.info.props or name in self.info.events:
            self.error(f"'{name}' ya está declarado como prop o evento", stmt)
            return
        if kind == "prop":
            if len(call.args) > 1 or any(k.arg != "default" for k in call.keywords):
                self.error("prop() admite un único argumento: el valor por defecto", call, "usa nombre = prop(valor_por_defecto)")
                return
            required = not call.args and not call.keywords
            decl = PropDecl(name, required, self.loc(stmt))
            if annotation is not None:
                decl.annotation = ast.unparse(annotation)
                decl.type_names = basic_type_names(annotation)
                # El tipo llega al runtime, que valida cada valor que recibe la prop.
                kind_value = ast.Constant(decl.annotation) if isinstance(annotation, ast.Constant) else annotation
                call.keywords.append(ast.copy_location(ast.keyword("kind", kind_value), call))
            self.info.props[name] = decl
            call.func = ast.copy_location(ast.Name(PROP_FACTORY, ast.Load()), call.func)
        else:
            if call.args or call.keywords:
                self.error("event() no admite argumentos", call, "usa nombre = event()")
                return
            self.info.events[name] = EventDecl(name, self.loc(stmt))
            call.func = ast.copy_location(ast.Name(EVENT_FACTORY, ast.Load()), call.func)
        call.args.insert(0, ast.copy_location(ast.Constant(name), call))
        self.rewritten.add(id(call))

    def check_misplaced_factories(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            kind = self.factory_kind(node)
            if kind is not None and id(node) not in self.rewritten:
                self.error(
                    f"{kind}() solo puede usarse en el nivel superior del script",
                    node,
                    f"declara nombre = {kind}(...) fuera de funciones y bloques",
                )

    # -- imports de componentes -------------------------------------------------
    def component_import(self, stmt: ast.ImportFrom) -> ast.stmt | None:
        kept: list[ast.alias] = []
        for alias in stmt.names:
            path = None if alias.name == "*" else self.resolve(stmt.module, alias.name, stmt.level)
            if path is None:
                kept.append(alias)
                continue
            name = alias.asname or alias.name
            if not name[:1].isupper():
                self.error(
                    f"el componente '{name}' debe empezar por mayúscula",
                    stmt,
                    "en la plantilla los componentes se usan como etiquetas: <MiComponente />",
                )
                continue
            if name in self.info.components:
                self.error(f"el componente '{name}' se importa dos veces", stmt)
                continue
            self.info.components[name] = ComponentImport(name, path, self.loc(stmt))
        if len(kept) == len(stmt.names):
            return stmt
        if not kept:
            return None
        stmt.names = kept
        return stmt


def _defined_names(tree: ast.Module, extra: dict) -> frozenset[str] | None:
    """Nombres globales que define el script, o None si no se puede determinar."""
    names: set[str] = set(extra)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            return None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("globals", "exec"):
            return None
        if isinstance(node, ast.Global):
            names.update(node.names)

    def visit(stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(stmt.name)
                continue
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for alias in stmt.names:
                    names.add(alias.asname or alias.name.split(".")[0])
                continue
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    names.add(node.id)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
            for child in ("body", "orelse", "finalbody", "handlers"):
                inner = getattr(stmt, child, None)
                if isinstance(inner, list):
                    visit([s for s in inner if isinstance(s, ast.stmt)])
                    for h in inner:
                        if isinstance(h, ast.ExceptHandler):
                            if h.name:
                                names.add(h.name)
                            visit(h.body)

    visit(tree.body)
    return frozenset(names)
