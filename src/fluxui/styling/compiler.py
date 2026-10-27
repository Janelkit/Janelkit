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

FLEXES = {"flex", "Column", "Row"}  # cajas con el motor de <flex> (FxFlex)
BOXES = FLEXES | {"Scroll", "List"}
TEXTUAL = {"Text", "Button", "TextField", "TextArea", "Checkbox", "Switch", "Select", "RadioGroup", "Tabs"}
FIELDS = {"Button", "TextField", "TextArea", "Select"}
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

# Clave especial que devuelven los conversores: `Behavior on <prop>` (lo coloca el compilador).
BEHAVIOR = "@behavior "

# transition: <propiedad CSS> -> (propiedad QML, animación)
_ANIMATABLE = {
    "color": ("fxColor", "ColorAnimation"),
    "background": ("fxBackground", "ColorAnimation"),
    "background-color": ("fxBackground", "ColorAnimation"),
    "border-color": ("fxBorderColor", "ColorAnimation"),
    "opacity": ("opacity", "NumberAnimation"),
    "width": ("Layout.preferredWidth", "NumberAnimation"),
    "height": ("Layout.preferredHeight", "NumberAnimation"),
    "border-radius": ("fxRadius", "NumberAnimation"),
}
_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)(ms|s)$")


def _transition(value: str, ctx: _Context) -> dict[str, str]:
    """`transition: background 200ms, opacity .3s` -> animaciones de esas propiedades."""
    out: dict[str, str] = {}
    for part in value.split(","):
        words = part.split()
        if len(words) < 2:
            raise StyleValueError(f"transition necesita propiedad y duración, p. ej. 'background 200ms': {part.strip()!r}")
        prop, duration = words[0], words[1]
        m = _DURATION_RE.match(duration if not duration.startswith(".") else "0" + duration)
        if not m:
            raise StyleValueError(f"duración no válida en transition: {duration!r} (usa 200ms o 0.2s)")
        ms = float(m.group(1)) * (1000 if m.group(2) == "s" else 1)
        props = list(_ANIMATABLE) if prop == "all" else [prop]
        for name in props:
            if name not in _ANIMATABLE:
                raise StyleValueError(
                    f"transition no puede animar {name!r}; se admiten: {', '.join(_ANIMATABLE)} y all"
                )
            qml_prop, animation = _ANIMATABLE[name]
            out[BEHAVIOR + qml_prop] = f"{animation} {{ duration: {ms:.0f}; easing.type: Easing.OutCubic }}"
    return out


def _single(qml_prop: str, kind: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        return {qml_prop: getattr(ctx, kind)(value)}

    return convert


def _padding_names(tag: str) -> tuple[str, list[str]]:
    if tag in ("Scroll", "List"):
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


def _words(*names: str) -> dict[str, str]:
    return {n: qml_string(n) for n in names}


_SPACING = ("start", "center", "end", "space-between", "space-around", "space-evenly")


def _align_items(value: str, ctx: _Context) -> dict[str, str]:
    allowed = _words("start", "center", "end", "stretch", *(("baseline",) if ctx.tag in FLEXES else ()))
    return {"alignItems": _keyword(value, allowed, "align-items")}


def _justify(value: str, ctx: _Context) -> dict[str, str]:
    return {"justifyContent": _keyword(value, _words(*_SPACING), "justify-content")}


def _align_content(value: str, ctx: _Context) -> dict[str, str]:
    return {"alignContent": _keyword(value, _words(*_SPACING, "stretch"), "align-content")}


def _direction(value: str, ctx: _Context) -> dict[str, str]:
    allowed = _words("row", "column", "row-reverse", "column-reverse")
    return {"direction": _keyword(value, allowed, "flex-direction")}


def _wrap(value: str, ctx: _Context) -> dict[str, str]:
    return {"wrap": _keyword(value, {"nowrap": "false", "wrap": "true"}, "flex-wrap")}


def _overflow(value: str, ctx: _Context) -> dict[str, str]:
    return {"fxOverflow": _keyword(value, _words("visible", "hidden", "auto", "scroll"), "overflow")}


def _align_self(value: str, ctx: _Context) -> dict[str, str]:
    v = _keyword(value, {"start": "start", "center": "center", "end": "end", "stretch": "stretch", "auto": ""}, "align-self")
    if v == "stretch":
        return {"fxSelfStretch": "true"}
    return {"fxSelfAlign": qml_string(v)}


def _grow(v: str, prop: str) -> str:
    if not re.fullmatch(r"\d+", v):
        raise StyleValueError(f"{prop} admite un número entero (p. ej. {prop}: 1), se recibió {v!r}")
    return v


def _number_text(v: str, what: str) -> str:
    if not re.fullmatch(r"\d+(\.\d+)?", v.strip()):
        raise StyleValueError(f"{what} admite un número, se recibió {v!r}")
    return v.strip()


def _percent(v: str) -> str:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%", v.strip())
    if not m:
        raise StyleValueError(f"porcentaje no válido: {v!r}")
    return m.group(1)


def _basis_value(v: str, ctx: _Context) -> dict[str, str]:
    if v in ("auto", "content"):
        return {"fxBasis": "-1"}
    if v.endswith("%"):
        return {"fxBasisPct": _percent(v)}
    return {"fxBasis": ctx.number(v)}


def _flex(value: str, ctx: _Context) -> dict[str, str]:
    """`flex: 1` (= 1 1 0), `flex: 1 0 200px`, `flex: auto` (= 1 1 auto), `flex: none` (= 0 0 auto)."""
    parts = value.split()
    if parts == ["none"]:
        return {"fxFlex": "0", "fxShrink": "0", "fxBasis": "-1"}
    if parts == ["auto"]:
        return {"fxFlex": "1", "fxBasis": "-1"}
    if not 1 <= len(parts) <= 3:
        raise StyleValueError(f"flex admite de 1 a 3 valores (crecer, encoger, base), se recibió {value!r}")
    out = {"fxFlex": _grow(parts[0], "flex")}
    if len(parts) >= 2:
        out["fxShrink"] = _number_text(parts[1], "el segundo valor de flex (encoger)")
    if len(parts) == 3:
        out.update(_basis_value(parts[2], ctx))
    return out


def _flex_grow(value: str, ctx: _Context) -> dict[str, str]:
    # Como en CSS: flex-grow solo no cambia la base (auto), a diferencia de flex: N.
    return {"fxFlex": _grow(value.strip(), "flex-grow"), "fxBasis": "-1"}


def _flex_shrink(value: str, ctx: _Context) -> dict[str, str]:
    return {"fxShrink": _number_text(value, "flex-shrink")}


def _flex_basis(value: str, ctx: _Context) -> dict[str, str]:
    return _basis_value(value.strip(), ctx)


def _order(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if not re.fullmatch(r"-?\d+", v):
        raise StyleValueError(f"order admite un número entero, se recibió {value!r}")
    return {"fxOrder": v}


# margin: auto se guarda por lado y compile_declarations lo junta en fxAutoMargin.
AUTO_MARGIN = "@auto-margin "
_AUTO_BITS = {"top": 1, "right": 2, "bottom": 4, "left": 8}


def _margin_side(side: str, v: str, ctx: _Context) -> dict[str, str]:
    key = f"Layout.{side}Margin"
    if v.strip() == "auto":
        return {key: "0", AUTO_MARGIN + side: "1"}
    return {key: ctx.number(v), AUTO_MARGIN + side: "0"}


def _margin(value: str, ctx: _Context) -> dict[str, str]:
    parts = value.split()
    if not 1 <= len(parts) <= 4:
        raise StyleValueError(f"margin admite de 1 a 4 valores, se recibió {value!r}")
    order = {1: (0, 0, 0, 0), 2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}[len(parts)]
    out: dict[str, str] = {}
    for side, i in zip(_SIDES, order):
        out.update(_margin_side(side, parts[i], ctx))
    return out


def _margin_one(side: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        return _margin_side(side, value, ctx)

    return convert


def _border_side(side: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        name = "fxBorder" + side.capitalize()
        props = _border(value, ctx)
        out = {}
        if "fxBorderWidth" in props:
            out[name] = props["fxBorderWidth"]
        if "fxBorderColor" in props:
            out[name + "Color"] = props["fxBorderColor"]
        return out

    return convert


def _border_side_part(side: str, part: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        name = "fxBorder" + side.capitalize()
        if part == "width":
            return {name: ctx.number(value)}
        return {name + "Color": ctx.color(value)}

    return convert


_CORNERS = ("topLeftRadius", "topRightRadius", "bottomRightRadius", "bottomLeftRadius")


def _radius(value: str, ctx: _Context) -> dict[str, str]:
    parts = value.split()
    if not 1 <= len(parts) <= 4:
        raise StyleValueError(f"border-radius admite de 1 a 4 valores, se recibió {value!r}")
    if len(parts) == 1:
        return {"fxRadius": ctx.number(parts[0])}
    if ctx.tag not in FLEXES:
        raise StyleValueError("un radio distinto por esquina solo se admite en <flex>, Column y Row")
    nums = [ctx.number(p) for p in parts]
    tl, tr, br, bl = {2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}[len(nums)]
    return dict(zip(_CORNERS, (nums[tl], nums[tr], nums[br], nums[bl])))


def _size(axis: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        v = value.strip()
        if ctx.tag == "Window":
            return {axis: ctx.number(v)}
        name = "Width" if axis == "width" else "Height"
        if v in ("auto", "fit-content"):
            return {}
        if v == "100%":
            return {f"Layout.fill{name}": "true"}
        if v.endswith("%"):
            # Porcentaje del contenedor: lo resuelve el motor de <flex> (también Column y Row).
            return {f"fx{name}Pct": _percent(v), f"Layout.fill{name}": "false"}
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
    "background": (BOXES | FIELDS | {"Text"}, _single("fxBackground", "color")),
    "background-color": (BOXES | FIELDS | {"Text"}, _single("fxBackground", "color")),
    "border": (BOXES | FIELDS | {"Text"}, _border),
    "border-color": (BOXES | FIELDS | {"Text"}, _single("fxBorderColor", "color")),
    "border-width": (BOXES | FIELDS | {"Text"}, _single("fxBorderWidth", "number")),
    "border-radius": (BOXES | FIELDS | {"Text"}, _radius),
    **{f"border-{side}": (FLEXES, _border_side(side)) for side in _SIDES},
    **{f"border-{side}-width": (FLEXES, _border_side_part(side, "width")) for side in _SIDES},
    **{f"border-{side}-color": (FLEXES, _border_side_part(side, "color")) for side in _SIDES},
    "overflow": (FLEXES, _overflow),
    "padding": (BOXES | TEXTUAL, _padding),
    **{f"padding-{side}": (BOXES | TEXTUAL, _padding_side(side)) for side in _SIDES},
    "gap": (BOXES, _single("gap", "number")),
    "row-gap": (FLEXES, _single("rowGap", "number")),
    "column-gap": (FLEXES, _single("columnGap", "number")),
    "flex-direction": ({"flex"}, _direction),
    "direction": ({"flex"}, _direction),
    "flex-wrap": (FLEXES, _wrap),
    "align-items": (FLEXES | {"Scroll"}, _align_items),
    "justify-content": (FLEXES | {"Scroll"}, _justify),
    "align-content": (FLEXES, _align_content),
    "font-size": (TEXTUAL | {"Window"}, _single("font.pixelSize", "number")),
    "font-weight": (TEXTUAL | {"Window"}, _weight),
    "font-family": (TEXTUAL | {"Window"}, _family),
    "font-style": (TEXTUAL | {"Window"}, _italic),
    "letter-spacing": (TEXTUAL, _single("font.letterSpacing", "number")),
    "text-transform": (TEXTUAL, _transform),
    "text-align": ({"Text", "TextField", "TextArea"}, _text_align),
    "line-height": ({"Text"}, _line_height),
    "flex": (ITEMS, _flex),
    "flex-grow": (ITEMS, _flex_grow),
    "flex-shrink": (ITEMS, _flex_shrink),
    "flex-basis": (ITEMS, _flex_basis),
    "order": (ITEMS, _order),
    "margin": (ITEMS, _margin),
    **{f"margin-{side}": (ITEMS, _margin_one(side)) for side in _SIDES},
    "align-self": (ITEMS, _align_self),
    "width": (ALL, _size("width")),
    "height": (ALL, _size("height")),
    "min-width": (ALL, _limit("min", "width")),
    "max-width": (ALL, _limit("max", "width")),
    "min-height": (ALL, _limit("min", "height")),
    "max-height": (ALL, _limit("max", "height")),
    "opacity": (ALL, _single("opacity", "number")),
    "transition": (ITEMS, _transition),
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
        if tag not in CONTROLS and ITEMS <= tags:
            pass  # elemento propio (.qml): admite las propiedades de disposición comunes
        elif tag not in tags:
            warn(f"'{decl.prop}' no tiene efecto en <{tag}>", decl)
            continue
        try:
            props.update(convert(decl.value, ctx))
        except StyleValueError as exc:
            warn(str(exc), decl)
    autos = [k for k in props if k.startswith(AUTO_MARGIN)]
    if autos:
        mask = sum(_AUTO_BITS[k[len(AUTO_MARGIN):]] for k in autos if props[k] == "1")
        for k in autos:
            del props[k]
        props["fxAutoMargin"] = str(mask)
    return props
