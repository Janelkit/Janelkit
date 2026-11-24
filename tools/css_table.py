"""Tabla «qué CSS admite cada elemento» de docs/estilos.md, generada desde el compilador.

Lee `SUPPORTED` de `janelkit/compiler/css.py` (propiedad -> elementos donde aplica) y
escribe la tabla entre los marcadores de docs/estilos.md. Así la documentación dice lo
mismo que el compilador: añadir una propiedad o un elemento cambia la tabla, y la prueba
`tests/test_docs.py` falla hasta que se regenera.

Uso:
    python tools/css_table.py           # reescribe la tabla en docs/estilos.md
    python tools/css_table.py --check   # sale con 1 si la tabla está desactualizada
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "estilos.md"
BEGIN = "<!-- css-por-elemento: generado por tools/css_table.py, no editar a mano -->"
END = "<!-- fin css-por-elemento -->"
SIDES = ("top", "right", "bottom", "left")

sys.path.insert(0, str(REPO / "packages" / "janelkit" / "src"))
from janelkit.compiler.css import ALL, ITEMS, SUPPORTED, _WINDOW_OVERRIDES  # noqa: E402
from janelkit.compiler.elements import BASE_ELEMENTS  # noqa: E402


def _supported_by(tag: str) -> set[str]:
    props = {name for name, (tags, _) in SUPPORTED.items() if tag in tags}
    if tag == "window":
        props |= set(_WINDOW_OVERRIDES)
    return props


def _compact(names: set[str]) -> list[str]:
    """Junta los cuatro lados: `padding-top`… -> `padding-*`; `border-top-width`… -> `border-*-width`."""
    names = set(names)
    out: list[str] = []
    for base, suffix in (("padding", ""), ("margin", ""), ("border", ""), ("border", "-width"), ("border", "-color")):
        sides = {f"{base}-{side}{suffix}" for side in SIDES}
        if sides <= names:
            names -= sides
            out.append(f"{base}-*{suffix}")
    return sorted(names | set(out), key=lambda n: (n.replace("-*", ""), n))


def _cell(names: set[str]) -> str:
    return ", ".join(f"`{n}`" for n in _compact(names)) if names else "—"


def _tags(tags: set[str]) -> str:
    return ", ".join(f"`{t}`" for t in sorted(tags))


def render() -> str:
    everywhere = {name for name, (tags, _) in SUPPORTED.items() if ALL <= tags}
    items = {name for name, (tags, _) in SUPPORTED.items() if ITEMS <= tags} - everywhere
    lines = [
        BEGIN,
        "",
        f"- **Todos los elementos** (salvo {_tags(set(BASE_ELEMENTS) - ALL)}, que no se dibuja{"n" if len(set(BASE_ELEMENTS) - ALL) > 1 else ""}): {_cell(everywhere)}.",
        f"- **Todos salvo `window`:** {_cell(items)}. También los elementos propios (QML del proyecto).",
        "",
        "| Elemento | Además admite |",
        "|---|---|",
    ]
    for tag in BASE_ELEMENTS:
        extra = _cell(_supported_by(tag) - everywhere - items) if tag in ALL else "ninguna: no se dibuja"
        lines.append(f"| `{tag}` | {extra} |")
    lines += ["", END]
    return "\n".join(lines)


def updated(text: str) -> str:
    start, end = text.index(BEGIN), text.index(END) + len(END)
    return text[:start] + render() + text[end:]


def main(argv: list[str]) -> int:
    raw = DOC.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    new = updated(text)
    if "--check" in argv:
        if new != text:
            print("docs/estilos.md: la tabla de CSS por elemento está desactualizada; ejecuta python tools/css_table.py")
            return 1
        return 0
    DOC.write_bytes(new.replace("\n", newline).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
