"""AST -> IR. Valida elementos, atributos, directivas, nombres y estilos antes de generar QML.

Los errores se acumulan para informar de varios problemas en una sola
compilación.
"""
from __future__ import annotations

import ast
import builtins
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Union

from ..diagnostics import Diagnostic, FluxError, SourceLocation
from ..qt_backend.controls import CONTROLS, QML_IMPORTS, ControlSpec, PropSpec, all_props, prop_spec, tag_of
from ..styling.compiler import compile_declarations, matching_declarations
from ..styling.parser import Rule, parse_stylesheet
from .ast_nodes import SFC, Attribute, EachBlock, Element, Expression, IfBlock, Interpolation, KeyBlock, Node, Text
from .expressions import free_names
from .ir import (
    Bound,
    ComponentSlot,
    ComponentUse,
    ConstArg,
    EachSlot,
    ExprBinding,
    Fragment,
    Handler,
    IfBranchSlot,
    IfSlot,
    IRComponent,
    IRElement,
    IRNode,
    IRRepeater,
    IRTemplate,
    KeySlot,
    Literal,
    PropArg,
    PropValue,
    TextBinding,
    TokenUse,
    Write,
    qml_string,
)
from .script_analysis import EventDecl, PropDecl, ScriptInfo

_NOT_LITERAL = object()
_BUILTINS = frozenset(dir(builtins))

# Un contenedor implícito (varios nodos en una rama o fila) se comporta como si
# sus hijos estuvieran directamente en el contenedor padre: hereda separación y
# alineación, y crece si alguno de sus hijos tiene flex.
_TRANSPARENT_BOX = {
    "gap": "parent && parent.spacing !== undefined ? parent.spacing : 0",
    "align": "parent && parent.fxAlign ? parent.fxAlign : 0",
    "stretch": "!!parent && parent.fxStretch === true",
    "fxFlex": "fillMain ? 1 : 0",
}


@dataclass
class ComponentInterface:
    """Lo que un componente padre necesita saber de un hijo para validar su uso."""

    props: dict[str, PropDecl] = field(default_factory=dict)
    events: dict[str, EventDecl] = field(default_factory=dict)


InterfaceLookup = Callable[[Path], ComponentInterface]


def lower(
    sfc: SFC,
    info: ScriptInfo | None = None,
    *,
    as_window: bool = True,
    interface: InterfaceLookup | None = None,
) -> IRComponent:
    return _Lowerer(sfc, info or ScriptInfo(), as_window, interface).run()


def _literal(code: str) -> Any:
    """Valor de una expresión literal simple (`640`, `"x"`, `True`) o `_NOT_LITERAL`."""
    try:
        value = ast.literal_eval(code.strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return _NOT_LITERAL
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return _NOT_LITERAL


class _Lowerer:
    def __init__(self, sfc: SFC, info: ScriptInfo, as_window: bool, interface: InterfaceLookup | None):
        self.sfc = sfc
        self.info = info
        self.as_window = as_window
        self.interface = interface
        self.errors: list[Diagnostic] = []
        self.warnings: list[Diagnostic] = []
        self.tokens: list[TokenUse] = []
        self.rules: list[Rule] = []
        self.counters: dict[str, int] = {}
        self.tpl = IRTemplate(self.next_id("t"))
        self.scopes: list[set[str]] = []  # variables de {#each} visibles
        self.component_paths: list[str] = []
        self._reported: set[tuple] = set()

    # -- utilidades ----------------------------------------------------------
    def error(self, msg: str, loc: SourceLocation, hint: str | None = None) -> None:
        key = (msg, loc)
        if key not in self._reported:
            self._reported.add(key)
            self.errors.append(Diagnostic(msg, loc, hint, source=self.sfc.source))

    def next_id(self, prefix: str) -> str:
        n = self.counters.get(prefix, 0)
        self.counters[prefix] = n + 1
        return f"{prefix}{n}"

    def add_expr_binding(self, expr: Expression, loc: SourceLocation) -> str:
        self.check_expr(expr)
        bid = self.next_id("b")
        self.tpl.bindings.append(ExprBinding(bid, expr, loc))
        return bid

    def is_component(self, tag: str) -> bool:
        return tag in self.info.components

    # -- nombres -------------------------------------------------------------
    def local_names(self) -> set[str]:
        return set().union(*self.scopes) if self.scopes else set()

    def check_expr(self, expr: Expression) -> None:
        """Avisa de nombres que no define el script ni un {#each} que los contenga."""
        if self.info.defined is None:
            return
        try:
            names = free_names(expr.code)
        except SyntaxError:  # ya validada por el parser; por si acaso
            return
        known = self.info.defined | self.local_names()
        for name in names:
            if name in known or name in _BUILTINS:
                continue
            close = difflib.get_close_matches(name, sorted(known), n=1)
            hint = f"¿quisiste decir '{close[0]}'?" if close else f"declara '{name}' en el <script> del componente"
            self.error(f"'{name}' no está definido", _name_location(expr, name), hint)

    # -- entrada -------------------------------------------------------------
    def run(self) -> IRComponent:
        sfc = self.sfc
        if sfc.style:
            self.rules = parse_stylesheet(sfc.style.content, sfc.style.loc, sfc.source)

        root_tpl = self.tpl
        roots = sfc.root_elements
        root_ir: IRElement | None = None
        if not roots:
            self.error("la plantilla está vacía", SourceLocation(sfc.file, 1, 1), "añade un elemento raíz, por ejemplo <Window>")
        else:
            for extra in roots[1:]:
                self.error(
                    "solo se admite un elemento raíz en la plantilla",
                    extra.loc,
                    "agrupa los elementos dentro de un <Window> o <Column>",
                )
            first = roots[0]
            if not isinstance(first, Element):
                self.error("la raíz de la plantilla debe ser un elemento", first.loc, "envuélvela en <Column>")
            elif first.tag == "Window":
                if not self.as_window:
                    self.error(
                        "un componente usado dentro de otro no puede tener <Window> como raíz",
                        first.loc,
                        "usa <Column> u otro contenedor como raíz del componente",
                    )
                root_ir = self.window(first)
            else:
                content = self.as_item(self.children([first], horizontal=False), first.loc)
                if content is not None and self.as_window:
                    root_ir = IRElement("FxWindow", first.loc)
                    content.props["anchors.fill"] = Literal("parent")
                    root_ir.children.append(content)
                else:
                    root_ir = content
        if self.errors:
            raise FluxError(self.errors)
        assert root_ir is not None

        return IRComponent(
            file=sfc.file,
            source=sfc.source,
            root=root_ir,
            template=root_tpl,
            script=sfc.script,
            script_info=self.info,
            is_window=self.as_window,
            imports=QML_IMPORTS,
            warnings=self.warnings,
            tokens=self.tokens,
            component_paths=self.component_paths,
        )

    def window(self, el: Element) -> IRElement:
        ir = self.element(el, allow_window=True)
        assert ir is not None
        return ir

    def as_item(self, nodes: list[IRNode], loc: SourceLocation, horizontal: bool = False) -> IRElement | None:
        """Un único elemento QML: el nodo tal cual o un contenedor implícito."""
        if not nodes:
            return None
        if len(nodes) == 1 and isinstance(nodes[0], IRElement):
            return nodes[0]
        box = IRElement("FxRow" if horizontal else "FxColumn", loc)
        box.children = nodes
        return box

    # -- elementos -----------------------------------------------------------
    def element(self, el: Element, allow_window: bool = False) -> IRElement | None:
        spec = CONTROLS.get(el.tag)
        if spec is None:
            self.unknown_element(el)
            return None
        if el.tag == "Window" and not allow_window:
            self.error("<Window> solo puede usarse como raíz de la plantilla", el.loc, "usa <Column> o <Row>")
            return None
        ir = IRElement(spec.qml_type, el.loc)
        conditional: list[Attribute] = []

        decls = matching_declarations(self.rules, el.tag, self.classes(el))
        for qml_prop, value in compile_declarations(decls, el.tag, self.sfc.source, self.warnings, self.tokens).items():
            ir.props[qml_prop] = Literal(value)

        for attr in el.attributes:
            if attr.name == "class":
                continue
            if attr.name == "id":
                if isinstance(attr.value, str) and attr.value:
                    ir.props["objectName"] = Literal(qml_string(attr.value))
                else:
                    self.error('el atributo id debe ser un texto literal, p. ej. id="guardar"', attr.loc)
            elif attr.directive == "on":
                self.event(attr, spec, ir)
            elif attr.directive == "bind":
                self.two_way(attr, el, spec, ir)
            elif attr.directive == "class":
                conditional.append(attr)
            elif attr.directive is not None:
                self.error(
                    f"directiva desconocida '{attr.directive}:'", attr.loc, "las directivas disponibles son on:, bind: y class:"
                )
            else:
                self.prop(attr, el, spec, ir)

        # Un tamaño fijo desactiva el estiramiento por defecto (texto y campos en columnas).
        for axis in ("Width", "Height"):
            if f"Layout.preferred{axis}" in ir.props:
                ir.props.setdefault(f"Layout.fill{axis}", Literal("false"))

        self.conditional_classes(el, conditional, ir)
        self.content(el, spec, ir)
        return ir

    def conditional_classes(self, el: Element, attrs: list[Attribute], ir: IRElement) -> None:
        """`class:activa={cond}`: los estilos de `.activa` se aplican mientras `cond` sea verdadera."""
        layers: list[tuple[str, dict[str, str]]] = []
        for attr in attrs:
            name = attr.argument
            expr = attr.value
            if expr is True:  # class:activa  ==  class:activa={activa}
                expr = Expression(name, attr.loc)
            if not isinstance(expr, Expression):
                self.error(f"class:{name} espera una condición entre llaves", attr.loc, f"usa class:{name}={{condicion}}")
                continue
            decls = [d for r in self.rules if f".{name}" in r.selectors for d in r.declarations]
            if not decls:
                self.warnings.append(
                    Diagnostic(f"la clase '{name}' no tiene reglas en <style>", attr.loc, severity="warning", source=self.sfc.source)
                )
                continue
            props = compile_declarations(decls, el.tag, self.sfc.source, self.warnings, self.tokens)
            when = f"!!fx.{self.add_expr_binding(expr, attr.loc)}"
            layers.append((when, props))
        # Si varias clases activas fijan la misma propiedad, gana la última.
        for i, (when, props) in enumerate(layers):
            for prop, value in props.items():
                later = [w for w, p in layers[i + 1:] if prop in p]
                cond = " && ".join([when, *(f"!{w}" for w in later)])
                ir.conditional.append((prop, value, cond))

    def unknown_element(self, el: Element) -> None:
        options = sorted({*CONTROLS, *self.info.components})
        close = difflib.get_close_matches(el.tag, options, n=1)
        if close:
            hint = f"¿quisiste decir <{close[0]}>?"
        elif el.tag[:1].isupper():
            hint = f"si es un componente, impórtalo en el script: from components.{el.tag} import {el.tag}"
        else:
            hint = "elementos disponibles: " + ", ".join(sorted(CONTROLS))
        self.error(f"elemento desconocido <{el.tag}>", el.loc, hint)

    def classes(self, el: Element) -> list[str]:
        attr = el.attribute("class")
        if attr is None:
            return []
        if not isinstance(attr.value, str):
            self.error("class dinámico aún no está soportado", attr.loc, 'usa un texto literal: class="a b"')
            return []
        return attr.value.split()

    def prop(self, attr: Attribute, el: Element, spec: ControlSpec, ir: IRElement) -> None:
        pspec = prop_spec(spec, attr.name)
        if pspec is None:
            close = difflib.get_close_matches(attr.name, all_props(spec), n=1)
            self.error(
                f"propiedad desconocida '{attr.name}' en <{el.tag}>",
                attr.loc,
                (f"¿quisiste decir '{close[0]}'? " if close else "") + "propiedades disponibles: " + ", ".join(all_props(spec)),
            )
            return
        value = self.prop_value(attr, pspec)
        if value is not None:
            ir.props[pspec.qml] = value

    def prop_value(self, attr: Attribute, pspec: PropSpec) -> PropValue | None:
        if attr.value is True:
            if pspec.type == "bool":
                return Literal("true")
            self.error(f"'{attr.name}' necesita un valor", attr.loc)
            return None
        if isinstance(attr.value, str):
            return self.literal_from_text(attr, attr.value, pspec)
        lit = _literal(attr.value.code)
        if lit is _NOT_LITERAL:
            return Bound(self.add_expr_binding(attr.value, attr.loc))
        return self.literal_from_python(attr, lit, pspec)

    def literal_from_text(self, attr: Attribute, text: str, pspec: PropSpec) -> Literal | None:
        if pspec.type == "number":
            if re.fullmatch(r"-?\d+(\.\d+)?", text.strip()):
                return Literal(text.strip())
            self.error(f"'{attr.name}' espera un número", attr.loc, f"usa {attr.name}={{{text or 0}}}")
            return None
        if pspec.type == "bool":
            if text in ("true", "false"):
                return Literal(text)
            self.error(f"'{attr.name}' espera true o false", attr.loc)
            return None
        return Literal(qml_string(text))

    def literal_from_python(self, attr: Attribute, value: Any, pspec: PropSpec) -> Literal | None:
        if pspec.type == "bool":
            if isinstance(value, bool):
                return Literal("true" if value else "false")
            self.error(f"'{attr.name}' espera True o False", attr.loc)
            return None
        if pspec.type == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return Literal(repr(value))
            self.error(f"'{attr.name}' espera un número", attr.loc)
            return None
        if value is None:
            return Literal("undefined")
        if isinstance(value, bool):
            return Literal("true" if value else "false")
        if isinstance(value, (int, float)):
            return Literal(qml_string(str(value)) if pspec.type == "string" else repr(value))
        return Literal(qml_string(value))

    def event(self, attr: Attribute, spec: ControlSpec, ir: IRElement) -> None:
        name = attr.argument
        ev = spec.events.get(name)
        if ev is None:
            available = ", ".join(f"on:{e}" for e in spec.events) or "ninguno"
            self.error(f"evento desconocido 'on:{name}' en <{tag_of(spec)}>", attr.loc, f"eventos disponibles: {available}")
            return
        handler = self.handler(attr, name)
        if handler is not None:
            args = ", ".join(ev.args)
            ir.handlers.setdefault(ev.qml_handler, []).append(f'fx.invoke("{handler.id}", [{args}])')
            if ev.enables:
                ir.props[ev.enables] = Literal("true")

    def handler(self, attr: Attribute, event: str) -> Handler | None:
        if not isinstance(attr.value, Expression):
            self.error(f"on:{event} espera una función entre llaves", attr.loc, f"usa on:{event}={{mi_funcion}}")
            return None
        self.check_expr(attr.value)
        handler = Handler(self.next_id("h"), attr.value, event, attr.loc)
        self.tpl.handlers.append(handler)
        return handler

    def two_way(self, attr: Attribute, el: Element, spec: ControlSpec, ir: IRElement) -> None:
        name = attr.argument
        tw = spec.two_way.get(name)
        if tw is None:
            available = ", ".join(f"bind:{p}" for p in spec.two_way) or "ninguno"
            self.error(f"bind:{name} no está disponible en <{el.tag}>", attr.loc, f"enlaces disponibles: {available}")
            return
        if el.attribute(name) is not None:
            self.error(f"'{name}' y 'bind:{name}' no pueden usarse a la vez", attr.loc)
            return
        expr = attr.value
        target = _parse_name(expr.code) if isinstance(expr, Expression) else None
        if target is None:
            self.error(
                f"bind:{name} necesita el nombre de un state",
                attr.loc,
                f"declara nombre = state(...) en el script y usa bind:{name}={{nombre}}",
            )
            return
        if target in self.local_names():
            self.error(
                f"bind:{name} no puede escribir en la variable de {{#each}} '{target}'",
                attr.loc,
                "usa on:input/on:change y una función del script que actualice la lista",
            )
            return
        if target in self.info.props:
            self.error(
                f"bind:{name} no puede escribir en la prop '{target}': es de solo lectura",
                attr.loc,
                "copia la prop en un state() o emite un evento hacia el padre",
            )
            return
        bid = self.add_expr_binding(expr, attr.loc)
        ir.props[tw.qml_prop] = Bound(bid)
        self.tpl.writes.append(Write(bid, expr, attr.loc))
        ir.handlers.setdefault(tw.qml_handler, []).insert(0, f'fx.write("{bid}", {tw.qml_prop})')

    # -- contenido -----------------------------------------------------------
    def content(self, el: Element, spec: ControlSpec, ir: IRElement) -> None:
        if spec.text_prop:
            self.text_content(el, spec, ir)
        elif el.tag == "Window":
            kids = self.children(el.children, horizontal=False)
            item = self.as_item(kids, el.loc)
            if item is not None:
                item.props["anchors.fill"] = Literal("parent")
                ir.children.append(item)
        elif spec.container:
            ir.children.extend(self.children(el.children, spec.horizontal))
        else:
            for child in el.children:
                if not (isinstance(child, Text) and not child.value.strip()):
                    self.error(f"<{el.tag}> no admite contenido", child.loc, f"usa <{el.tag} ... />")
                    break

    def text_content(self, el: Element, spec: ControlSpec, ir: IRElement) -> None:
        for child in el.children:
            if not isinstance(child, (Text, Interpolation)):
                self.error(f"<{el.tag}> solo admite texto e interpolaciones {{...}}", child.loc)
                return
        parts = _normalize_text(el.children)
        if not parts:
            return
        if el.attribute(spec.text_prop) is not None:
            self.error(f"<{el.tag}> tiene contenido y atributo '{spec.text_prop}' a la vez", el.loc)
            return
        ir.props[spec.text_prop] = self.text_value(parts, el.children[0].loc)

    def text_value(self, parts: list[Union[str, Expression]], loc: SourceLocation) -> PropValue:
        if all(isinstance(p, str) for p in parts):
            return Literal(qml_string("".join(parts)))  # type: ignore[arg-type]
        for part in parts:
            if isinstance(part, Expression):
                self.check_expr(part)
        bid = self.next_id("b")
        self.tpl.bindings.append(TextBinding(bid, parts, loc))
        return Bound(bid)

    def children(self, nodes: list[Node], horizontal: bool) -> list[IRNode]:
        out: list[IRNode] = []
        run: list[Node] = []

        def flush_text() -> None:
            parts = _normalize_text(run)
            if parts:
                label = IRElement("FxText", run[0].loc)
                label.props["text"] = self.text_value(parts, run[0].loc)
                out.append(label)
            run.clear()

        for node in nodes:
            if isinstance(node, (Text, Interpolation)):
                run.append(node)
                continue
            flush_text()
            if isinstance(node, Element):
                if self.is_component(node.tag):
                    out.append(self.component_slot(node))
                else:
                    child = self.element(node)
                    if child is not None:
                        out.append(child)
            elif isinstance(node, IfBlock):
                out.extend(self.if_block(node, horizontal))
            elif isinstance(node, EachBlock):
                out.extend(self.each_block(node, horizontal))
            elif isinstance(node, KeyBlock):
                out.extend(self.key_block(node, horizontal))
        flush_text()
        return out

    # -- regiones dinámicas --------------------------------------------------
    def fragment(self, nodes: list[Node], horizontal: bool, local_names: tuple[str, ...], loc: SourceLocation) -> Fragment:
        tpl = IRTemplate(self.next_id("t"))
        saved = self.tpl
        self.tpl = tpl
        self.scopes.append(set(local_names))
        try:
            meaningful = [n for n in nodes if not (isinstance(n, Text) and not n.value.strip())]
            if len(meaningful) == 1 and isinstance(meaningful[0], Element) and self.is_component(meaningful[0].tag):
                return Fragment(tpl, component=self.component_use(meaningful[0]))
            items = self.children(nodes, horizontal)
            if not items:
                return Fragment(tpl)
            box = self.as_item(items, loc, horizontal)
            if box is not items[0]:
                box.props.update({k: Literal(v) for k, v in _TRANSPARENT_BOX.items()})
            return Fragment(tpl, root=box)
        finally:
            self.tpl = saved
            self.scopes.pop()

    def if_block(self, node: IfBlock, horizontal: bool) -> list[IRNode]:
        branches: list[IfBranchSlot] = []
        for branch in node.branches:
            if branch.condition is not None:
                self.check_expr(branch.condition)
            frag = self.fragment(branch.children, horizontal, (), branch.loc)
            model_id = None if frag.empty else self.next_id("m")
            branches.append(IfBranchSlot(model_id, branch.condition, frag))
        self.tpl.slots.append(IfSlot(branches, node.loc))
        return [IRRepeater(b.model_id, node.loc, b.fragment.root) for b in branches if b.model_id]

    def each_block(self, node: EachBlock, horizontal: bool) -> list[IRNode]:
        self.check_expr(node.iterable)
        local_names = tuple(n for n in (node.item, node.index) if n)
        if node.index is not None and node.index == node.item:
            self.error(f"el índice y el elemento de {{#each}} no pueden llamarse igual ('{node.item}')", node.loc)
        if node.key is not None:
            self.scopes.append(set(local_names))
            self.check_expr(node.key)
            self.scopes.pop()
        frag = self.fragment(node.children, horizontal, local_names, node.loc)
        slot = EachSlot(self.next_id("m"), node.iterable, node.item, node.index, node.key, frag, node.loc)
        if node.else_children is not None:
            empty = self.fragment(node.else_children, horizontal, (), node.loc)
            if not empty.empty:
                slot.empty_model_id = self.next_id("m")
                slot.empty_fragment = empty
        self.tpl.slots.append(slot)
        out: list[IRNode] = []
        if not frag.empty:
            out.append(IRRepeater(slot.model_id, node.loc, frag.root))
        if slot.empty_model_id:
            out.append(IRRepeater(slot.empty_model_id, node.loc, slot.empty_fragment.root))
        return out

    def key_block(self, node: KeyBlock, horizontal: bool) -> list[IRNode]:
        self.check_expr(node.expression)
        frag = self.fragment(node.children, horizontal, (), node.loc)
        if frag.empty:
            return []
        slot = KeySlot(self.next_id("m"), node.expression, frag, node.loc)
        self.tpl.slots.append(slot)
        return [IRRepeater(slot.model_id, node.loc, frag.root)]

    # -- componentes hijos ---------------------------------------------------
    def component_slot(self, el: Element) -> IRRepeater:
        model_id = self.next_id("m")
        use = self.component_use(el)
        self.tpl.slots.append(ComponentSlot(model_id, use, el.loc))
        return IRRepeater(model_id, el.loc)

    def component_use(self, el: Element) -> ComponentUse:
        imp = self.info.components[el.tag]
        iface = self.interface(imp.path) if self.interface else ComponentInterface()
        props: dict[str, PropArg] = {}
        events: dict[str, Handler] = {}
        for attr in el.attributes:
            if attr.directive == "on":
                if attr.argument not in iface.events:
                    available = ", ".join(f"on:{e}" for e in iface.events) or "ninguno"
                    self.error(
                        f"<{el.tag}> no declara el evento '{attr.argument}'",
                        attr.loc,
                        f"eventos disponibles: {available}. En el hijo: {attr.argument} = event()",
                    )
                    continue
                handler = self.handler(attr, attr.argument)
                if handler is not None:
                    events[attr.argument] = handler
            elif attr.directive is not None:
                self.error(
                    f"'{attr.name}' no se admite en componentes",
                    attr.loc,
                    "pasa el valor como prop y escucha un evento del hijo para recibir cambios",
                )
            elif attr.name in ("class", "id"):
                self.error(
                    f"'{attr.name}' aún no se admite en componentes",
                    attr.loc,
                    "aplica estilos y flex en el elemento raíz del componente hijo",
                )
            elif attr.name not in iface.props:
                available = ", ".join(iface.props) or "ninguna"
                close = difflib.get_close_matches(attr.name, list(iface.props), n=1)
                self.error(
                    f"<{el.tag}> no declara la prop '{attr.name}'",
                    attr.loc,
                    (f"¿quisiste decir '{close[0]}'? " if close else "") + f"props disponibles: {available}",
                )
            else:
                props[attr.name] = self.prop_arg(attr)
        missing = [p.name for p in iface.props.values() if p.required and p.name not in props]
        if missing:
            self.error(
                f"falta{'n' if len(missing) > 1 else ''} la{'s' if len(missing) > 1 else ''} prop"
                f"{'s' if len(missing) > 1 else ''} obligatoria{'s' if len(missing) > 1 else ''} "
                f"{', '.join(repr(m) for m in missing)} en <{el.tag}>",
                el.loc,
                " ".join(f"{m}={{...}}" for m in missing),
            )
        for child in el.children:
            if not (isinstance(child, Text) and not child.value.strip()):
                self.error(
                    f"<{el.tag}> no admite contenido entre etiquetas (slots) todavía",
                    child.loc,
                    f"pasa los datos como props: <{el.tag} ... />",
                )
                break
        key = str(imp.path)
        if key not in self.component_paths:
            self.component_paths.append(key)
        return ComponentUse(el.tag, key, props, events, el.loc)

    def prop_arg(self, attr: Attribute) -> PropArg:
        if attr.value is True:
            return ConstArg(True)
        if isinstance(attr.value, str):
            return ConstArg(attr.value)
        lit = _literal(attr.value.code)
        if lit is not _NOT_LITERAL:
            return ConstArg(lit)
        self.check_expr(attr.value)
        return attr.value


def _parse_name(code: str) -> str | None:
    try:
        node = ast.parse(code.strip(), mode="eval").body
    except SyntaxError:
        return None
    return node.id if isinstance(node, ast.Name) else None


def _name_location(expr: Expression, name: str) -> SourceLocation:
    """Ubicación de la primera aparición de `name` dentro de la expresión."""
    m = re.search(rf"(?<![\w.]){re.escape(name)}\b", expr.code)
    if not m:
        return expr.loc
    before = expr.code[: m.start()]
    lines = before.count("\n")
    if lines == 0:
        return SourceLocation(expr.loc.file, expr.loc.line, expr.loc.column + len(before))
    return SourceLocation(expr.loc.file, expr.loc.line + lines, len(before) - before.rfind("\n"))


def _normalize_text(nodes: list[Node]) -> list[Union[str, Expression]]:
    """Colapsa espacios como HTML y quita los de los extremos."""
    parts: list[Union[str, Expression]] = []
    for node in nodes:
        if isinstance(node, Text):
            text = re.sub(r"\s+", " ", node.value)
            if parts and isinstance(parts[-1], str):
                parts[-1] += text
            elif text:
                parts.append(text)
        elif isinstance(node, Interpolation):
            parts.append(node.expression)
    if parts and isinstance(parts[0], str):
        parts[0] = parts[0].lstrip()
    if parts and isinstance(parts[-1], str):
        parts[-1] = parts[-1].rstrip()
    return [p for p in parts if not (isinstance(p, str) and not p)]
