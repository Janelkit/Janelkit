"""Qué cajas se pueden disponer con un layout de Qt (la vía rápida) y cuáles necesitan
el motor de <flex> (flex.js).

Column, Row y `<flex direction="column">` se generan como `JkColumn`/`JkRow`/`JkQtBox`
(un GridLayout de Qt, en C++) si la caja y sus hijos solo usan lo que ese layout hace
igual que flex.js; si no, como `JkFlexColumn`/`JkFlexRow`/`JkFlex`. Se decide al
compilar, mirando todas las propiedades que pueden llegar a tener (también las de los
estados y las clases condicionales), así que el resultado es el mismo con las dos.

Lo que obliga a usar el motor de <flex>:
- en la caja: wrap, justify-content, overflow: auto/scroll, direction (en Column/Row, o
  distinta de column en <flex>), align-items: baseline, y ser una caja implícita o la
  caja exterior de un componente;
- en los hijos: order, flex-shrink, flex-basis, márgenes auto, tamaños en %, position,
  align-self: baseline, :first-child/:last-child, contenido de un <Slot /> (no se sabe
  qué es) y componentes con atributos en su etiqueta dentro de un {#each} (al reordenar
  filas, Qt no mueve su raíz);
- más de un hijo con flex (Qt no reparte en proporción como `flex: N 1 0`), salvo que
  todos sean <Spacer>; en <flex>, cualquier hijo con flex (encoge distinto).
"""
from __future__ import annotations

from typing import Callable

from ..qt_backend.controls import CONTROLS
from ..styling.compiler import compile_declarations
from ..styling.parser import Declaration, parse_stylesheet
from .ast_nodes import SFC, Element, Expression
from .ir import IRElement, IRNode, IRRepeater, Literal

# Tipos de caja: el que pone el compilador al bajar la plantilla -> (vía rápida, motor de <flex>).
CHOICE = {"JkColumn": ("JkColumn", "JkFlexColumn"), "JkRow": ("JkRow", "JkFlexRow"), "JkFlex": ("JkQtBox", "JkFlex")}
BOX_TYPES = ("JkColumn", "JkRow", "JkFlex", "JkFlexColumn", "JkFlexRow", "JkQtBox")

# Propiedades de hijo que solo entiende flex.js -> valores que no cambian nada.
_ITEM_ONLY_FLEX = {
    "jkOrder": ("0",), "jkShrink": ("NaN",), "jkBasis": ("-2",), "jkBasisPct": ("0",),
    "jkWidthPct": ("0",), "jkHeightPct": ("0",), "jkAutoMargin": ("0",),  # margin: 4px declara jkAutoMargin: 0
    "jkPosition": ('""', '"static"'), "jkTop": ("undefined",), "jkRight": ("undefined",),
    "jkBottom": ("undefined",), "jkLeft": ("undefined",), "jkFirst": (), "jkLast": (),
}  # fmt: skip
# Elementos que crecen sin que se lo pidan (flex: 1 por defecto).
_GROW_BY_DEFAULT = ("JkScroll", "JkSpacer", "JkList", "JkPages")
# Hijos que no ocupan sitio en la caja (no son Item o son invisibles).
_NOT_ITEMS = ("JkContext", "JkTransition", "Binding", "HoverHandler", "TapHandler", "Timer")

FLEX, SPACER, COMPLEX = "flex", "spacer", "complex"

# Rasgos de la raíz de un componente hijo (ruta -> rasgos o None si no se sabe).
RootLookup = Callable[[str], "frozenset[str] | None"]


def _keys(ir: IRElement) -> dict[str, list[str]]:
    """Propiedades que puede tener el elemento -> sus valores posibles (QML)."""
    out: dict[str, list[str]] = {}
    for key, value in ir.props.items():
        name = key.split()[-1]  # "property int jkFlex" -> jkFlex
        out.setdefault(name, []).append(value.qml if isinstance(value, Literal) else "?")
    for name, value, _ in ir.conditional:
        out.setdefault(name, []).append(value)
    return out


def features_of_props(qml_type: str, keys: dict[str, list[str]]) -> frozenset[str]:
    """Rasgos de un hijo según las propiedades que puede tener."""
    out: set[str] = set()
    if any(v.strip() not in neutral for k, neutral in _ITEM_ONLY_FLEX.items() for v in keys.get(k, ())):
        out.add(COMPLEX)
    if any("baseline" in v for v in keys.get("jkSelfAlign", [])):
        out.add(COMPLEX)
    flex = keys.get("jkFlex")
    if flex is not None:
        if any(v.strip() != "0" for v in flex):
            out.add(FLEX)
    elif qml_type in _GROW_BY_DEFAULT:
        out.add(FLEX)
        if qml_type == "JkSpacer":
            out.add(SPACER)
    return frozenset(out)


def _features(node: IRNode, roots: RootLookup) -> frozenset[str] | None:
    """Rasgos de un hijo de una caja, o None si no se sabe (cuenta como COMPLEX)."""
    if isinstance(node, IRRepeater):
        if node.opaque:
            return None
        if node.delegate is not None:
            if node.many and node.delegate.qml_type == "JkRemote":
                return None
            return _features(node.delegate, roots)
        return roots(node.component) if node.component else frozenset()
    if node.qml_type in _NOT_ITEMS:
        return frozenset()
    if node.qml_type == "JkRemote":
        # Los atributos de la etiqueta van a la raíz con Binding (JkRemote.qml).
        keys: dict[str, list[str]] = {}
        for b in node.children:
            if isinstance(b, IRElement) and b.qml_type == "Binding" and "property" in b.props:
                keys.setdefault(b.props["property"].qml.strip('"'), []).append(b.props["value"].qml)
        root = roots(node.component) if node.component else None
        if root is None:
            return None
        return features_of_props("", keys) | root
    own = features_of_props(node.qml_type, _keys(node))
    if not node.qml_type.startswith("Jk"):

        own |= {FLEX}  # elemento .qml propio: puede crecer por su cuenta (Layout.fillWidth)
    return own


def why_flex(box: IRElement, roots: RootLookup) -> str | None:
    """Por qué la caja necesita el motor de <flex>, o None si basta un layout de Qt."""
    keys = _keys(box)
    legacy = box.qml_type != "JkFlex"
    if "jkFill" in keys:
        return "caja exterior de un componente"
    if "jkLegacy" in keys:
        return "caja implícita de un bloque"
    if any(v != "false" for v in keys.get("wrap", [])):
        return "wrap"
    if any(v not in ('"start"', '"flex-start"') for v in keys.get("justifyContent", [])):
        return "justify-content"
    if any("auto" in v or "scroll" in v for v in keys.get("jkOverflow", [])):
        return "overflow"
    if any("baseline" in v for v in keys.get("alignItems", [])):
        return "align-items: baseline"
    direction = keys.get("direction")
    if legacy and direction is not None:
        return "direction"
    if not legacy and (direction != ['"column"'] or any(c[0] == "direction" for c in box.conditional)):
        return "<flex> en fila"
    flex = spacers = 0
    for child in box.children:
        feats = _features(child, roots)
        if feats is None:
            return "un hijo que no se conoce al compilar (<Slot />, componente)"
        if COMPLEX in feats:
            return "un hijo con order, margin: auto, %, position, flex-shrink/basis o :first-child"
        n = 2 if isinstance(child, IRRepeater) and child.many else 1
        if FLEX in feats:
            flex += n
            if SPACER in feats:
                spacers += n
    if not legacy and flex:
        return "un hijo con flex en <flex>"
    if flex > 1 and flex != spacers:
        return "varios hijos con flex"
    return None


# False: todas las cajas con el motor de <flex> (para comparar las dos vías en las pruebas).
FAST_LAYOUTS = True


# Colocan a sus hijos con el motor de <flex>. JkScroll también (un JkFlexColumn dentro),
# pero no cuenta: su contenido suele ser una columna grande, y como layout de Qt cambia
# de ancho antes (300 tarjetas en un <Scroll>: 8,7 ms por paso; con el motor, 25).
_ENGINE = ("JkFlex", "JkFlexColumn", "JkFlexRow")


def choose_layouts(roots_ir: list[IRElement], roots: RootLookup, root_in_engine: bool = False) -> set[str]:
    """Pone a cada caja su tipo final: layout de Qt si se puede, motor de <flex> si no.

    Dentro de una caja con el motor, también el motor: el motor lee al momento el tamaño de
    sus hijos y un layout de Qt lo calcula más tarde, en su propio polish (flex.js lo
    adelanta con `settleQt`, pero cuesta más). Con la rejilla de 200 tarjetas de
    apps/examples/flex: 17 ms por fotograma con todo en el motor, 24 con las tarjetas en un
    layout de Qt (en el panel de apps/challenges, al revés: 2,9 frente a 2,4 ms). `root_in_engine`: la raíz es la de un componente que va dentro de una
    caja con el motor. Devuelve los componentes hijos que van dentro de una caja con el
    motor, para compilar su raíz igual."""
    seen: set[int] = set()
    engine_children: set[str] = set()

    def choose(node: IRNode, in_engine: bool) -> None:
        if isinstance(node, IRRepeater):
            if node.component is not None and in_engine:
                engine_children.add(node.component)
            if node.delegate is not None:
                choose(node.delegate, in_engine)
            return
        if node.component is not None and in_engine:  # JkRemote: la raíz del componente va aquí
            engine_children.add(node.component)
        if id(node) not in seen and node.qml_type in CHOICE:
            seen.add(id(node))
            fast, slow = CHOICE[node.qml_type]
            ok = FAST_LAYOUTS and not in_engine and why_flex(node, roots) is None
            node.qml_type = fast if ok else slow
        inner = node.qml_type in _ENGINE
        for child in node.children:
            choose(child, inner)
        if node.delegate is not None:
            choose(node.delegate, inner)

    for i, root in enumerate(roots_ir):
        choose(root, root_in_engine and i == 0)
        _mark_deep(root)
    return engine_children


_QT = ("JkQtBox", "JkColumn", "JkRow")


def _mark_deep(node: IRNode) -> bool:
    """Marca las cajas de Qt con cajas del motor dentro (jkDeep, ver settleQt en flex.js):
    solo en esas hace falta bajar al colocarlas desde el motor. Devuelve si `node` tiene o
    puede tener (un componente, un bloque) alguna caja del motor."""
    if isinstance(node, IRRepeater):
        if node.delegate is not None:
            _mark_deep(node.delegate)
        return True  # un bloque puede llevar su propia caja (del motor)
    deep = node.component is not None or node.qml_type in _ENGINE
    for child in node.children:
        deep = _mark_deep(child) or deep
    if node.delegate is not None:
        deep = _mark_deep(node.delegate) or deep
    if deep and node.qml_type in _QT:
        node.props["jkDeep"] = Literal("true")
    return deep


# -- raíz de un componente hijo ---------------------------------------------------
def root_features(sfc: SFC) -> frozenset[str] | None:
    """Rasgos de la raíz de un componente para la caja que lo contiene (sin compilarlo):
    lo que le pueden dar sus propias reglas de <style> y sus atributos. None si no se sabe."""
    roots = sfc.root_elements
    if len(roots) != 1 or not isinstance(roots[0], Element):
        return None
    root = roots[0]
    spec = CONTROLS.get(root.tag)
    if spec is None or root.tag in ("Window", "Slot"):
        return None  # otro componente o un elemento propio: no se sabe
    # Una raíz caja puede recibir clases de la etiqueta (<Boton class="primary"> activa
    # .boton.primary): cuentan las reglas que nombran su etiqueta o alguna de sus clases.
    passed = root.tag in ("flex", "Column", "Row")
    static: set[str] = set()
    toggles: set[str] = set()
    dynamic = False
    keys: dict[str, list[str]] = {}
    decls: list[Declaration] = []
    for attr in root.attributes:
        if attr.directive == "class":
            toggles.add(attr.argument)
        elif attr.name == "class":
            if isinstance(attr.value, str):
                static |= set(attr.value.split())
            else:
                dynamic = True
        elif attr.name == "flex" and attr.directive is None:
            keys.setdefault("jkFlex", []).append(attr.value.code if isinstance(attr.value, Expression) else str(attr.value))
        elif attr.name == "style" and attr.directive is None:
            if not isinstance(attr.value, str):
                return None  # style={{...}}: valores de Python (pueden ser %)
            for chunk in attr.value.split(";"):
                if ":" in chunk:
                    prop, value = chunk.split(":", 1)
                    decls.append(Declaration(prop.strip().lower(), value.strip(), root.loc))
    if sfc.style:
        try:
            rules = parse_stylesheet(sfc.style.content, sfc.style.loc, sfc.source)
        except Exception:
            return None
        for rule in rules:
            for sel in rule.parsed:
                if len(sel.parts) != 1:
                    continue  # necesita antecesores: la raíz no los tiene en su archivo
                comp = sel.parts[0]
                if comp.tag is not None and comp.tag != root.tag:
                    continue
                missing = [c for c in comp.classes if c not in static and c not in toggles]
                if missing and not dynamic and not (passed and (comp.tag == root.tag or len(missing) < len(comp.classes))):
                    continue
                if "first-child" in comp.pseudos or "last-child" in comp.pseudos:
                    return frozenset({COMPLEX})
                decls.extend(rule.declarations)
    try:
        props = compile_declarations(decls, root.tag, sfc.source, [])
    except Exception:
        return None
    for name, value in props.items():
        keys.setdefault(name, []).append(value)
    return features_of_props(spec.qml_type, keys)

