"""La documentación que sale del código no se queda atrás."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("css_table", REPO / "tools" / "css_table.py")
css_table = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(css_table)


def test_the_css_per_element_table_matches_the_compiler():
    """docs/estilos.md lista lo que admite cada elemento tal como lo dice css.SUPPORTED.
    Si falla: python tools/css_table.py."""
    assert css_table.main(["--check"]) == 0


def test_every_supported_property_is_explained():
    """Cada propiedad de css.SUPPORTED aparece explicada en docs/estilos.md, fuera de la tabla generada.
    Los lados van agrupados: `border-top`, `-right`… explica también `border-left-color`."""
    import re

    from janelkit.compiler.css import SUPPORTED

    text = (REPO / "docs" / "estilos.md").read_text(encoding="utf-8")
    start, end = text.index(css_table.BEGIN), text.index(css_table.END)
    prose = text[:start] + text[end:]
    missing = []
    for name in SUPPORTED:
        first_side = re.sub(r"-(top|right|bottom|left)(-width|-color)?$", "-top", name)
        if f"`{name}`" not in prose and f"`{first_side}`" not in prose:
            missing.append(name)
    assert missing == []


# -- los ejemplos de la documentación compilan ------------------------------------------------

DOCS = [*sorted((REPO / "docs").glob("*.md")), REPO / "README.md", *sorted((REPO / "packages").glob("*/README.md"))]
_BLOCK = re.compile(r"^( *)```html\n(.*?)^\1```", re.S | re.M)
_SECTION = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S)
_UNDEFINED = re.compile(r"'([A-Za-z_]\w*)' no está definido")


def _examples() -> list[tuple[str, str]]:
    out = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        for m in _BLOCK.finditer(text):
            indent = len(m.group(1))
            source = "\n".join(line[indent:] for line in m.group(2).splitlines())
            out.append((f"{path.relative_to(REPO).as_posix()}:{text[:m.start()].count(chr(10)) + 1}", source))
    return out


def problems_of_example(source: str) -> list[str]:
    """Errores y avisos del compilador en un ejemplo, que suele ser un fragmento: se envuelve en
    un <column> (salvo un <window>), los nombres que da por existentes se definen como state y
    los componentes que no define se toleran. El resto (sintaxis, atributos, CSS) cuenta."""
    from janelkit.compiler import compile_source
    from janelkit.diagnostics import JanelError

    script = re.search(r"<script\b[^>]*>(.*?)</script>", source, re.S)
    styles = "".join(m.group(0) + "\n" for m in _SECTION.finditer(source) if m.group(1) == "style")
    template = _SECTION.sub("", source).strip()
    root = template if template.startswith("<window") else f"<column>\n{template}\n</column>"
    defined: list[str] = []
    while True:
        body = (script.group(1) if script else "") + "\nfrom janelkit import state\n"
        body += "".join(f"{name} = state(None)\n" for name in defined)
        try:
            compiled = compile_source(f"<script>\n{body}</script>\n{styles}{root}", "App.janel")
        except JanelError as exc:
            messages = [d.message for d in exc.diagnostics]
            missing = [m.group(1) for m in map(_UNDEFINED.search, messages) if m and m.group(1) not in defined]
            other = [m for m in messages if not _UNDEFINED.search(m) and "elemento desconocido" not in m]
            if other or not missing:
                return other
            defined += missing
            continue
        return [w.message for w in compiled.warnings]


@pytest.mark.parametrize("where, source", _examples(), ids=[w for w, _ in _examples()])
def test_the_examples_in_the_docs_compile(where, source):
    assert problems_of_example(source) == []


def test_a_broken_example_is_caught():
    assert problems_of_example('<row><text class="t">{nombre}</text></row>\n<style>.t { gap: 4px }</style>')
    assert problems_of_example("<row><button on:click={guardar}>Guardar</row>")
    assert problems_of_example("{#each items as i}<Tarjeta dato={i} />{/each}") == []
