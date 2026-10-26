"""Traduce declaraciones CSS-like a propiedades de los controles Qt Quick de FluxUI.

Qt Quick no es un navegador: solo se admite lo que figura en `SUPPORTED`.
Cualquier otra propiedad, o una propiedad que no aplica al elemento, genera
una advertencia con su ubicación. Los valores pueden ser tokens del tema:
`color: var(--text-muted)` se enlaza a `fxtheme.text_muted` y cambia con el tema.
"""
from __future__ import annotations

import re
from typing import Callable

from ..compiler.ir import TokenUse, qml_string
from ..diagnostics import Diagnostic
from ..qt_backend.controls import CONTROLS
from .parser import Declaration, Rule

THEME_OBJECT = "fxtheme"  # propiedad de contexto QML con los tokens del tema activo

BOXES = {"Column", "Row", "Scroll"}
TEXTUAL = {"Text", "Button", "TextField", "TextArea", "Checkbox"}
FIELDS = {"Button", "TextField", "TextArea"}
ITEMS = set(CONTROLS) - {"Window"}
ALL = set(CONTROLS)

_NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")
_VAR_RE = re.compile(r"^var\(\s*--([A-Za-z][\w-]*)\s*\)$")
_WEIGHTS = {"normal": 400, "bold": 700, "lighter": 300, "bolder": 800}
_SIDES = ("top", "right", "bottom", "left")


class StyleValueError(ValueError):
    pass


def token_key(css_name: str) -> str:
    """`text-muted` -> `text_muted` (nombre de la propiedad QML del token)."""
    return css_name.replace("-", "_")


class _Context:
    """Estado de la compilación de una declaración: tokens usados y elemento destino."""

    def __init__(self, tag: str, decl: Declaration, tokens: list[TokenUse]):
        self.tag = tag
        self.decl = decl
        self.tokens = tokens

    def token(self, value: str) -> str | None:
        m = _VAR_RE.match(value.strip())
        if not m:
            return None
        key = token_key(m.group(1))
        self.tokens.append(TokenUse(key, self.decl.loc))
        return f"{THEME_OBJECT}.{key}"

    def number(self, value: str) -> str:
        if (tok := self.token(value)) is not None:
            return tok
        m = _NUM_RE.match(value.strip())
        if not m:
            raise StyleValueError(f"se esperaba un número en px o var(--token), se recibió {value!r}")
        return m.group(1)

    def color(self, value: str) -> str:
        if (tok := self.token(value)) is not None:
            return tok
        v = value.strip()
        m = re.match(r"^rgba?\(([^)]*)\)$", v)
        if m:
            parts = [p.strip() for p in m.group(1).split(",")]
            if len(parts) not in (3, 4):
                raise StyleValueError(f"color no válido: {value!r}")
            try:
                r, g, b = (float(p) / 255 for p in parts[:3])
                a = float(parts[3]) if len(parts) == 4 else 1.0
            except ValueError:
                raise StyleValueError(f"color no válido: {value!r}") from None
            return f"Qt.rgba({r:.4g}, {g:.4g}, {b:.4g}, {a:.4g})"
        if re.match(r"^#[0-9a-fA-F]{3,8}$", v) or re.match(r"^[a-zA-Z]+$", v):
            return qml_string(v)
        raise StyleValueError(f"color no válido: {value!r}")


Converter = Callable[[str, _Context], dict[str, str]]


def _single(qml_prop: str, kind: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        return {qml_prop: getattr(ctx, kind)(value)}

    return convert


def _padding_names(tag: str) -> tuple[str, list[str]]:
    if tag == "Scroll":
        return "innerPadding", [f"inner{s.capitalize()}Padding" for s in _SIDES]
    return "padding", [f"{s}Padding" for s in _SIDES]


def _padding(value: str, ctx: _Context) -> dict[str, str]:
    parts = value.split()
    if not 1 <= len(parts) <= 4:
        raise StyleValueError(f"padding admite de 1 a 4 valores, se recibió {value!r}")
    nums = [ctx.number(p) for p in parts]
    whole, sides = _padding_names(ctx.tag)
    if len(nums) == 1:
        return {whole: nums[0]}
    top, right, bottom, left = {2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}[len(nums)]
    return dict(zip(sides, (nums[top], nums[right], nums[bottom], nums[left])))


def _padding_side(side: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        return {_padding_names(ctx.tag)[1][_SIDES.index(side)]: ctx.number(value)}

    return convert


def _border(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if v in ("none", "0"):
        return {"fxBorderWidth": "0"}
    width = color = None
    # Separar por espacios respetando paréntesis: 1px solid rgba(0, 0, 0, .1)
    for part in re.findall(r"[^\s(]+(?:\([^)]*\))?", v):
        if part in ("solid", "none"):
            continue
        if width is None and _NUM_RE.match(part):
            width = ctx.number(part)
        elif color is None:
            color = ctx.color(part)  # var(--x) suelto se interpreta como color
        else:
            raise StyleValueError(f"border no válido: {value!r}; usa p. ej. 1px solid #ccc")
    out = {}
    if width is not None:
        out["fxBorderWidth"] = width
    if color is not None:
        out["fxBorderColor"] = color
        out.setdefault("fxBorderWidth", "1")
    return out


def _weight(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip().lower()
    if v in _WEIGHTS:
        return {"font.weight": str(_WEIGHTS[v])}
    if v.isdigit() and 1 <= int(v) <= 1000:
        return {"font.weight": v}
    raise StyleValueError(f"font-weight no válido: {value!r}")


def _family(value: str, ctx: _Context) -> dict[str, str]:
    return {"font.family": ctx.token(value) or qml_string(value.strip().strip("\"'"))}


def _italic(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip().lower()
    if v not in ("italic", "normal"):
        raise StyleValueError(f"font-style no válido: {value!r}")
    return {"font.italic": "true" if v == "italic" else "false"}


def _text_align(value: str, ctx: _Context) -> dict[str, str]:
    options = {"left": "Qt.AlignLeft", "center": "Qt.AlignHCenter", "right": "Qt.AlignRight", "justify": "Qt.AlignJustify"}
    v = value.strip().lower()
    if v not in options:
        raise StyleValueError(f"text-align no válido: {value!r}; usa left, center, right o justify")
    return {"horizontalAlignment": options[v]}


def _transform(value: str, ctx: _Context) -> dict[str, str]:
    options = {
        "none": "Font.MixedCase",
        "uppercase": "Font.AllUppercase",
        "lowercase": "Font.AllLowercase",
        "capitalize": "Font.Capitalize",
    }
    v = value.strip().lower()
    if v not in options:
        raise StyleValueError(f"text-transform no válido: {value!r}")
    return {"font.capitalization": options[v]}


def _line_height(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if not re.fullmatch(r"\d+(\.\d+)?", v):
        raise StyleValueError("line-height admite un factor sin unidades, p. ej. 1.4")
    return {"lineHeight": v}


def _keyword(value: str, allowed: dict[str, str], prop: str) -> str:
    v = value.strip().lower()
    if v in ("flex-start",):
        v = "start"
    elif v in ("flex-end",):
        v = "end"
    if v not in allowed:
        raise StyleValueError(f"{prop} no soportado: {value!r}; valores admitidos: {', '.join(allowed)}")
    return allowed[v]


def _align_items(value: str, ctx: _Context) -> dict[str, str]:
    horizontal = CONTROLS[ctx.tag].horizontal
    allowed = (
        {"start": "Qt.AlignTop", "center": "Qt.AlignVCenter", "end": "Qt.AlignBottom", "stretch": "stretch"}
        if horizontal
        else {"start": "Qt.AlignLeft", "center": "Qt.AlignHCenter", "end": "Qt.AlignRight", "stretch": "stretch"}
    )
    flag = _keyword(value, allowed, "align-items")
    if flag == "stretch":
        return {"stretch": "true", "align": "0"}
    return {"align": flag, "stretch": "false"}


def _justify(value: str, ctx: _Context) -> dict[str, str]:
    return {"justify": _keyword(value, {"start": "0", "center": "0.5", "end": "1"}, "justify-content")}


def _align_self(value: str, ctx: _Context) -> dict[str, str]:
    v = _keyword(value, {"start": "start", "center": "center", "end": "end", "stretch": "stretch", "auto": ""}, "align-self")
    if v == "stretch":
        return {"fxSelfStretch": "true"}
    return {"fxSelfAlign": qml_string(v)}


def _flex(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip().split()[0] if value.strip() else ""
    if v == "none":
        return {"fxFlex": "0"}
    if not re.fullmatch(r"\d+", v):
        raise StyleValueError(f"flex admite un número entero (p. ej. flex: 1), se recibió {value!r}")
    return {"fxFlex": v}


def _size(axis: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        v = value.strip()
        if ctx.tag == "Window":
            return {axis: ctx.number(v)}
        name = "Width" if axis == "width" else "Height"
        if v == "auto":
            return {}
        if v == "100%":
            return {f"Layout.fill{name}": "true"}
        if v.endswith("%"):
            raise StyleValueError(f"solo se admite {axis}: 100% (ocupar el espacio disponible); usa flex para repartir")
        return {f"Layout.preferred{name}": ctx.number(v), f"Layout.fill{name}": "false"}

    return convert


def _limit(kind: str, axis: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        name = "Width" if axis == "width" else "Height"
        if ctx.tag == "Window":
            return {f"{kind}imum{name}": ctx.number(value)}
        return {f"Layout.{kind}imum{name}": ctx.number(value)}

    return convert


# propiedad CSS -> (elementos donde aplica, conversor)
SUPPORTED: dict[str, tuple[set[str], Converter]] = {
    "color": (TEXTUAL, _single("fxColor", "color")),
    "background": (BOXES | FIELDS, _single("fxBackground", "color")),
    "background-color": (BOXES | FIELDS, _single("fxBackground", "color")),
    "border": (BOXES | FIELDS, _border),
    "border-color": (BOXES | FIELDS, _single("fxBorderColor", "color")),
    "border-width": (BOXES | FIELDS, _single("fxBorderWidth", "number")),
    "border-radius": (BOXES | FIELDS, _single("fxRadius", "number")),
    "padding": (BOXES | TEXTUAL, _padding),
    **{f"padding-{side}": (BOXES | TEXTUAL, _padding_side(side)) for side in _SIDES},
    "gap": (BOXES, _single("gap", "number")),
    "align-items": (BOXES, _align_items),
    "justify-content": (BOXES, _justify),
    "font-size": (TEXTUAL | {"Window"}, _single("font.pixelSize", "number")),
    "font-weight": (TEXTUAL | {"Window"}, _weight),
    "font-family": (TEXTUAL | {"Window"}, _family),
    "font-style": (TEXTUAL | {"Window"}, _italic),
    "letter-spacing": (TEXTUAL, _single("font.letterSpacing", "number")),
    "text-transform": (TEXTUAL, _transform),
    "text-align": ({"Text", "TextField", "TextArea"}, _text_align),
    "line-height": ({"Text"}, _line_height),
    "flex": (ITEMS, _flex),
    "flex-grow": (ITEMS, _flex),
    "align-self": (ITEMS, _align_self),
    "width": (ALL, _size("width")),
    "height": (ALL, _size("height")),
    "min-width": (ALL, _limit("min", "width")),
    "max-width": (ALL, _limit("max", "width")),
    "min-height": (ALL, _limit("min", "height")),
    "max-height": (ALL, _limit("max", "height")),
    "opacity": (ALL, _single("opacity", "number")),
}

# Window usa su propia propiedad de color de fondo.
_WINDOW_OVERRIDES = {"background": "color", "background-color": "color"}


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
    decls: list[Declaration],
    tag: str,
    source: str,
    warnings: list[Diagnostic],
    tokens: list[TokenUse] | None = None,
) -> dict[str, str]:
    """Propiedades QML (nombre -> expresión) para el elemento `tag`."""
    tokens = tokens if tokens is not None else []
    props: dict[str, str] = {}

    def warn(msg: str, decl: Declaration, hint: str | None = None) -> None:
        warnings.append(Diagnostic(msg, decl.loc, hint, severity="warning", source=source))

    for decl in decls:
        ctx = _Context(tag, decl, tokens)
        if tag == "Window" and decl.prop in _WINDOW_OVERRIDES:
            try:
                props[_WINDOW_OVERRIDES[decl.prop]] = ctx.color(decl.value)
            except StyleValueError as exc:
                warn(str(exc), decl)
            continue
        entry = SUPPORTED.get(decl.prop)
        if entry is None:
            warn(
                f"propiedad de estilo no soportada: '{decl.prop}'",
                decl,
                "consulta la tabla de propiedades soportadas en docs/estilos.md",
            )
            continue
        tags, convert = entry
        if tag not in tags:
            warn(f"'{decl.prop}' no tiene efecto en <{tag}>", decl)
            continue
        try:
            props.update(convert(decl.value, ctx))
        except StyleValueError as exc:
            warn(str(exc), decl)
    return props
