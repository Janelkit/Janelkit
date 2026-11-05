r"""Markdown sin HTML para `<Text format="markdown">`.

El Markdown de Qt (md4c, dialecto GitHub) también interpreta HTML: un mensaje de chat con
`<img src=…>` o `<span style=…>` cambiaría la interfaz. Qt no deja quitarlo desde QML,
así que JanelKit escapa cada `<` (`\<`, que Markdown muestra como `<`) antes de pasarle
el texto. Sin `<` no empieza ninguna etiqueta ni bloque HTML.

Dentro de código el `\` se vería, y el HTML ya no se interpreta: ahí no se toca.
- Bloques con valla (``` o ~~~) que empiezan en la columna 0.
- Código en línea (`` `a < b` ``) que se abre y se cierra en la misma línea.

Reconocer el código exactamente como md4c no es trivial (un `` ` `` sin cerrar se empareja
con otro de una línea siguiente, una lista corta un bloque…). Por eso, si queda algún `<`
sin escapar, md4c hace de juez: se analiza el resultado con y sin HTML y, si el texto
visible difiere, md4c encontró HTML y se escapan todos los `<`, también los del código
(allí se verá un `\`, pero nunca pasa HTML).

Los enlaces automáticos `<https://…>` se escapan también; las direcciones sueltas
(`https://…`) y `[texto](url)` siguen siendo enlaces.
"""
from __future__ import annotations

import re
from functools import lru_cache

_FENCE = re.compile(r"(`{3,}|~{3,})(.*)")
_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def safe_markdown(text: str) -> str:
    """`text` con cada `<` fuera de código escapado: md4c no verá HTML."""
    if "<" not in text:
        return text
    return _safe(text)


@lru_cache(maxsize=2048)  # una lista vuelve a mostrar los mismos mensajes al desplazarse
def _safe(text: str) -> str:
    result, kept = _escape(text)
    if kept and _md4c_sees_html(result):
        result = _inline(text, code=False)
    return result


def _md4c_sees_html(text: str) -> bool:
    from PySide6.QtGui import QTextDocument

    features = QTextDocument.MarkdownFeature
    shown = []
    for flags in (features.MarkdownDialectGitHub, features.MarkdownDialectGitHub | features.MarkdownNoHTML):
        document = QTextDocument()
        document.setMarkdown(text, flags)
        shown.append(document.toPlainText())
    return shown[0] != shown[1]


def _escape(text: str) -> tuple[str, bool]:
    """(texto escapado, si quedó algún `<` sin escapar dentro de lo que parece código)."""
    out: list[str] = []
    fence: str | None = None  # la valla abierta («```», «~~~~»…), si hay
    kept = False
    for line in text.splitlines(keepends=True):
        if fence is not None:
            out.append(line)
            kept = kept or "<" in line
            stripped = line.strip()
            if len(line) - len(line.lstrip(" ")) <= 3 and stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            continue
        match = _FENCE.match(line)
        if match is not None and not (match[1][0] == "`" and "`" in match[2]):
            fence = match[1]
            out.append(line)
            kept = kept or "<" in line
            continue
        escaped = _inline(line)
        kept = kept or escaped.count("<") != escaped.count("\\<")
        out.append(escaped)
    return "".join(out), kept


def _inline(line: str, code: bool = True) -> str:
    """Escapa los `<` de `line`; con `code`, salvo dentro de código en línea cerrado en ella."""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n and line[i + 1] in _PUNCT:
            out.append(line[i : i + 2])  # `\<` o `\`` ya escapados: se quedan como están
            i += 2
        elif ch == "`" and code:
            run = i
            while i < n and line[i] == "`":
                i += 1
            close = _closing(line, i, i - run)
            if close is None:
                out.append(line[run:i])  # sin cierre en la línea: comillas literales; se sigue escapando
            else:
                out.append(line[run:close])
                i = close
        elif ch == "<":
            out.append("\\<")
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _closing(line: str, start: int, length: int) -> int | None:
    """Fin (exclusivo) de la primera racha de exactamente `length` comillas desde `start`."""
    i, n = start, len(line)
    while i < n:
        if line[i] != "`":
            i += 1
            continue
        run = i
        while i < n and line[i] == "`":
            i += 1
        if i - run == length:
            return i
    return None
