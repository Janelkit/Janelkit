"""Parser del subconjunto CSS de `<style>`: reglas con selectores de clase o de elemento."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..diagnostics import Diagnostic, FluxError, SourceLocation

_SELECTOR_RE = re.compile(r"^(\.[A-Za-z_][\w-]*|[A-Z][\w]*)$")


@dataclass
class Declaration:
    prop: str
    value: str
    loc: SourceLocation


@dataclass
class Rule:
    selectors: list[str]  # ".clase" o "Elemento"
    declarations: list[Declaration]
    loc: SourceLocation


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
        for sel in selectors:
            if not _SELECTOR_RE.match(sel):
                raise fail(
                    f"selector no soportado: {sel!r}",
                    pos,
                    "por ahora solo se admiten selectores de clase (.nombre) o de elemento (Button)",
                )
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
        rules.append(Rule(selectors, decls, loc(pos)))
        pos = close + 1
