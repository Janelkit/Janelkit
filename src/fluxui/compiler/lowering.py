"""AST -> IR. Valida elementos, atributos, directivas y estilos antes de generar QML.

Los errores se acumulan para informar de varios problemas en una sola
compilación.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Union

from ..diagnostics import Diagnostic, FluxError, SourceLocation
from ..qt_backend.controls import CONTROLS, QML_IMPORTS, ControlSpec, PropSpec, all_props, prop_spec
from ..styling.compiler import compile_declarations, matching_declarations
from ..styling.parser import Rule, parse_stylesheet
from .ast_nodes import SFC, Attribute, EachBlock, Element, Expression, IfBlock, Interpolation, Node, Text
from .ir import (
    Bound,
    ExprBinding,
    Guard,
    Handler,
    IRComponent,
    IRElement,
    Literal,
    PropValue,
    TextBinding,
    VisibilityBinding,
    Write,
    qml_string,
)

_NOT_LITERAL = object()


def lower(sfc: SFC) -> IRComponent:
    return _Lowerer(sfc).run()


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
    def __init__(self, sfc: SFC):
        self.sfc = sfc
        self.errors: list[Diagnostic] = []
        self.warnings: list[Diagnostic] = []
        self.bindings: list = []
        self.handlers: list[Handler] = []
        self.writes: list[Write] = []
        self.rules: list[Rule] = []

    # -- utilidades ----------------------------------------------------------
    def error(self, msg: str, loc: SourceLocation, hint: str | None = None) -> None:
        self.errors.append(Diagnostic(msg, loc, hint, source=self.sfc.source))

    def new_binding_id(self) -> str:
        return f"b{len(self.bindings)}"

    def add_expr_binding(self, expr: Expression, loc: SourceLocation) -> str:
        bid = self.new_binding_id()
        self.bindings.append(ExprBinding(bid, expr, loc))
        return bid

    # -- entrada -------------------------------------------------------------
    def run(self) -> IRComponent:
        sfc = self.sfc
        if sfc.style:
            self.rules = parse_stylesheet(sfc.style.content, sfc.style.loc, sfc.source)

        roots = sfc.root_elements
        start = SourceLocation(sfc.file, 1, 1)
        root_ir: IRElement | None = None
        if not roots:
            self.error("la plantilla está vacía", start, "añade un elemento raíz, por ejemplo <Window>")
        else:
            for extra in roots[1:]:
                self.error(
                    "solo se admite un elemento raíz en la plantilla",
                    extra.loc,
                    "agrupa los elementos dentro de un <Window> o <Column>",
                )
            first = roots[0]
            if not isinstance(first, Element):
                self.error("la raíz de la plantilla debe ser un elemento", first.loc)
            else:
                root_ir = self.element(first, [])
        if self.errors:
            raise FluxError(self.errors)
        assert root_ir is not None

        if root_ir.qml_type != "ApplicationWindow":
            window = IRElement("ApplicationWindow", root_ir.loc)
            window.props.update({k: Literal(v) for k, v in CONTROLS["Window"].defaults.items()})
            window.children.append(root_ir)
            root_ir = window

        return IRComponent(
            file=sfc.file,
            source=sfc.source,
            root=root_ir,
            script=sfc.script,
            bindings=self.bindings,
            handlers=self.handlers,
            writes=self.writes,
            imports=QML_IMPORTS,
            warnings=self.warnings,
        )

    # -- elementos -----------------------------------------------------------
    def element(self, el: Element, guards: list[Guard]) -> IRElement | None:
        spec = CONTROLS.get(el.tag)
        if spec is None:
            self.error(
                f"elemento desconocido <{el.tag}>",
                el.loc,
                "elementos disponibles: " + ", ".join(sorted(CONTROLS)),
            )
            return None
        ir = IRElement(spec.qml_type, el.loc)
        ir.props.update({k: Literal(v) for k, v in spec.defaults.items()})

        classes = self.classes(el)
        decls = matching_declarations(self.rules, el.tag, classes)
        for qml_prop, value in compile_declarations(decls, spec.qml_type, self.sfc.source, self.warnings).items():
            ir.props[qml_prop] = Literal(value)

        visible_expr: Expression | None = None
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
            elif attr.directive is not None:
                self.error(f"directiva desconocida '{attr.directive}:'", attr.loc, "las directivas disponibles son on: y bind:")
            elif attr.name == "visible" and guards and isinstance(attr.value, Expression):
                visible_expr = attr.value
            else:
                self.prop(attr, el, spec, ir)

        if guards:
            bid = self.new_binding_id()
            self.bindings.append(VisibilityBinding(bid, list(guards), visible_expr, el.loc))
            ir.props["visible"] = Bound(bid)

        self.content(el, spec, ir)
        return ir

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
            self.error(
                f"propiedad desconocida '{attr.name}' en <{el.tag}>",
                attr.loc,
                "propiedades disponibles: " + ", ".join(all_props(spec)),
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
            self.error(f"evento desconocido 'on:{name}' en <{spec_tag(spec)}>", attr.loc, f"eventos disponibles: {available}")
            return
        if not isinstance(attr.value, Expression):
            self.error(f"on:{name} espera una función entre llaves", attr.loc, f"usa on:{name}={{mi_funcion}}")
            return
        hid = f"h{len(self.handlers)}"
        self.handlers.append(Handler(hid, attr.value, name, attr.loc))
        args = ", ".join(ev.args)
        ir.handlers.setdefault(ev.qml_handler, []).append(f'fx.invoke("{hid}", [{args}])')

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
        if not (isinstance(expr, Expression) and isinstance(_parse_name(expr.code), str)):
            self.error(
                f"bind:{name} necesita el nombre de un state",
                attr.loc,
                f"declara nombre = state(...) en el script y usa bind:{name}={{nombre}}",
            )
            return
        bid = self.add_expr_binding(expr, attr.loc)
        ir.props[tw.qml_prop] = Bound(bid)
        self.writes.append(Write(bid, expr, attr.loc))
        ir.handlers.setdefault(tw.qml_handler, []).insert(0, f'fx.write("{bid}", {tw.qml_prop})')

    # -- contenido -----------------------------------------------------------
    def content(self, el: Element, spec: ControlSpec, ir: IRElement) -> None:
        if spec.text_prop:
            self.text_content(el, spec, ir)
        elif spec.container:
            ir.children.extend(self.children(el.children, []))
            if spec.qml_type == "ApplicationWindow" and len(ir.children) > 1:
                column = IRElement("Column", el.loc)
                column.children = ir.children
                ir.children = [column]
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
        bid = self.new_binding_id()
        self.bindings.append(TextBinding(bid, parts, loc))
        return Bound(bid)

    def children(self, nodes: list[Node], guards: list[Guard]) -> list[IRElement]:
        out: list[IRElement] = []
        run: list[Node] = []

        def flush_text() -> None:
            parts = _normalize_text(run)
            if parts:
                label = IRElement("Label", run[0].loc)
                label.props["text"] = self.text_value(parts, run[0].loc)
                if guards:
                    bid = self.new_binding_id()
                    self.bindings.append(VisibilityBinding(bid, list(guards), None, run[0].loc))
                    label.props["visible"] = Bound(bid)
                out.append(label)
            run.clear()

        for node in nodes:
            if isinstance(node, (Text, Interpolation)):
                run.append(node)
                continue
            flush_text()
            if isinstance(node, Element):
                child = self.element(node, guards)
                if child is not None:
                    out.append(child)
            elif isinstance(node, IfBlock):
                conditions = [b.condition for b in node.branches if b.condition is not None]
                for index, branch in enumerate(node.branches):
                    out.extend(self.children(branch.children, [*guards, Guard(conditions, index)]))
            elif isinstance(node, EachBlock):
                self.error("{#each} aún no está soportado", node.loc, "llegará en el Incremento 4 (listas con clave)")
        flush_text()
        return out


def spec_tag(spec: ControlSpec) -> str:
    return next((tag for tag, s in CONTROLS.items() if s is spec), spec.qml_type)


def _parse_name(code: str) -> str | None:
    try:
        node = ast.parse(code.strip(), mode="eval").body
    except SyntaxError:
        return None
    return node.id if isinstance(node, ast.Name) else None


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
