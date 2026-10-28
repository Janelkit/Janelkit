"""Parser del subconjunto CSS de `<style>`.

Selectores admitidos: de elemento (`Button`, `flex`), de clase (`.titulo`),
compuestos (`.boton.primary`, `flex.tarjeta`), con pseudo-clases (`.fila:hover`),
de descendiente (`.tarjeta .titulo`) y de hijo directo (`.menu > .item`), y
varios separados por comas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..diagnostics import Diagnostic, FluxError, SourceLocation

# Pseudo-clases admitidas (`:active` es otro nombre de `:pressed`).
PSEUDO_CLASSES = (
    "hover", "pressed", "focus", "focus-visible", "focus-within", "disabled",
    "checked", "selected", "expanded", "first-child", "last-child", "dragging", "drag-over",
)  # fmt: skip
_PSEUDO_ALIASES = {"active": "pressed"}

_COMPOUND_RE = re.compile(r"^([A-Za-z][\w]*)?((?:\.[A-Za-z_][\w-]*|:[a-z-]+)*)$")
_PART_RE = re.compile(r"\.[A-Za-z_][\w-]*|:[a-z-]+")


@dataclass(frozen=True)
class Compound:
    """Una parte de un selector: `flex.tarjeta:hover`."""

    tag: str | None
    classes: tuple[str, ...] = ()
    pseudos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Selector:
    """`.tarjeta:hover .acciones` = partes (.tarjeta:hover, .acciones) unidas por " "."""

    text: str
    parts: tuple[Compound, ...]
    combinators: tuple[str, ...]  # entre partes: " " (descendiente) o ">" (hijo)

    @property
    def subject(self) -> Compound:
        return self.parts[-1]

    @property
    def specificity(self) -> tuple[int, int]:
        """Como en CSS (sin ids): (clases y pseudo-clases, elementos)."""
        return (
            sum(len(p.classes) + len(p.pseudos) for p in self.parts),
            sum(1 for p in self.parts if p.tag),
        )


@dataclass
class Declaration:
    prop: str
    value: str
    loc: SourceLocation


@dataclass
class Rule:
    selectors: list[str]  # texto de cada selector (".clase", "Elemento", ".a .b:hover")
    declarations: list[Declaration]
    loc: SourceLocation
    parsed: list[Selector] = field(default_factory=list)

    def class_names(self) -> list[str]:
        return [c for s in self.parsed for p in s.parts for c in p.classes]


class SelectorError(ValueError):
    pass


def parse_selector(text: str) -> Selector:
    tokens = re.split(r"\s*(>)\s*|\s+", text.strip())
    parts: list[Compound] = []
    combinators: list[str] = []
    pending = " "
    for token in tokens:
        if token is None or token == "":
            continue
        if token == ">":
            if not parts or pending == ">":
                raise SelectorError(f"'>' sin elemento a su izquierda en {text!r}")
            pending = ">"
            continue
        m = _COMPOUND_RE.match(token)
        if not m or not token:
            raise SelectorError(f"selector no soportado: {token!r}")
        pseudos: list[str] = []
        classes: list[str] = []
        for piece in _PART_RE.findall(m.group(2) or ""):
            if piece.startswith("."):
                classes.append(piece[1:])
                continue
            name = _PSEUDO_ALIASES.get(piece[1:], piece[1:])
            if name not in PSEUDO_CLASSES:
                raise SelectorError(f"pseudo-clase no soportada: {piece!r}; disponibles: :" + ", :".join(PSEUDO_CLASSES))
            pseudos.append(name)
        if parts:
            combinators.append(pending)
        parts.append(Compound(m.group(1), tuple(classes), tuple(pseudos)))
        pending = " "
    if not parts or pending == ">":
        raise SelectorError(f"selector incompleto: {text!r}")
    return Selector(text.strip(), tuple(parts), tuple(combinators))


def parse_stylesheet(content: str, start: SourceLocation, source: str) -> list[Rule]:
    """`start` es la ubicación del primer carácter de `content` en el archivo."""
    # Eliminar comentarios conservando longitudes para no desplazar posiciones.
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), content, flags=re.DOTALL)

    def loc(offset: int) -> SourceLocation:
        line = start.line + text.count("\n", 0, offset)
        if line == start.line:
            col = start.column + offset
        else:
            col = offset - text.rfind("\n", 0, offset)
        return SourceLocation(start.file, line, col)

    def fail(msg: str, offset: int, hint: str | None = None) -> FluxError:
        return FluxError(Diagnostic(msg, loc(offset), hint, source=source))

    rules: list[Rule] = []
    pos = 0
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return rules
        brace = text.find("{", pos)
        if brace < 0:
            raise fail("regla CSS incompleta: falta '{'", pos)
        close = text.find("}", brace)
        if close < 0:
            raise fail("regla CSS sin cerrar: falta '}'", brace)
        selectors = [s.strip() for s in text[pos:brace].split(",")]
        parsed: list[Selector] = []
        for sel in selectors:
            try:
                parsed.append(parse_selector(sel))
            except SelectorError as exc:
                raise fail(
                    str(exc),
                    pos,
                    "selectores admitidos: .clase, Elemento, compuestos (.a.b), pseudo-clases (.a:hover), "
                    "descendientes (.a .b) e hijos directos (.a > .b)",
                ) from None
        decls: list[Declaration] = []
        body_start = brace + 1
        for m in re.finditer(r"[^;]+", text[body_start:close]):
            chunk = m.group(0)
            if not chunk.strip():
                continue
            offset = body_start + m.start() + (len(chunk) - len(chunk.lstrip()))
            if ":" not in chunk:
                raise fail(f"declaración CSS no válida: {chunk.strip()!r}", offset, "usa propiedad: valor;")
            prop, value = chunk.split(":", 1)
            decls.append(Declaration(prop.strip().lower(), value.strip(), loc(offset)))
        rules.append(Rule(selectors, decls, loc(pos), parsed))
        pos = close + 1
