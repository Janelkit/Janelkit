"""AST -> IR. Valida elementos, atributos, directivas, nombres y estilos antes de generar QML.

Los errores se acumulan para informar de varios problemas en una sola
compilación.
"""
from __future__ import annotations

import ast
import builtins
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Union

from ..diagnostics import Diagnostic, FluxError, SourceLocation
from ..qt_backend.controls import (
    BASE_ELEMENTS,
    CHOICES,
    CONTROLS,
    ROUTED_EVENTS,
    INTERACTIVE_ROLES,
    ROUTE,
    QML_IMPORTS,
    ControlSpec,
    PropSpec,
    all_props,
    prop_spec,
    tag_of,
)
from ..styling.compiler import BEHAVIOR, INHERITED, SUPPORTED, TEXT_PREFIX, VAR_PREFIX, compile_declarations, token_key
from ..styling.parser import Declaration, Rule, parse_stylesheet
from .cascade import ALWAYS, Cascade, StyleNode
from .layout_choice import BOX_TYPES, choose_layouts
from .ast_nodes import SFC, Attribute, EachBlock, Element, Expression, IfBlock, Interpolation, KeyBlock, Node, Text
from .qml_interface import QmlImport, read_interface
from .expressions import EVENT_NAME, free_names, handler_names, is_inline_handler
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
    RefUse,
    SlotOutlet,
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
    "gap": "parent && parent.fxBox ? Fx.mainGap(parent) : 0",
    "alignItems": 'parent && parent.fxBox ? parent.fxBox.alignItems : ""',
    "fxLegacy": "parent && parent.fxBox ? parent.fxBox.fxLegacy : true",
    "fxFlex": "fillMain ? 1 : 0",
}

# Propiedades de un hijo de <flex> que los controles no declaran: el compilador las
# declara en el elemento que las usa (tipo, valor por defecto = sin fijar).
_FLEX_ITEM_EXTRAS = {
    "fxOrder": ("int", "0"),
    "fxShrink": ("real", "NaN"),
    "fxBasis": ("real", "-2"),
    "fxBasisPct": ("real", "0"),
    "fxWidthPct": ("real", "0"),
    "fxHeightPct": ("real", "0"),
    "fxAutoMargin": ("int", "0"),
    "fxPosition": ("string", '""'),
    "fxTop": ("var", "undefined"),
    "fxRight": ("var", "undefined"),
    "fxBottom": ("var", "undefined"),
    "fxLeft": ("var", "undefined"),
}
# Lo que un elemento .qml propio comunica a su contenedor <flex> (ver flex.js).
_TOUCH_DEPS = (
    "visible",
    "Layout.preferredWidth", "Layout.preferredHeight", "Layout.minimumWidth", "Layout.minimumHeight",
    "Layout.maximumWidth", "Layout.maximumHeight", "Layout.fillWidth", "Layout.fillHeight",
    "Layout.leftMargin", "Layout.topMargin", "Layout.rightMargin", "Layout.bottomMargin",
)  # fmt: skip


@dataclass
class ComponentInterface:
    """Lo que un componente padre necesita saber de un hijo para validar su uso."""

    props: dict[str, PropDecl] = field(default_factory=dict)
    events: dict[str, EventDecl] = field(default_factory=dict)
    slots: frozenset[str] | None = None  # nombres de <Slot>; None = desconocido (no se valida)
    root_box: bool = False  # su raíz es una caja y hereda atributos: van a ella (FxRemote)
    inherit_attrs: bool = True
    root_items: frozenset[str] | None = None  # lo que su raíz pide a la caja que lo contiene (None: no se sabe)


# Atributos de la etiqueta de un componente que no son props: se aplican a una
# caja exterior que envuelve al componente (clases, id, tamaño y flex).
_WRAPPER_ATTRS = frozenset({"class", "id", "flex", "width", "height", "visible"})
# Si la raíz del componente es una caja, además pasan a ella estos y los eventos nativos.
_PASSED_ATTRS = _WRAPPER_ATTRS | {"style", "label", "title", "tabindex", "disabled", "ref", "as"}
# Lo que en una caja se lee de sí misma sin id; en un FxRemote se lee de la raíz.
_BARE = re.compile(r"(?<![\w.])(hovered|ToolTip\.text|enabled|activeFocus)\b")


InterfaceLookup = Callable[[Path], ComponentInterface]


def lower(
    sfc: SFC,
    info: ScriptInfo | None = None,
    *,
    as_window: bool = True,
    interface: InterfaceLookup | None = None,
    root_in_engine: bool = False,
) -> IRComponent:
    lowerer = _Lowerer(sfc, info or ScriptInfo(), as_window, interface)
    lowerer.root_in_engine = root_in_engine
    return lowerer.run()


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
        self.root_in_engine = False  # la raíz va dentro de una caja con el motor (layout_choice.py)
        self.slot_fragments: list[Fragment] = []
        self.qml_imports: dict[str, QmlImport] = {}  # tag -> import
        self.pending_transitions: dict[int, SourceLocation] = {}  # id(IRElement) -> ubicación
        self.use_counts: dict[str, int] = {}  # etiqueta de componente -> usos vistos
        self.qml_specs: dict[str, ControlSpec] = {}
        self._reported: set[tuple] = set()
        self.cascade = Cascade(self.rules, lambda: self.next_id("fxs"), self.style_warning)
        self.style_stack: list[StyleNode] = []  # antecesores en la plantilla (selectores de descendiente)
        self.doc = 0  # documento QML actual: el contenido de cada slot es otro
        self.docs = 0
        self.local_vars: frozenset[str] = frozenset()
        self.passed_root: Element | None = None  # raíz que recibe los atributos de la etiqueta
        self.last_node: StyleNode | None = None

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
        """Componente .flux (los .qml importados son elementos, ver `spec_for`)."""
        imp = self.info.components.get(tag)
        return imp is not None and imp.path.suffix != ".qml"

    def spec_for(self, tag: str) -> ControlSpec | None:
        """Elemento integrado o elemento propio importado de un archivo .qml."""
        imp = self.info.components.get(tag)
        if imp is None or imp.path.suffix != ".qml":
            return CONTROLS.get(tag)
        if tag not in self.qml_specs:
            folders = {i.directory: i.alias for i in self.qml_imports.values()}
            alias = folders.get(imp.path.parent, f"FxUser{len(folders)}")
            self.qml_imports[tag] = QmlImport(alias, imp.path.parent, tag)
            self.qml_specs[tag] = read_interface(imp.path, tag, alias)
        return self.qml_specs[tag]

    # -- nombres -------------------------------------------------------------
    def local_names(self) -> set[str]:
        return set().union(*self.scopes) if self.scopes else set()

    def check_expr(self, expr: Expression, names: list[str] | None = None) -> None:
        """Avisa de nombres que no define el script ni un {#each} que los contenga."""
        if self.info.defined is None:
            return
        if names is None:
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

    def check_inline(self, expr: Expression, event: str) -> None:
        """Manejador en línea: los nombres asignados deben ser state del script."""
        loads, stores = handler_names(expr.code)
        self.check_expr(expr, loads + [n for n in stores if n not in loads])
        for name in stores:
            loc = _name_location(expr, name)
            if name in self.local_names():
                self.error(
                    f"on:{event} no puede asignar a la variable de bloque '{name}'",
                    loc,
                    f"modifica el elemento en el sitio ({name}[\"campo\"] = ...) o usa una función del script",
                )
            elif name in self.info.props:
                self.error(f"on:{event} no puede asignar a la prop '{name}': es de solo lectura", loc,
                           "emite un evento hacia el padre o copia la prop en un state()")
            elif name == EVENT_NAME:
                self.error(f"'{EVENT_NAME}' es el argumento del evento y no se puede asignar", loc)

    # -- entrada -------------------------------------------------------------
    def run(self) -> IRComponent:
        sfc = self.sfc
        if sfc.style:
            self.rules = parse_stylesheet(sfc.style.content, sfc.style.loc, sfc.source)
            self.cascade.rules = self.rules
        # Variables propias (--x) que define este componente, en <style> o en style=:
        # var(--x) las busca en los antecesores en vez de en el tema.
        self.local_vars = frozenset(
            {token_key(d.prop[2:]) for r in self.rules for d in r.declarations if d.prop.startswith("--")}
            | _inline_vars(sfc.root_elements)
        )

        root_tpl = self.tpl
        roots = sfc.root_elements
        if (
            not self.as_window and len(roots) == 1 and isinstance(roots[0], Element)
            and roots[0].tag in ("flex", "Column", "Row") and self.info.inherit_attrs
        ):  # fmt: skip
            self.passed_root = roots[0]
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
                    _fill_parent(content)
                    root_ir.children.append(content)
                else:
                    root_ir = content
        for loc in self.pending_transitions.values():
            self.error(
                "transition:, in: y out: solo se aplican al elemento raíz de un bloque {#if}, {#each} o {#key}",
                loc,
                "si el bloque tiene varios elementos, agrúpalos en un <Column> o <Row> y pon ahí la transición",
            )
        if self.errors:
            raise FluxError(self.errors)
        assert root_ir is not None
        # Layout de Qt o motor de <flex> para cada caja (layout_choice.py).
        engine_children = choose_layouts(
            [root_ir, *(f.root for f in self.slot_fragments if f.root is not None)],
            self.root_features, self.root_in_engine,
        )
        # Avisa al runtime de que la vista existe (on_mount) y cuál es su raíz.
        root_ir.handlers.setdefault("Component.onCompleted", []).append("fx.mounted(this)")

        return IRComponent(
            file=sfc.file,
            source=sfc.source,
            root=root_ir,
            template=root_tpl,
            script=sfc.script,
            script_info=self.info,
            is_window=self.as_window,
            imports=QML_IMPORTS + tuple(dict.fromkeys(i.import_line for i in self.qml_imports.values())),
            warnings=self.warnings,
            tokens=self.tokens,
            component_paths=self.component_paths,
            engine_children=sorted(engine_children),
            slot_fragments=self.slot_fragments,
            qml_files=sorted({str(self.info.components[t].path) for t in self.qml_imports}),
            class_names=self.class_names(),
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
    def inline_style(self, attr: Attribute, el: Element, ir: IRElement) -> None:
        """`style="gap: 4px"` o `style={{"background": color, "--acento": c}}`: gana a las reglas y a los estados."""
        if isinstance(attr.value, str):
            decls = []
            for chunk in attr.value.split(";"):
                if not chunk.strip():
                    continue
                if ":" not in chunk:
                    self.error(f"style: declaración no válida {chunk.strip()!r}", attr.loc, 'usa style="propiedad: valor; ..."')
                    return
                prop, value = chunk.split(":", 1)
                decls.append(Declaration(prop.strip().lower(), value.strip(), attr.loc))
            props = compile_declarations(decls, el.tag, self.sfc.source, self.warnings, self.tokens, self.local_vars)
            for key in [k for k in props if k.startswith(BEHAVIOR)]:
                ir.behaviors[key[len(BEHAVIOR):]] = props.pop(key)
            self.override(ir, {k: Literal(v) for k, v in props.items()})
            return
        try:
            node = ast.parse(attr.value.code.strip(), mode="eval").body
        except SyntaxError:
            node = None
        if not isinstance(node, ast.Dict) or not all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys):
            self.error(
                "style={...} espera un diccionario con nombres de propiedad fijos",
                attr.loc,
                'p. ej. style={{"background": color, "width": f"{pct}%", "--acento": acento}}; para clases usa class={...}',
            )
            return
        box = el.tag in ("flex", "Column", "Row")
        values: dict[str, Literal] = {}
        for key_node, value_node in zip(node.keys, node.values):
            name = key_node.value.strip().lower()
            expr = Expression(ast.get_source_segment(attr.value.code.strip(), value_node) or "None", attr.loc)
            if name.startswith("--"):
                if not box:
                    self.error(f"las variables propias ({name}) se definen en <flex>, Column o Row", attr.loc)
                    continue
                values[VAR_PREFIX + token_key(name[2:])] = Literal(f"fx.{self.add_expr_binding(expr, attr.loc)}")
                continue
            targets = _INLINE.get(name)
            entry = SUPPORTED.get(name)
            if targets is None or entry is None or (el.tag in CONTROLS and el.tag not in entry[0]):
                where = "" if targets is None else f" en <{el.tag}>"
                self.error(
                    f"style={{...}} no admite '{name}'{where}",
                    attr.loc,
                    "con valores de Python: " + ", ".join(sorted(_INLINE)) + " y variables (--x); el resto, en <style> o con class",
                )
                continue
            bid = self.add_expr_binding(expr, attr.loc)
            for qml_prop, template in targets:
                if box and qml_prop in INHERITED:
                    qml_prop = TEXT_PREFIX + INHERITED[qml_prop]
                values[qml_prop] = Literal(template.format(f"fx.{bid}"))
        self.override(ir, values)

    @staticmethod
    def override(ir: IRElement, values: dict[str, Literal]) -> None:
        """Valores en línea: sustituyen a los de las reglas, también a los de los estados."""
        ir.props.update(values)
        ir.conditional[:] = [c for c in ir.conditional if c[0] not in values or c[2] == "true"]

    def check_role(self, el: Element, ir: IRElement) -> None:
        """`<flex as="button">` sin texto ni label: el lector de pantalla no tendría qué leer."""
        role = ir.props.get("fxRole")
        if role is not None and not isinstance(role, Literal):
            return  # as={...}: el papel se sabe al ejecutar
        interactive = role is not None and role.qml.strip('"') in INTERACTIVE_ROLES
        if not interactive and not (role is None and "fxClickable" in ir.props and el.tag == "flex"):
            return
        if "Accessible.name" in ir.props or _has_text(el.children):
            return
        what = f'as={role.qml}' if role is not None else "on:click"
        self.warnings.append(
            Diagnostic(
                f"<{el.tag} {what}> no tiene texto ni label: un lector de pantalla no sabría qué es",
                el.loc,
                'añade label="..." (p. ej. label="Cerrar") o un texto dentro',
                severity="warning",
                source=self.sfc.source,
            )
        )

    def style_warning(self, msg: str, rule: Rule) -> None:
        self.warnings.append(Diagnostic(msg, rule.loc, severity="warning", source=self.sfc.source))

    def element(self, el: Element, allow_window: bool = False, match_tag: str | None = None) -> IRElement | None:
        """`match_tag`: etiqueta para los selectores (la caja exterior de un componente usa la suya)."""
        spec = self.spec_for(el.tag)
        if spec is None:
            self.unknown_element(el)
            return None
        if el.tag == "Window" and not allow_window:
            self.error("<Window> solo puede usarse como raíz de la plantilla", el.loc, "usa <Column> o <Row>")
            return None
        ir = IRElement(spec.qml_type, el.loc)
        ir.props.update({k: Literal(v) for k, v in spec.fixed.items()})
        node = self.style_node(el, ir, match_tag)
        node.passed = el is self.passed_root
        self.last_node = node
        self.apply_styles(self.style_stack + [node], el.tag, ir)

        for attr in el.attributes:
            if attr.name == "class" or attr.directive == "class":
                continue
            if attr.name == "style" and attr.directive is None:
                self.inline_style(attr, el, ir)
                continue
            if attr.name == "id":
                if isinstance(attr.value, str) and attr.value:
                    ir.props["objectName"] = Literal(qml_string(attr.value))
                else:
                    self.error('el atributo id debe ser un texto literal, p. ej. id="guardar"', attr.loc)
            elif attr.name == "ref" or (el.tag == "Pages" and attr.name == "stack") or (el.tag == "Sections" and attr.name == "of"):
                self.ref(attr, ir)
            elif attr.directive == "on":
                self.event(attr, spec, ir)
            elif attr.directive == "bind":
                self.two_way(attr, el, spec, ir)
            elif attr.directive in ("transition", "in", "out"):
                self.transition(attr, ir)
            elif attr.directive is not None:
                self.error(
                    f"directiva desconocida '{attr.directive}:'",
                    attr.loc,
                    "las directivas disponibles son on:, bind:, class:, transition:, in: y out:",
                )
            else:
                self.prop(attr, el, spec, ir)

        if "ToolTip.text" in ir.props:  # title: descripción emergente y para lectores de pantalla
            ir.props["fxTrackHover"] = Literal("true")
            ir.props["ToolTip.visible"] = Literal('hovered && ToolTip.text !== ""')
            ir.props["ToolTip.delay"] = Literal("700")
            ir.props["Accessible.description"] = Literal("ToolTip.text")
        if match_tag is None:  # en la etiqueta de un componente, el papel es el de su raíz
            self.check_role(el, ir)
        _accessible_states(ir, self.cascade)
        _context_extras(ir, self.cascade)
        if spec.tag is not None and "fxFlex" in ir.props:
            _custom_flex(ir)
        _style_extras(ir, self.cascade)
        _flex_item_extras(ir, custom=spec.tag is not None, new_id=lambda: self.next_id("fxi"))

        # Un tamaño fijo desactiva el estiramiento por defecto (texto y campos en columnas).
        for axis in ("Width", "Height"):
            if f"Layout.preferred{axis}" in ir.props:
                ir.props.setdefault(f"Layout.fill{axis}", Literal("false"))

        self.style_stack.append(node)
        try:
            self.content(el, spec, ir)
        finally:
            self.style_stack.pop()
        return ir

    def transition(self, attr: Attribute, ir: IRElement) -> None:
        """`transition:fade`, `in:scale={300}`, `out:slide`: animación al montar/desmontar el bloque."""
        kind = attr.argument
        if kind not in _TRANSITIONS:
            self.error(f"transición desconocida '{kind}'", attr.loc, "disponibles: " + ", ".join(_TRANSITIONS))
            return
        ms = _TRANSITION_MS
        if attr.value is not True:
            value = _literal(attr.value.code) if isinstance(attr.value, Expression) else _NOT_LITERAL
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                self.error(f"{attr.name} espera la duración en milisegundos, p. ej. {attr.name}={{300}}", attr.loc)
                return
            ms = value
        if ir.qml_type == "FxPages":  # <Pages transition:slide>: anima la página que entra
            ir.props["fxTransition"] = Literal(qml_string(kind))
            ir.props["fxTransitionMs"] = Literal(str(ms))
            return
        directions = ("in", "out") if attr.directive == "transition" else (attr.directive,)
        for direction in directions:
            ir.transitions[direction] = (kind, ms)
        self.pending_transitions[id(ir)] = attr.loc

    def attach_transitions(self, frag: Fragment) -> None:
        """Raíz de un bloque con transiciones: un FxTransition hijo hace las animaciones."""
        root = frag.root
        if root is None or not root.transitions:
            return
        self.pending_transitions.pop(id(root), None)
        tid = root.props["id"].qml if "id" in root.props else self.next_id("fxt")
        root.props["id"] = Literal(tid)
        anim = IRElement("FxTransition", root.loc)
        anim.props.update({"target": Literal(tid), "bridge": Literal("fx")})
        for direction, prefix in (("in", "enter"), ("out", "leave")):
            if direction in root.transitions:
                kind, ms = root.transitions[direction]
                anim.props[f"{prefix}Kind"] = Literal(qml_string(kind))
                anim.props[f"{prefix}Ms"] = Literal(str(ms))
        root.children.append(anim)
        if "out" in root.transitions:
            frag.leave_ms = root.transitions["out"][1]

    def ref(self, attr: Attribute, ir: IRElement) -> None:
        name = _parse_name(attr.value.code) if isinstance(attr.value, Expression) else None
        if name is None:
            self.error("ref necesita el nombre de una referencia", attr.loc, "declara campo = ref() en el script y usa ref={campo}")
            return
        if name in self.local_names():
            self.error(f"ref no puede usar la variable de {{#each}} '{name}'", attr.loc, "declara la referencia en el script")
            return
        self.check_expr(attr.value)
        use = RefUse(self.next_id("r"), name, attr.loc)
        self.tpl.refs.append(use)
        ir.handlers.setdefault("Component.onCompleted", []).append(f'fx.setRef("{use.id}", this, true)')

    def class_names(self) -> list[str]:
        """Clases que aparecen en algún selector de <style>, en orden de aparición."""
        return list(dict.fromkeys(c for r in self.rules for c in r.class_names()))

    def style_node(self, el: Element, ir: IRElement | None, match_tag: str | None = None) -> StyleNode:
        """Clases del elemento: fijas, `class:x={cond}` y `class={expr}` (con sus bindings)."""
        toggles: dict[str, str] = {}
        dynamic: str | None = None
        known = set(self.class_names())
        for attr in el.attributes:
            if attr.directive == "class" and ir is not None:
                name = attr.argument
                expr = attr.value
                if expr is True:  # class:activa  ==  class:activa={activa}
                    expr = Expression(name, attr.loc)
                if not isinstance(expr, Expression):
                    self.error(f"class:{name} espera una condición entre llaves", attr.loc, f"usa class:{name}={{condicion}}")
                    continue
                if name not in known:
                    self.warnings.append(
                        Diagnostic(f"la clase '{name}' no tiene reglas en <style>", attr.loc, severity="warning", source=self.sfc.source)
                    )
                    continue
                toggles[name] = self.add_expr_binding(expr, attr.loc)
            elif attr.name == "class" and isinstance(attr.value, Expression) and ir is not None:
                # class={expr}: el binding vale " a b " (ver runtime/component.py).
                self.check_expr(attr.value)
                dynamic = self.next_id("b")
                self.tpl.bindings.append(ExprBinding(dynamic, attr.value, attr.loc, classes=True))
        return StyleNode(match_tag or el.tag, frozenset(self.classes(el)), toggles, dynamic, ir, self.doc)

    def apply_styles(self, chain: list[StyleNode], tag: str, ir: IRElement) -> None:
        """Propiedades de las reglas que aplican: fijas, o con la condición de su estado."""
        compiled: list[tuple[str, dict[str, str]]] = []
        for m in self.cascade.matches(chain):
            props = compile_declarations(
                m.decls, tag, self.sfc.source, [] if m.quiet else self.warnings, self.tokens, self.local_vars
            )
            for key in [k for k in props if k.startswith(BEHAVIOR)]:  # la animación es del elemento
                ir.behaviors[key[len(BEHAVIOR):]] = props.pop(key)
            compiled.append((m.cond, props))
        if ir.qml_type in _BOXES and any(k.startswith("fxOutline") for _, p in compiled for k in p):
            ir.props["fxCustomOutline"] = Literal("true")
        layers: list[tuple[str, dict[str, str]]] = []
        for i, (cond, props) in enumerate(compiled):
            if cond == ALWAYS:
                ir.props.update({k: Literal(v) for k, v in props.items()})
                continue
            # Una regla fija posterior gana a esta (la última gana).
            later = {k for c, p in compiled[i + 1:] if c == ALWAYS for k in p}
            props = {k: v for k, v in props.items() if k not in later}
            if props:
                layers.append((cond, props))
        # En orden de precedencia: si varias fijan lo mismo, gana la última activa (qml_generator).
        for when, props in layers:
            for prop, value in props.items():
                ir.conditional.append((prop, value, when))

    def unknown_element(self, el: Element) -> None:
        if el.tag[:1].islower():
            # Las etiquetas en minúscula son los elementos base de FluxUI.
            close = difflib.get_close_matches(el.tag, BASE_ELEMENTS, n=1)
            hint = (f"¿quisiste decir <{close[0]}>? " if close else "") + "elementos base: " + ", ".join(
                f"<{t}>" for t in BASE_ELEMENTS
            ) + ". Los componentes se escriben en mayúscula"
            self.error(f"elemento base desconocido <{el.tag}>", el.loc, hint)
            return
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
            return []  # class={expr}: lo resuelve style_node
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
        choices = CHOICES.get((el.tag, attr.name))
        if choices and isinstance(attr.value, str) and attr.value not in choices:
            self.error(
                f"valor no válido para '{attr.name}' en <{el.tag}>: {attr.value!r}",
                attr.loc,
                "valores admitidos: " + ", ".join(choices),
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
        if handler is not None and ev.qml_handler == ROUTE:
            # Eventos de las cajas: los entrega events.py (propagación, prevent, stop).
            routes = dict(_routes(ir))
            routes[name] = handler.id
            ir.props["fxOn"] = Literal("({" + ", ".join(f'"{k}": "{v}"' for k, v in routes.items()) + "})")
            ir.props["fxBridge"] = Literal("fx")
            if name != "click":
                ir.props["fxListen"] = Literal("true")
            if ev.enables:
                ir.props[ev.enables] = Literal("true")
        elif handler is not None:
            args = ", ".join(ev.args)
            call = f'fx.invoke("{handler.id}", [{args}])'
            ir.handlers.setdefault(ev.qml_handler, []).append(f"if ({ev.when}) {call}" if ev.when else call)
            if ev.params:
                ir.handler_params[ev.qml_handler] = ev.params
            if ev.enables:
                ir.props[ev.enables] = Literal("true")

    def handler(self, attr: Attribute, event: str) -> Handler | None:
        if not isinstance(attr.value, Expression):
            self.error(f"on:{event} espera una función entre llaves", attr.loc, f"usa on:{event}={{mi_funcion}}")
            return None
        inline = is_inline_handler(attr.value.code)
        if inline:
            self.check_inline(attr.value, event)
        else:
            self.check_expr(attr.value)
        handler = Handler(self.next_id("h"), attr.value, event, attr.loc, inline)
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
        path = _parse_path(expr.code) if isinstance(expr, Expression) else None
        if path is None:
            self.error(
                f"bind:{name} necesita el nombre de un state",
                attr.loc,
                f"declara nombre = state(...) en el script y usa bind:{name}={{nombre}} (o {{modulo.nombre}})",
            )
            return
        # Con un punto (prefs.tema) se escribe en el state que hay al final: si lo es, se
        # comprueba al ejecutar. La variable de la fila o la prop solo son el camino.
        target = path[0] if len(path) == 1 else None
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
        self.tpl.writes.append(Write(bid, expr, attr.loc))
        if tw.params:
            ir.handler_params[tw.qml_handler] = tw.params
        if spec.tag is None:
            ir.props[tw.qml_prop] = Bound(bid)
            ir.handlers.setdefault(tw.qml_handler, []).insert(0, f'fx.write("{bid}", {tw.qml_value or tw.qml_prop})')
            return
        # Elemento QML propio: su señal <prop>Changed también salta con los cambios que
        # llegan de Python, y su código puede asignar la propiedad (lo que rompería un
        # binding normal). Un Binding sobrevive a esas asignaciones, y solo se devuelve
        # a Python un valor distinto del que ya tiene.
        prop = tw.qml_prop
        ir.conditional.append((prop, f"fx.{bid}", "true"))
        ir.handlers.setdefault(tw.qml_handler, []).insert(0, f'if ({prop} !== fx.{bid}) fx.write("{bid}", {prop})')

    # -- contenido -----------------------------------------------------------
    def content(self, el: Element, spec: ControlSpec, ir: IRElement) -> None:
        if el.tag == "List":
            self.list_content(el, ir)
        elif spec.text_prop:
            self.text_content(el, spec, ir)
        elif el.tag == "Window":
            kids = self.children(el.children, horizontal=False)
            item = self.as_item(kids, el.loc)
            if item is not None:
                _fill_parent(item)
                ir.children.append(item)
        elif spec.container:
            ir.children.extend(self.children(el.children, spec.horizontal))
        else:
            for child in el.children:
                if not (isinstance(child, Text) and not child.value.strip()):
                    self.error(f"<{el.tag}> no admite contenido", child.loc, f"usa <{el.tag} ... />")
                    break

    def list_content(self, el: Element, ir: IRElement) -> None:
        """`<List>{#each ...}{/each}</List>`: una lista virtualizada (ListView)."""
        blocks = [n for n in el.children if not (isinstance(n, Text) and not n.value.strip())]
        if len(blocks) != 1 or not isinstance(blocks[0], EachBlock):
            loc = blocks[0].loc if blocks else el.loc
            self.error(
                "<List> debe contener exactamente un bloque {#each}",
                loc,
                "<List>{#each elementos as e (e['id'])}<Row>...</Row>{/each}</List>; para contenido libre usa <Scroll>",
            )
            return
        node = blocks[0]
        if node.else_children is not None:
            self.error("{:else} no está disponible dentro de <List>", node.loc, "muestra el estado vacío con un {#if} fuera de la lista")
        for rep in self.each_block(node, horizontal=False, lazy=True):
            ir.props["model"] = Literal(f"fx.{rep.model_id}")
            ir.delegate = rep.delegate
        animate = el.attribute("animate")
        if animate is not None and self.tpl.slots and isinstance(self.tpl.slots[-1], EachSlot):
            self.tpl.slots[-1].animated = animate.value is True or (
                isinstance(animate.value, Expression) and _literal(animate.value.code) is True
            )

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
                if node.tag == "Slot" and not self.is_component("Slot"):
                    out.extend(self.slot_outlet(node, horizontal))
                elif self.is_component(node.tag):
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
    def fragment(
        self,
        nodes: list[Node],
        horizontal: bool,
        local_names: tuple[str, ...],
        loc: SourceLocation,
        component_root: bool = True,
    ) -> Fragment:
        """Contenido de un bloque. Con `component_root=False` la raíz es siempre un elemento propio."""
        tpl = IRTemplate(self.next_id("t"))
        saved = self.tpl
        self.tpl = tpl
        self.scopes.append(set(local_names))
        try:
            meaningful = [n for n in nodes if not (isinstance(n, Text) and not n.value.strip())]
            only = meaningful[0] if len(meaningful) == 1 else None
            if component_root and isinstance(only, Element) and self.is_component(only.tag) and not self.tag_attrs(only):
                return Fragment(tpl, component=self.component_use(only))
            items = self.children(nodes, horizontal)
            if not items:
                return Fragment(tpl)
            box = self.as_item(items, loc, horizontal)
            if box is not items[0]:
                box.props.update({k: Literal(v) for k, v in _TRANSPARENT_BOX.items()})
                # La dirección del padre (<flex direction="column"> con un {#if} de varios elementos).
                own = "row" if horizontal else "column"
                box.props["direction"] = Literal(f'parent && parent.fxBox ? parent.fxBox.direction : "{own}"')
            frag = Fragment(tpl, root=box)
            if component_root:  # en <List> las filas se animan con <List animate>
                self.attach_transitions(frag)
            return frag
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
        return [IRRepeater(b.model_id, node.loc, b.fragment.root, _path(b.fragment)) for b in branches if b.model_id]

    def each_block(self, node: EachBlock, horizontal: bool, lazy: bool = False) -> list[IRNode]:
        self.check_expr(node.iterable)
        local_names = tuple(n for n in (node.item, node.index) if n)
        if node.index is not None and node.index == node.item:
            self.error(f"el índice y el elemento de {{#each}} no pueden llamarse igual ('{node.item}')", node.loc)
        if node.key is not None:
            self.scopes.append(set(local_names))
            self.check_expr(node.key)
            self.scopes.pop()
        frag = self.fragment(node.children, horizontal, local_names, node.loc, component_root=not lazy)
        slot = EachSlot(self.next_id("m"), node.iterable, node.item, node.index, node.key, frag, node.loc, lazy=lazy)
        if lazy and frag.root is not None:
            # En un ListView las filas no están en un layout: ocupan el ancho de la lista.
            frag.root.props["width"] = Literal("ListView.view ? ListView.view.width : implicitWidth")
            if frag.root.qml_type in _BOXES:
                frag.root.props["fxSizedW"] = Literal("true")
        if node.else_children is not None and not lazy:
            empty = self.fragment(node.else_children, horizontal, (), node.loc)
            if not empty.empty:
                slot.empty_model_id = self.next_id("m")
                slot.empty_fragment = empty
        self.tpl.slots.append(slot)
        out: list[IRNode] = []
        if not frag.empty:
            out.append(IRRepeater(slot.model_id, node.loc, frag.root, _path(frag), many=True))
        if slot.empty_model_id:
            out.append(IRRepeater(slot.empty_model_id, node.loc, slot.empty_fragment.root, _path(slot.empty_fragment)))
        return out

    def key_block(self, node: KeyBlock, horizontal: bool) -> list[IRNode]:
        self.check_expr(node.expression)
        if node.hidden:
            out = self.hidden_branch(node.children, node.expression, node.loc, horizontal)
            if node.else_children is not None:
                opposite = Expression(f"not ({node.expression.code.strip()})", node.expression.loc)
                out += self.hidden_branch(node.else_children, opposite, node.loc, horizontal)
            return out
        frag = self.fragment(node.children, horizontal, (), node.loc)
        if frag.empty:
            return []
        slot = KeySlot(self.next_id("m"), node.expression, frag, node.loc)
        self.tpl.slots.append(slot)
        return [IRRepeater(slot.model_id, node.loc, frag.root, _path(frag))]

    def hidden_branch(self, nodes: list[Node], condition: Expression, loc: SourceLocation, horizontal: bool) -> list[IRNode]:
        """Una rama de {#hidden}: se crea la primera vez que `condition` es falsa y después solo se oculta."""
        frag = self.fragment(nodes, horizontal, (), loc, component_root=False)
        if frag.empty:
            return []
        shown = self.hide_when(frag, condition, horizontal)
        slot = KeySlot(self.next_id("m"), condition, frag, loc, hidden=True, shown_id=shown)
        self.tpl.slots.append(slot)
        return [IRRepeater(slot.model_id, loc, frag.root, _path(frag))]

    def hide_when(self, frag: Fragment, condition: Expression, horizontal: bool) -> str:
        """{#hidden}: la raíz del fragmento se oculta mientras `condition` sea verdadera.
        Devuelve el id del binding que la muestra.

        Con transiciones, un FxTransition en modo `toggle` anima al mostrar y al ocultar, y
        es quien cambia `visible` (al terminar la salida)."""
        root = frag.root
        if "visible" in root.props or any(prop == "visible" for prop, _, _ in root.conditional):
            box = IRElement("FxRow" if horizontal else "FxColumn", root.loc)
            box.children = [root]
            box.props.update({k: Literal(v) for k, v in _TRANSPARENT_BOX.items()})
            own = "row" if horizontal else "column"
            box.props["direction"] = Literal(f'parent && parent.fxBox ? parent.fxBox.direction : "{own}"')
            box.transitions, root.transitions = root.transitions, {}
            self.pending_transitions.pop(id(root), None)
            frag.root = root = box
        saved, self.tpl = self.tpl, frag.template
        try:
            bid = self.add_expr_binding(Expression(f"not ({condition.code.strip()})", condition.loc), condition.loc)
        finally:
            self.tpl = saved
        if root.transitions:
            self.attach_transitions(frag)
            anim = root.children[-1]
            anim.props["toggle"] = Literal("true")
            anim.props["shown"] = Bound(bid)
            frag.leave_ms = 0  # ocultarse no retira la fila
        else:
            root.props["visible"] = Bound(bid)
        return bid

    # -- slots ---------------------------------------------------------------
    def slot_outlet(self, el: Element, horizontal: bool) -> list[IRNode]:
        """`<Slot />` o `<Slot name="x">reserva</Slot>` en la plantilla de un componente."""
        name = "default"
        for attr in el.attributes:
            if attr.name == "name" and isinstance(attr.value, str) and attr.value.isidentifier():
                name = attr.value
            else:
                self.error('<Slot> solo admite name="nombre" (un identificador literal)', attr.loc)
        fallback = self.fragment(el.children, horizontal, (), el.loc)
        slot = SlotOutlet(name, self.next_id("m"), None if fallback.empty else fallback, el.loc)
        out: list[IRNode] = [IRRepeater(slot.model_id, el.loc, opaque=True)]
        if slot.fallback is not None:
            slot.fallback_model_id = self.next_id("m")
            out.append(IRRepeater(slot.fallback_model_id, el.loc, fallback.root, _path(fallback)))
        self.tpl.slots.append(slot)
        return out

    def slot_contents(self, el: Element, iface: ComponentInterface) -> dict[str, Fragment]:
        """Contenido entre las etiquetas de un componente: por defecto, o `slot="x"` en un elemento."""
        default: list[Node] = []
        named: dict[str, Element] = {}
        for child in el.children:
            attr = child.attribute("slot") if isinstance(child, Element) else None
            if attr is None:
                default.append(child)
            elif not (isinstance(attr.value, str) and attr.value.isidentifier()):
                self.error('slot="..." debe ser un nombre literal', attr.loc)
            elif attr.value in named:
                self.error(
                    f"el slot '{attr.value}' se rellena dos veces en <{el.tag}>",
                    attr.loc,
                    "agrupa el contenido en un <Column> o <Row>",
                )
            else:
                named[attr.value] = Element(child.tag, [a for a in child.attributes if a is not attr], child.children, child.loc)
        contents: dict[str, tuple[list[Node], SourceLocation]] = {}
        if any(not (isinstance(n, Text) and not n.value.strip()) for n in default):
            contents["default"] = (default, el.loc)
        for name, child in named.items():
            contents[name] = ([child], child.loc)
        slots: dict[str, Fragment] = {}
        for name, (nodes, loc) in contents.items():
            if iface.slots is not None and name not in iface.slots:
                available = ", ".join("<Slot />" if s == "default" else f'<Slot name="{s}" />' for s in sorted(iface.slots))
                what = "contenido entre etiquetas" if name == "default" else f"el slot '{name}'"
                self.error(
                    f"<{el.tag}> no admite {what}",
                    loc,
                    f"slots de <{el.tag}>: {available}" if available else f"<{el.tag}> no declara ningún <Slot />",
                )
                continue
            saved_doc = self.doc
            self.docs += 1
            self.doc = self.docs
            self.style_stack.append(self.style_node(el, None))
            try:
                frag = self.fragment(nodes, False, (), loc)
            finally:
                self.style_stack.pop()
                self.doc = saved_doc
            if frag.root is not None:
                self.slot_fragments.append(frag)
            if not frag.empty:
                slots[name] = frag
        return slots

    # -- componentes hijos ---------------------------------------------------
    def root_features(self, path: str) -> frozenset[str] | None:
        """Lo que la raíz de un componente hijo pide a su caja (layout_choice.py)."""
        return self.interface(Path(path)).root_items if self.interface else None

    def iface_of(self, el: Element) -> ComponentInterface:
        imp = self.info.components[el.tag]
        return self.interface(imp.path) if self.interface else ComponentInterface()

    def tag_attrs(self, el: Element) -> list[Attribute]:
        """Atributos de la etiqueta de un componente que no son props: van a su raíz (o a una caja exterior)."""
        iface = self.iface_of(el)
        names = _PASSED_ATTRS if iface.root_box else _WRAPPER_ATTRS
        out = []
        for a in el.attributes:
            if a.name in iface.props:
                continue
            if a.directive == "class" or (a.directive is None and a.name in names):
                out.append(a)
            elif iface.root_box and a.directive == "on" and a.argument not in iface.events and a.argument in ROUTED_EVENTS:
                out.append(a)  # on:click, on:keydown…: eventos nativos de la raíz
        return out

    def component_slot(self, el: Element) -> IRNode:
        model_id = self.next_id("m")
        use = self.component_use(el)
        self.tpl.slots.append(ComponentSlot(model_id, use, el.loc))
        repeater = IRRepeater(model_id, el.loc, component=use.path)
        attrs = self.tag_attrs(el)
        if not attrs:
            return repeater
        if self.iface_of(el).root_box:
            # La raíz es una caja: los atributos se le aplican a ella (FxRemote.qml).
            ir = self.element(Element("flex", attrs, [], el.loc), match_tag=el.tag)
            if ir is None:
                return repeater
            remote = self.remote(ir, model_id, self.last_node)
            if remote is not None:
                remote.component = use.path
                return remote
            ir.qml_type = "FxColumn"  # lo que no se puede aplicar desde fuera: caja exterior (fxFill)
            box = ir
        else:
            # Caja exterior con los estilos de la etiqueta: <Tarjeta class="ancha" flex={1} />
            box = self.element(Element("Column", attrs, [], el.loc), match_tag=el.tag)
            if box is None:
                return repeater
        box.props["fxFill"] = Literal("true")  # la raíz del componente ocupa toda la caja
        box.children.append(repeater)
        return box

    def remote(self, ir: IRElement, model_id: str, node: StyleNode | None) -> IRElement | None:
        """Los atributos de la etiqueta como Binding sobre la raíz del componente, o None si
        algo no se puede fijar desde fuera (transiciones, texto heredado, variables…)."""
        if ir.children or ir.behaviors or ir.delegate is not None or ir.transitions:
            return None
        handlers = dict(ir.handlers)
        refs = handlers.pop("Component.onCompleted", [])
        if handlers or any("fx.setRef(" not in s for s in refs):
            return None
        if any(when == "true" for _, _, when in ir.conditional):
            return None
        props = {k: (f"fx.{v.binding_id}" if isinstance(v, Bound) else v.qml) for k, v in ir.props.items()}
        rid = props.pop("id", None) or self.next_id("fxr")
        props.pop("readonly property bool fxTouchExtras", None)
        if any(k.startswith(("property ", "readonly property ")) for k in props):
            return None
        root = f"{rid}.fxRoot"

        def fix(expr: str) -> str:
            expr = _BARE.sub(lambda m: f"{rid}.{m.group(1)}", expr)
            expr = re.sub(rf"\b{rid}\b(?!\.fxRoot)", root, expr)
            return expr.replace(root + ".", root + "?.")

        remote = IRElement("FxRemote", ir.loc)
        remote.props.update({"id": Literal(rid), "model": Literal(f"fx.{model_id}"), "delegate": Literal(f"fx.{model_id}.delegate")})
        styled: dict[str, list[tuple[str, str]]] = {}
        for prop, value, when in ir.conditional:
            styled.setdefault(prop, []).append((fix(value), fix(when)))
        if node is not None and (node.classes or node.toggles or node.dynamic):
            parts = [qml_string(" " + " ".join(sorted(node.classes)) + " ")] if node.classes else []
            parts += [f'(fx.{bid} ? " {name} " : "")' for name, bid in node.toggles.items()]
            parts += [f'(fx.{node.dynamic} || "")'] if node.dynamic else []
            props["fxInClass"] = " + ".join(parts)
        for prop in dict.fromkeys([*props, *styled]):
            entries = styled.get(prop, [])
            if prop in props:
                value, when = fix(props[prop]), "true"
            else:
                (value, when), entries = entries[0], entries[1:]
            for v, w in entries:
                value = f"({w}) ? {v} : ({value})"
                when = "true" if when == "true" else f"({when}) || ({w})"
            b = IRElement("Binding", ir.loc)
            b.props.update({"target": Literal(root), "property": Literal(qml_string(prop)), "value": Literal(value)})
            if when != "true":
                b.props["when"] = Literal(f"!!({when})")  # undefined mientras no hay raíz
            remote.children.append(b)
        used = [n for n in _FLEX_ITEM_EXTRAS if n in props or n in styled]
        if used:  # el motor no ve estos cambios por sí solo (ver _flex_item_extras)
            deps = ", ".join([*(f"fxRoot.{n}" for n in used), *(["Fx.positionDeps(fxRoot)"] if "fxPosition" in used else [])])
            remote.props["readonly property bool fxTouchExtras"] = Literal(f"fxRoot ? Fx.touch(fxRoot.parent, fxRoot, {deps}) : false")
        if refs:
            calls = "; ".join(s.replace(", this,", ", fxRoot,") for s in refs)
            remote.handlers["onFxRootChanged"] = [f"if (fxRoot) {{ {calls} }}"]
        return remote

    def component_use(self, el: Element) -> ComponentUse:
        imp = self.info.components[el.tag]
        iface = self.interface(imp.path) if self.interface else ComponentInterface()
        props: dict[str, PropArg] = {}
        events: dict[str, Handler] = {}
        wrapper = self.tag_attrs(el)
        for attr in el.attributes:
            if any(attr is w for w in wrapper):
                continue
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
            elif attr.name not in iface.props:
                available = ", ".join(iface.props) or "ninguna"
                close = difflib.get_close_matches(attr.name, list(iface.props), n=1)
                self.error(
                    f"<{el.tag}> no declara la prop '{attr.name}'",
                    attr.loc,
                    (f"¿quisiste decir '{close[0]}'? " if close else "") + f"props disponibles: {available}",
                )
            else:
                props[attr.name] = arg = self.prop_arg(attr)
                decl = iface.props[attr.name]
                if isinstance(arg, ConstArg) and decl.type_names is not None and not _const_matches(arg.value, decl.type_names):
                    self.error(
                        f"la prop '{attr.name}' de <{el.tag}> espera {decl.annotation} y recibe "
                        f"{type(arg.value).__name__} ({arg.value!r})",
                        attr.loc,
                        f"en {Path(imp.path).name}: {attr.name}: {decl.annotation} = prop(...)",
                    )
        missing = [p.name for p in iface.props.values() if p.required and p.name not in props]
        if missing:
            self.error(
                f"falta{'n' if len(missing) > 1 else ''} la{'s' if len(missing) > 1 else ''} prop"
                f"{'s' if len(missing) > 1 else ''} obligatoria{'s' if len(missing) > 1 else ''} "
                f"{', '.join(repr(m) for m in missing)} en <{el.tag}>",
                el.loc,
                " ".join(f"{m}={{...}}" for m in missing),
            )
        slots = self.slot_contents(el, iface)
        key = str(imp.path)
        if key not in self.component_paths:
            self.component_paths.append(key)
        ordinal = self.use_counts.get(el.tag, 0)
        self.use_counts[el.tag] = ordinal + 1
        return ComponentUse(el.tag, key, props, events, el.loc, slots, ordinal)

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


_BOXES = BOX_TYPES
_TRANSITIONS = ("fade", "scale", "slide")
_TRANSITION_MS = 200


def _fill_parent(item: IRElement) -> None:
    """Raíz del contenido de la ventana: la ocupa entera, así que su tamaño viene de fuera."""
    item.props["anchors.fill"] = Literal("parent")
    # Idiomas de derecha a izquierda (árabe, hebreo…): todo el contenido se refleja.
    item.props["LayoutMirroring.enabled"] = Literal("fxi18n.rtl === true")
    item.props["LayoutMirroring.childrenInherit"] = Literal("true")
    if item.qml_type in _BOXES:
        item.props["fxSizedW"] = Literal("true")
        item.props["fxSizedH"] = Literal("true")


def _custom_flex(ir: IRElement) -> None:
    """flex en un elemento .qml propio: no tiene `fxFlex`, así que se declara y se le dan
    las mismas reglas de disposición que a los controles de FluxUI (fx.js)."""
    ir.props["property int fxFlex"] = ir.props.pop("fxFlex")
    ir.props.setdefault("Layout.fillWidth", Literal("Fx.fillWidth(parent, fxFlex, false, false)"))
    ir.props.setdefault("Layout.fillHeight", Literal("Fx.fillHeight(parent, fxFlex, false)"))


# style={{...}}: propiedad CSS -> [(propiedad QML, expresión con {} = el valor de Python)].
_INLINE = {
    "background": [("fxBackground", "Fx.cssColor({})")],
    "background-color": [("fxBackground", "Fx.cssColor({})")],
    "color": [("fxColor", "Fx.cssColor({})")],
    "border-color": [("fxBorderColor", "Fx.cssColor({})")],
    "border-width": [("fxBorderWidth", "Fx.cssPx({}, 0)")],
    "border-radius": [("fxRadius", "Fx.cssPx({}, 0)")],
    "opacity": [("opacity", "Fx.cssPx({}, 1)")],
    "gap": [("gap", "Fx.cssPx({}, 0)")],
    "padding": [("padding", "Fx.cssPx({}, 0)")],
    "font-size": [("font.pixelSize", "Fx.cssPx({}, 14)")],
    "top": [("fxTop", "{}")],
    "right": [("fxRight", "{}")],
    "bottom": [("fxBottom", "{}")],
    "left": [("fxLeft", "{}")],
    "z-index": [("z", "Fx.cssPx({}, 0)")],
    "width": [("Layout.preferredWidth", "Fx.cssPx({}, -1)"), ("fxWidthPct", "Fx.cssPct({})"), ("Layout.fillWidth", "false")],
    "height": [("Layout.preferredHeight", "Fx.cssPx({}, -1)"), ("fxHeightPct", "Fx.cssPct({})"), ("Layout.fillHeight", "false")],
}  # fmt: skip


def _inline_vars(nodes: list[Node]) -> set[str]:
    """Variables propias definidas en atributos style= de la plantilla."""
    out: set[str] = set()
    for node in nodes:
        children: list[Node] = []
        if isinstance(node, Element):
            attr = node.attribute("style")
            if attr is not None:
                text = attr.value if isinstance(attr.value, str) else attr.value.code
                out |= {token_key(m) for m in re.findall(r"--([A-Za-z][\w-]*)", text)}
            children = node.children
        elif isinstance(node, IfBlock):
            children = [c for b in node.branches for c in b.children]
        elif isinstance(node, EachBlock):
            children = node.children + (node.else_children or [])
        elif isinstance(node, KeyBlock):
            children = node.children + (node.else_children or [])
        out |= _inline_vars(children)
    return out


def _context_extras(ir: IRElement, cascade: Cascade) -> None:
    """Texto heredado y variables propias: lo que declara cada elemento (fase 4 de docs/flex.md)."""
    keys = {*ir.props, *ir.behaviors, *(c[0] for c in ir.conditional)}
    own = sorted(k for k in keys if k.startswith((TEXT_PREFIX, VAR_PREFIX)))
    if own and ir.qml_type in _BOXES:
        for name in own:
            ir.props[f"property var {name}"] = ir.props.pop(name, Literal("undefined"))
        i = cascade.ensure_id(ir)
        ctx = IRElement("FxContext", ir.loc)
        names = [n[len(VAR_PREFIX):] for n in own if n.startswith(VAR_PREFIX)]
        ctx.props.update({"id": Literal(f"{i}_ctx"), "box": Literal(i), "names": Literal(json.dumps(names))})
        ir.children.insert(0, ctx)
        ir.props["fxOwnCtx"] = Literal(f"{i}_ctx")
    if ir.qml_type == "FxText":
        fixed = sorted({INHERITED[k] for k in keys if k in INHERITED} | ({"capitalization"} if "font.capitalization" in keys else set()))
        if fixed:
            ir.props["fxOwn"] = Literal(qml_string(" " + " ".join(fixed) + " "))
    uses_vars = any("Fx.cssVar(" in v.qml for v in ir.props.values() if isinstance(v, Literal)) or any(
        "Fx.cssVar(" in c[1] for c in ir.conditional
    )
    if uses_vars and ir.qml_type not in (*_BOXES, "FxText"):
        ir.props["readonly property QtObject fxCtx"] = Literal(f"Fx.ctxOf({cascade.ensure_id(ir)})")


def _accessible_states(ir: IRElement, cascade: Cascade) -> None:
    """Estados de una caja para los lectores de pantalla, solo donde se usan."""
    if ir.qml_type not in _BOXES:
        return
    if any(k.startswith("Accessible.") for k in [*ir.props, *(c[0] for c in ir.conditional)]):
        # label o title en una caja sin papel: no se anuncia (con papel, FxRole.qml la anuncia).
        ir.props.setdefault("Accessible.ignored", Literal(f'{cascade.ensure_id(ir)}.fxAs === "box"'))
    role = ir.props.get("fxRole")
    role = role.qml.strip('"') if isinstance(role, Literal) else ""
    if role in ("checkbox", "switch"):
        ir.props["Accessible.checkable"] = Literal("true")
        ir.props["Accessible.checked"] = Literal("checked")
    if "selected" in ir.props or role in ("tab", "menuitem", "option", "listitem"):
        ir.props["Accessible.selected"] = Literal("selected")
    if "fxTabIndex" in ir.props or role:
        ir.props["Accessible.focusable"] = Literal("activeFocusOnTab")


def _routes(ir: IRElement) -> dict[str, str]:
    current = ir.props.get("fxOn")
    if current is None:
        return {}
    return dict(re.findall(r'"(\w+)": "(\w+)"', current.qml))


def _has_text(nodes: list[Node]) -> bool:
    """¿Hay texto (o una interpolación, o un slot) en el contenido?"""
    for node in nodes:
        if isinstance(node, Text) and node.value.strip():
            return True
        if isinstance(node, Interpolation):
            return True
        if isinstance(node, Element):
            if node.tag == "Slot" or node.attribute("text") is not None or node.attribute("label") is not None:
                return True
            if _has_text(node.children):
                return True
        elif isinstance(node, (IfBlock, EachBlock, KeyBlock)):
            return True  # contenido dinámico: no se sabe
    return False


def _style_extras(ir: IRElement, cascade: Cascade) -> None:
    """`cursor` y `translate()` en elementos que no son cajas: declara lo que necesitan."""
    if ir.qml_type in _BOXES:
        return

    def used(name: str) -> bool:
        return name in ir.props or name in ir.behaviors or any(c[0] == name for c in ir.conditional)

    if used("fxCursor"):
        ir.props["property int fxCursor"] = ir.props.pop("fxCursor", Literal("Qt.ArrowCursor"))
        hid = cascade.handler(ir, "HoverHandler")
        handler = next(c for c in ir.children if isinstance(c, IRElement) and c.props.get("id") == Literal(hid))
        handler.props["cursorShape"] = Literal(f"{cascade.ensure_id(ir)}.fxCursor")
    if used("fxTx") or used("fxTy"):
        for name in ("fxTx", "fxTy"):
            ir.props[f"property real {name}"] = ir.props.pop(name, Literal("0"))
        i = cascade.ensure_id(ir)
        ir.props["transform"] = Literal(f"Translate {{ x: {i}.fxTx; y: {i}.fxTy }}")


def _flex_item_extras(ir: IRElement, custom: bool, new_id: Callable[[], str]) -> None:
    """Declara en el elemento las propiedades de hijo de <flex> que usa (order, flex-shrink,
    flex-basis, %, margin: auto) y avisa a su contenedor cuando cambian."""
    used = [n for n in _FLEX_ITEM_EXTRAS if n in ir.props or any(c[0] == n for c in ir.conditional)]
    for name in used if ir.qml_type not in _BOXES else ():  # las cajas ya las declaran (FxFlex.qml)
        kind, default = _FLEX_ITEM_EXTRAS[name]
        value = ir.props.pop(name, Literal(default))
        ir.props[f"property {kind} {name}"] = value
    deps = list(used)
    if custom:
        # Un elemento .qml propio no trae el binding fxTouch de los controles de FluxUI.
        deps = [*_TOUCH_DEPS, *(["fxFlex"] if "property int fxFlex" in ir.props else []), *deps]
    if deps:
        name = "fxTouch" if custom else "fxTouchExtras"
        # El motor necesita el propio elemento (para olvidar lo que guardó de él): con un id.
        if "id" not in ir.props:
            ir.props["id"] = Literal(new_id())
        item = ir.props["id"].qml
        if "fxPosition" in used:  # absolute/fixed: se recoloca si su bloque contenedor cambia
            deps.append(f"Fx.positionDeps({item})")
        ir.props[f"readonly property bool {name}"] = Literal(f"Fx.touch(parent, {item}, {', '.join(deps)})")
    if custom:
        ir.props["property var fxHints"] = Literal("null")
        ir.handlers.setdefault("onImplicitWidthChanged", []).append("Fx.resized(parent)")
        ir.handlers.setdefault("onImplicitHeightChanged", []).append("Fx.resized(parent)")


def _const_matches(value: object, names: frozenset[str]) -> bool:
    """¿Un literal pasado como prop encaja con los tipos básicos de su anotación?"""
    kind = "None" if value is None else type(value).__name__
    if kind in names:
        return True
    if kind == "bool" and "int" in names:
        return True  # bool es un int en Python
    return kind == "int" and "float" in names


def _parse_path(code: str) -> list[str] | None:
    """`nombre` o `a.b.nombre` (solo nombres y atributos): sus partes; si no, None."""
    try:
        node = ast.parse(code.strip(), mode="eval").body
    except SyntaxError:
        return None
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return [node.id, *reversed(parts)]


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


def _path(frag: Fragment) -> str | None:
    """Ruta del componente que es la raíz del fragmento, si lo es."""
    return frag.component.path if frag.component is not None else None
