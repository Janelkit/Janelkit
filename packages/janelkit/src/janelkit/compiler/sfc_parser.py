"""Extrae las secciones `<script>`, `<style>` y la plantilla de un archivo .janel.

Las secciones extraídas se sustituyen por espacios (conservando los saltos de
línea) para que la plantilla se analice sobre el texto original y cada nodo
mantenga su línea y columna reales.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..diagnostics import Diagnostic, JanelError, location_at
from .ast_nodes import SFC, ScriptBlock, StyleBlock
from .template_parser import parse_template

_OPEN_RE = re.compile(r"<(script|style)\b([^>]*)>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([A-Za-z_][\w:-]*)\s*=\s*"([^"]*)"')
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def parse_file(path: str | Path) -> SFC:
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise JanelError(Diagnostic(f"no se encontró el archivo {path}")) from None
    return parse_sfc(source, str(path))


def parse_sfc(source: str, file: str = "<memoria>") -> SFC:
    source = source.replace("\r\n", "\n")
    errors: list[Diagnostic] = []
    script: ScriptBlock | None = None
    style: StyleBlock | None = None
    template_text = list(source)

    comments = [(m.start(), m.end()) for m in _COMMENT_RE.finditer(source)]

    def in_comment(pos: int) -> bool:
        return any(start <= pos < end for start, end in comments)

    def err(msg: str, offset: int, hint: str | None = None) -> None:
        errors.append(Diagnostic(msg, location_at(file, source, offset), hint, source=source))

    pos = 0
    while (m := _OPEN_RE.search(source, pos)) is not None:
        if in_comment(m.start()):
            pos = m.end()
            continue
        kind = m.group(1).lower()
        close = re.compile(rf"</{kind}\s*>", re.IGNORECASE).search(source, m.end())
        if close is None:
            err(f"la sección <{kind}> no está cerrada", m.start(), f"añade </{kind}> al final de la sección")
            break
        attrs = dict(_ATTR_RE.findall(m.group(2)))
        content = source[m.end():close.start()]
        content_loc = location_at(file, source, m.end())
        if kind == "script":
            lang = attrs.get("lang", "python")
            if script is not None:
                err("solo se admite una sección <script> por componente", m.start())
            elif lang != "python":
                err(f'lenguaje de script no soportado: "{lang}"', m.start(), 'usa <script lang="python">')
            else:
                script = ScriptBlock(content, lang, content_loc)
        else:
            if style is not None:
                err("solo se admite una sección <style> por componente", m.start())
            else:
                style = StyleBlock(content, content_loc)
        for i in range(m.start(), close.end()):
            if template_text[i] != "\n":
                template_text[i] = " "
        pos = close.end()

    if errors:
        raise JanelError(errors)

    template = parse_template("".join(template_text), file, source)
    return SFC(file=file, source=source, script=script, style=style, template=template)
