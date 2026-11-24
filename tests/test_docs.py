"""La documentación que sale del código no se queda atrás."""
from __future__ import annotations

import importlib.util
from pathlib import Path

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
