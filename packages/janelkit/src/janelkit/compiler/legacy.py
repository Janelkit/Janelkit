"""Nombres de JanelKit 0.1 que la 0.2 aún acepta, con un aviso. Se quitan en 0.3.

Desde 0.2 los elementos del núcleo se escriben en minúscula (`<text>`, `<button>`,
`<column>`…): la mayúscula queda para los componentes importados. Una etiqueta o un
selector de tipo con el nombre antiguo, si el script no importa un componente con ese
nombre, compila como el nuevo y avisa. `janel migrate` actualiza el proyecto con las
mismas reglas (`css_tag_spans`).

Cada nombre nuevo mide lo mismo que el antiguo, así que cambiarlo en el texto del
`<style>` no mueve ninguna posición.
"""
from __future__ import annotations

import re
from typing import Container, Iterator

from ..diagnostics import Diagnostic, SourceLocation
from .ast_nodes import SFC, EachBlock, Element, IfBlock, KeyBlock, Node

LEGACY_TAGS: dict[str, str] = {
    name: name.lower()
    for name in (
        "Window", "Column", "Row", "Scroll", "List", "Text", "Button", "TextField", "TextArea",
        "Checkbox", "Switch", "Slider", "Select", "RadioGroup", "Tabs", "Image", "Video",
        "ProgressBar", "Shortcut", "Spacer", "Slot",
    )
}  # fmt: skip

HINT = (
    "desde JanelKit 0.2 los elementos del núcleo se escriben en minúscula (la mayúscula es para "
    "componentes importados); `janel migrate` actualiza el proyecto. El nombre antiguo deja de valer en 0.3"
)

_WORD = re.compile(r"[A-Za-z_][\w-]*")


def normalize(sfc: SFC, components: Container[str]) -> list[Diagnostic]:
    """Cambia en el sitio los nombres antiguos por los nuevos y devuelve un aviso por cada uno."""
    notices: list[Diagnostic] = []
    for el in _elements(sfc.template):
        new = LEGACY_TAGS.get(el.tag)
        if new is not None and el.tag not in components:
            notices.append(Diagnostic(f"<{el.tag}> ahora se escribe <{new}>", el.loc, HINT, "warning", sfc.source))
            el.tag = new
    if sfc.style is not None:
        css = sfc.style.content
        spans = [(i, word) for i, word in css_tag_spans(css) if word not in components]
        for i, word in spans:
            loc = _offset_location(sfc.style.loc, css, i)
            notices.append(
                Diagnostic(f"el selector '{word}' ahora es '{word.lower()}'", loc, HINT, "warning", sfc.source)
            )
        if spans:
            sfc.style.content = replace_spans(css, spans)
    return notices


def css_tag_spans(css: str) -> Iterator[tuple[int, str]]:
    """Posición y nombre de cada nombre antiguo usado como selector de tipo (`Text.titulo {`)."""
    i, depth, n = 0, 0, len(css)
    while i < n:
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        c = css[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and (m := _WORD.match(css, i)) is not None:
            before = css[i - 1] if i else " "
            if m.group() in LEGACY_TAGS and before not in ".:#-\\" and not before.isalnum():
                yield i, m.group()
            i = m.end()
            continue
        i += 1


def replace_spans(text: str, spans: list[tuple[int, str]]) -> str:
    out, last = [], 0
    for i, word in spans:
        out += [text[last:i], LEGACY_TAGS[word]]
        last = i + len(word)
    out.append(text[last:])
    return "".join(out)


def _elements(nodes: list[Node]) -> Iterator[Element]:
    for node in nodes:
        if isinstance(node, Element):
            yield node
            yield from _elements(node.children)
        elif isinstance(node, IfBlock):
            for branch in node.branches:
                yield from _elements(branch.children)
        elif isinstance(node, (EachBlock, KeyBlock)):
            yield from _elements(node.children)
            yield from _elements(node.else_children or [])


def _offset_location(start: SourceLocation, text: str, offset: int) -> SourceLocation:
    before = text[:offset]
    newlines = before.count("\n")
    if not newlines:
        return SourceLocation(start.file, start.line, start.column + offset)
    return SourceLocation(start.file, start.line + newlines, offset - before.rfind("\n"))
