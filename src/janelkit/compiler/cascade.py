"""La cascada de `<style>`: qué reglas aplican a cada elemento y bajo qué condición.

Todo se resuelve al compilar, porque los estilos tienen ámbito y la plantilla se
conoce entera. Lo que depende del estado (pseudo-clases, `class:x={...}`,
`class={...}`) se convierte en una condición QML que la vista evalúa sola:
pasar el ratón por encima no llama a Python.

Precedencia (docs/estilos.md), como en CSS: gana la regla más específica (más
clases y pseudo-clases; después, más elementos) y, a igualdad, la última del
archivo. Por encima de todas, las que dependen de una clase condicional o dinámica
del propio elemento (`class:x`, `class={...}`), como antes de los selectores
compuestos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from ..styling.parser import Compound, Declaration, Rule, Selector
from .ir import IRElement, Literal

ALWAYS = "true"
_BOXES = ("JkColumn", "JkRow", "JkFlex", "JkFlexColumn", "JkFlexRow", "JkQtBox")


@dataclass
class StyleNode:
    """Un elemento de la plantilla tal como lo ven los selectores."""

    tag: str  # etiqueta escrita (en la caja exterior de un componente, la del componente)
    classes: frozenset[str] = frozenset()  # class="a b"
    toggles: dict[str, str] = field(default_factory=dict)  # class:x={...} -> id del binding
    dynamic: str | None = None  # class={expr} -> id del binding (vale " a b ")
    ir: IRElement | None = None  # None: etiqueta de un componente sin caja exterior
    doc: int = 0  # documento QML: el contenido de un slot es otro y no ve los ids de fuera
    passed: bool = False  # raíz de un componente: recibe clases de su etiqueta (jkInClass)


@dataclass
class Match:
    rank: tuple[int, int, int]  # (sobre las demás, clases y pseudo-clases, elementos)
    order: int
    cond: str  # ALWAYS o una expresión QML
    decls: list[Declaration]
    quiet: bool  # class={expr}: no se sabe qué clases dará; sin avisos de propiedades que no aplican


def and_(conds: list[str]) -> str:
    conds = [c for c in dict.fromkeys(conds) if c != ALWAYS]
    if not conds:
        return ALWAYS
    return " && ".join(f"({c})" if "||" in c else c for c in conds)


def or_(conds: list[str]) -> str:
    conds = list(dict.fromkeys(conds))
    if ALWAYS in conds:
        return ALWAYS
    return conds[0] if len(conds) == 1 else " || ".join(f"({c})" if " " in c else c for c in conds)


def _prop_name(cls: str) -> str:
    return "jkc_" + re.sub(r"\W", "_", cls)


class Cascade:
    def __init__(self, rules: list[Rule], new_id: Callable[[], str], warn: Callable[[str, Rule], None]):
        self.rules = rules
        self.new_id = new_id
        self.warn = warn
        self._warned: set[str] = set()

    # -- reglas que aplican --------------------------------------------------
    def matches(self, chain: list[StyleNode]) -> list[Match]:
        """Reglas que aplican al último nodo de `chain` (los anteriores son sus antecesores)."""
        node = chain[-1]
        out: list[Match] = []
        for order, rule in enumerate(self.rules):
            conds: list[str] = []
            rank = (-1, -1, -1)
            quiet = True
            for sel in rule.parsed:
                if self._match(sel, chain, len(sel.parts) - 1, len(chain) - 1, build=False, rule=rule) is None:
                    continue
                conds.append(self._match(sel, chain, len(sel.parts) - 1, len(chain) - 1, build=True, rule=rule))
                rank = max(rank, self._rank(sel, node))
                quiet = quiet and (node.dynamic is not None or node.passed) and any(
                    c not in node.classes and c not in node.toggles for c in sel.subject.classes
                )
            if conds:
                out.append(Match(rank, order, or_(conds), rule.declarations, quiet))
        out.sort(key=lambda m: (m.rank, m.order))
        return out

    @staticmethod
    def _rank(sel: Selector, node: StyleNode) -> tuple[int, int, int]:
        # Depende de class:x o class={...} del propio elemento: gana a las demás reglas.
        toggled = int(any(c not in node.classes for c in sel.subject.classes))
        return (toggled, *sel.specificity)

    def _match(self, sel: Selector, chain: list[StyleNode], i: int, j: int, build: bool, rule: Rule) -> str | None:
        """Condición para que la parte `i` del selector (y las anteriores) case con chain[j]."""
        here = self._compound(sel.parts[i], chain[j], chain[-1], build, sel, rule)
        if here is None:
            return None
        if i == 0:
            return here
        if sel.combinators[i - 1] == ">":
            if j == 0:
                return None
            up = self._match(sel, chain, i - 1, j - 1, build, rule)
            return None if up is None else and_([here, up])
        alts = []
        for k in range(j - 1, -1, -1):
            # Primero se comprueba sin efectos (handlers, ids) y solo se construye lo que casa.
            if self._match(sel, chain, i - 1, k, False, rule) is not None:
                alts.append(self._match(sel, chain, i - 1, k, build, rule))
        return or_(alts) if alts else None

    def _compound(
        self, comp: Compound, node: StyleNode, subject: StyleNode, build: bool, sel: Selector, rule: Rule
    ) -> str | None:
        if comp.tag is not None and comp.tag != node.tag:
            return None
        is_self = node is subject
        needs: list[tuple[str, str]] = []  # (tipo, nombre): lo que se decide en la vista
        for cls in comp.classes:
            if cls in node.classes:
                continue
            if cls in node.toggles:
                needs.append(("toggle", cls))
            elif node.dynamic is not None:
                needs.append(("dynamic", cls))
            elif node.passed and (comp.tag == node.tag or any(c in node.classes for c in comp.classes)):
                # .boton.primary en la raíz de Boton: la activa <Boton class="primary">.
                needs.append(("passed", cls))
            else:
                return None
        needs.extend(("pseudo", p) for p in comp.pseudos)
        if not needs:
            return ALWAYS
        if node.ir is None or (not is_self and node.doc != subject.doc):
            if not build and sel.text not in self._warned:
                self._warned.add(sel.text)
                where = "la etiqueta de un componente" if node.ir is None else "un elemento fuera del slot"
                self.warn(
                    f"'{sel.text}': el estado o la clase condicional de {where} no se puede usar aquí; la regla se ignora",
                    rule,
                )
            return None
        if not build:
            return "?"
        return and_([self._condition(kind, name, node, is_self) for kind, name in needs])

    # -- condiciones en la vista ---------------------------------------------
    def _condition(self, kind: str, name: str, node: StyleNode, is_self: bool) -> str:
        ir = node.ir
        assert ir is not None
        if kind == "toggle":
            bid = node.toggles[name]
            if is_self:
                return f"!!jk.{bid}"
            prop = _prop_name(name)
            ir.props.setdefault(f"readonly property bool {prop}", Literal(f"!!jk.{bid}"))
            return f"{self.ensure_id(ir)}.{prop}"
        passed = f'{self.ensure_id(ir)}.jkInClass.indexOf(" {name} ") >= 0' if node.passed else None
        if kind == "passed":
            return passed
        if kind == "dynamic":
            if is_self:
                cond = f'(jk.{node.dynamic} || "").indexOf(" {name} ") >= 0'
            else:
                ir.props.setdefault("readonly property string jkClasses", Literal(f'jk.{node.dynamic} || ""'))
                cond = f'{self.ensure_id(ir)}.jkClasses.indexOf(" {name} ") >= 0'
            return or_([cond, passed]) if passed else cond
        return self.pseudo(ir, name)

    def ensure_id(self, ir: IRElement) -> str:
        if "id" not in ir.props:
            ir.props["id"] = Literal(self.new_id())
        return ir.props["id"].qml

    def handler(self, ir: IRElement, kind: str) -> str:
        """Un HoverHandler o TapHandler hijo del elemento (uno de cada como mucho)."""
        hid = f"{self.ensure_id(ir)}_{'hov' if kind == 'HoverHandler' else 'tap'}"
        if not any(c.props.get("id") == Literal(hid) for c in ir.children if isinstance(c, IRElement)):
            h = IRElement(kind, ir.loc)
            h.props["id"] = Literal(hid)
            ir.children.append(h)
        return hid

    def pseudo(self, ir: IRElement, name: str) -> str:
        i = self.ensure_id(ir)
        box = ir.qml_type in _BOXES
        if name == "hover":
            if box:
                ir.props["jkTrackHover"] = Literal("true")
                return f"{i}.hovered"
            return f"{self.handler(ir, 'HoverHandler')}.hovered"
        if name == "pressed":
            if box:
                ir.props["jkTrackPress"] = Literal("true")
                return f"{i}.jkPressed"
            return f"{self.handler(ir, 'TapHandler')}.pressed"
        if name == "focus":
            return f"{i}.activeFocus"
        if name == "focus-visible":
            # Las cajas solo toman el foco con el teclado; los controles dicen cómo lo tomaron.
            return f"{i}.activeFocus" if box else f"({i}.activeFocus && {i}.focusReason !== Qt.MouseFocusReason)"
        if name == "focus-within":
            return f"Jk.within({i}, {i}.Window.activeFocusItem)"
        if name == "disabled":
            return f"!{i}.enabled"
        if name == "dragging":  # los pone qt_backend/events.py al arrastrar
            return f"{i}.jkDragging"
        if name == "drag-over":
            return f"{i}.jkDragOver"
        if name in ("checked", "selected", "expanded"):
            return f"{i}.{name} === true"
        # :first-child / :last-child: los marca el motor de <flex> (flex.js).
        ir.props.setdefault("property bool jkFirst", Literal("false"))
        ir.props.setdefault("property bool jkLast", Literal("false"))
        return f"{i}.jkFirst" if name == "first-child" else f"{i}.jkLast"
