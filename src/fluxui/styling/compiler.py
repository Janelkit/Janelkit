"""Traduce declaraciones CSS-like a propiedades de Qt Quick.

Qt Quick no es un navegador: solo se admite la tabla `SUPPORTED`. Cualquier otra
propiedad genera una advertencia con su ubicación.
"""
from __future__ import annotations

import re
from typing import Callable

from ..compiler.ir import qml_string
from ..diagnostics import Diagnostic
from .parser import Declaration, Rule

_TEXT_TYPES = {"Label", "Button", "TextField", "CheckBox"}
_PADDED_TYPES = {"Column", "Row", "Label", "Button", "TextField", "CheckBox"}
_ALL = None  # aplica a cualquier tipo

_NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")
_WEIGHTS = {"normal": 400, "bold": 700, "lighter": 300, "bolder": 800}


class StyleValueError(ValueError):
    pass


def _number(value: str) -> str:
    m = _NUM_RE.match(value.strip())
    if not m:
        raise StyleValueError(f"se esperaba un número en px, se recibió {value!r}")
    return m.group(1)


def _string(value: str) -> str:
    return qml_string(value.strip().strip("\"'"))


def _color(value: str) -> str:
    v = value.strip()
    m = re.match(r"^rgba?\(([^)]*)\)$", v)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) not in (3, 4):
            raise StyleValueError(f"color no válido: {value!r}")
        r, g, b = (float(p) / 255 for p in parts[:3])
        a = float(parts[3]) if len(parts) == 4 else 1.0
        return f"Qt.rgba({r:.4g}, {g:.4g}, {b:.4g}, {a:.4g})"
    if re.match(r"^#[0-9a-fA-F]{3,8}$", v) or re.match(r"^[a-zA-Z]+$", v):
        return qml_string(v)
    raise StyleValueError(f"color no válido: {value!r}")


def _weight(value: str) -> str:
    v = value.strip().lower()
    if v in _WEIGHTS:
        return str(_WEIGHTS[v])
    if v.isdigit() and 1 <= int(v) <= 1000:
        return v
    raise StyleValueError(f"font-weight no válido: {value!r}")


def _italic(value: str) -> str:
    v = value.strip().lower()
    if v not in ("italic", "normal"):
        raise StyleValueError(f"font-style no válido: {value!r}")
    return "true" if v == "italic" else "false"


# propiedad CSS -> (tipos QML donde aplica | None = todos, propiedad QML, conversor)
SUPPORTED: dict[str, tuple[set[str] | None, str, Callable[[str], str]]] = {
    "padding": (_PADDED_TYPES, "padding", _number),
    "gap": ({"Column", "Row"}, "spacing", _number),
    "font-size": (_TEXT_TYPES, "font.pixelSize", _number),
    "font-weight": (_TEXT_TYPES, "font.weight", _weight),
    "font-family": (_TEXT_TYPES, "font.family", _string),
    "font-style": (_TEXT_TYPES, "font.italic", _italic),
    "color": ({"Label", "TextField"}, "color", _color),
    "background": ({"ApplicationWindow"}, "color", _color),
    "background-color": ({"ApplicationWindow"}, "color", _color),
    "width": (_ALL, "width", _number),
    "height": (_ALL, "height", _number),
    "opacity": (_ALL, "opacity", _number),
}


def matching_declarations(rules: list[Rule], tag: str, classes: list[str]) -> list[Declaration]:
    """Declaraciones aplicables en orden de precedencia (las últimas ganan).

    Precedencia simple: reglas de elemento antes que reglas de clase; dentro de
    cada grupo, el orden del archivo.
    """
    by_tag = [d for r in rules if tag in r.selectors for d in r.declarations]
    class_sel = {f".{c}" for c in classes}
    by_class = [d for r in rules if class_sel & set(r.selectors) for d in r.declarations]
    return by_tag + by_class


def compile_declarations(
    decls: list[Declaration], qml_type: str, source: str, warnings: list[Diagnostic]
) -> dict[str, str]:
    props: dict[str, str] = {}
    for decl in decls:
        entry = SUPPORTED.get(decl.prop)
        if entry is None:
            warnings.append(
                Diagnostic(
                    f"propiedad de estilo no soportada: '{decl.prop}'",
                    decl.loc,
                    "consulta la tabla de propiedades soportadas en docs/estilos.md",
                    severity="warning",
                    source=source,
                )
            )
            continue
        types, qml_prop, convert = entry
        if types is not None and qml_type not in types:
            warnings.append(
                Diagnostic(
                    f"'{decl.prop}' no tiene efecto en {qml_type}",
                    decl.loc,
                    severity="warning",
                    source=source,
                )
            )
            continue
        try:
            props[qml_prop] = convert(decl.value)
        except StyleValueError as exc:
            warnings.append(Diagnostic(str(exc), decl.loc, severity="warning", source=source))
    return props
