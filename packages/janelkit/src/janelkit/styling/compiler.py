"""Traduce declaraciones CSS-like a propiedades de los controles Qt Quick de JanelKit.

Qt Quick no es un navegador: solo se admite lo que figura en `SUPPORTED`.
Cualquier otra propiedad, o una propiedad que no aplica al elemento, genera
una advertencia con su ubicación. Los valores pueden ser tokens del tema:
`color: var(--text-muted)` se enlaza a `jktheme.text_muted` y cambia con el tema.
"""
from __future__ import annotations

import re
from typing import Callable

from ..compiler.ir import TokenUse, qml_string
from ..diagnostics import Diagnostic
from ..qt_backend.controls import CONTROLS
from .parser import Declaration

THEME_OBJECT = "jktheme"  # propiedad de contexto QML con los tokens del tema activo

FLEXES = {"flex", "Column", "Row"}  # cajas con el motor de <flex> (JkFlex)
BOXES = FLEXES | {"Scroll", "List"}
TEXTUAL = {"Text", "Button", "TextField", "TextArea", "Checkbox", "Switch", "Select", "RadioGroup", "Tabs"}
FIELDS = {"Button", "TextField", "TextArea", "Select"}
ITEMS = set(CONTROLS) - {"Window"}
ALL = set(CONTROLS)

_NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")
_VAR_RE = re.compile(r"^var\(\s*--([A-Za-z][\w-]*)\s*(?:,\s*(.+))?\)$")

# Texto que heredan los <Text> de dentro de una caja (fase 4 de docs/flex.md):
# propiedad QML del texto -> nombre en el contexto de estilo (JkContext.qml).
INHERITED = {
    "jkColor": "color", "font.family": "family", "font.pixelSize": "size", "font.weight": "weight",
    "font.italic": "italic", "font.letterSpacing": "letterSpacing", "font.capitalization": "capitalization",
    "horizontalAlignment": "align", "lineHeight": "lineHeight", "wrapMode": "wrap", "elide": "elide",
}  # fmt: skip
VAR_PREFIX = "jkV_"  # variable propia `--x` en una caja: propiedad jkV_x
TEXT_PREFIX = "jkT_"  # texto heredable fijado en una caja: jkT_color, jkT_size…
_WEIGHTS = {"normal": 400, "bold": 700, "lighter": 300, "bolder": 800}
_SIDES = ("top", "right", "bottom", "left")


class StyleValueError(ValueError):
    pass


def token_key(css_name: str) -> str:
    """`text-muted` -> `text_muted` (nombre de la propiedad QML del token)."""
    return css_name.replace("-", "_")


class _Context:
    """Estado de la compilación de una declaración: tokens usados y elemento destino."""

    def __init__(self, tag: str, decl: Declaration, tokens: list[TokenUse], local_vars: frozenset[str] = frozenset()):
        self.tag = tag
        self.decl = decl
        self.tokens = tokens
        self.local_vars = local_vars  # variables propias (--x) definidas en este componente
        self.notes: list[str] = []  # avisos que no impiden aplicar la declaración

    def token(self, value: str, convert: Callable[[str], str] | None = None, default: str = "undefined") -> str | None:
        """`var(--x)`: un token del tema, o una variable propia que se busca en los antecesores.

        Es propia si este componente la define o si lleva valor por defecto (`var(--x, 8px)`);
        si no, es un token del tema, como siempre.
        """
        m = _VAR_RE.match(value.strip())
        if not m:
            return None
        key = token_key(m.group(1))
        fallback = m.group(2)
        if fallback is None and key not in self.local_vars:
            self.tokens.append(TokenUse(key, self.decl.loc))
            return f"{THEME_OBJECT}.{key}"
        if fallback is not None:
            other = (convert or (lambda v: self.token(v) or qml_string(v.strip())))(fallback.strip())
        else:
            other = f"{THEME_OBJECT}.{key}"
        return f'Jk.cssVar(jkCtx, "{key}", {other}, {default})'

    def number(self, value: str) -> str:
        if (tok := self.token(value, self.number, "0")) is not None:
            return tok
        m = _NUM_RE.match(value.strip())
        if not m:
            raise StyleValueError(f"se esperaba un número en px o var(--token), se recibió {value!r}")
        return m.group(1)

    def color(self, value: str) -> str:
        if (tok := self.token(value, self.color, '"transparent"')) is not None:
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

_NUMBER_ANIM = "NumberAnimation"
_COLOR_ANIM = "ColorAnimation"
# transition: <propiedad CSS> -> [(propiedad QML, animación)]
_ANIMATABLE = {
    "color": [("jkColor", _COLOR_ANIM)],
    "background": [("jkBackground", _COLOR_ANIM)],
    "background-color": [("jkBackground", _COLOR_ANIM)],
    "border-color": [("jkBorderColor", _COLOR_ANIM)],
    "opacity": [("opacity", _NUMBER_ANIM)],
    "width": [("Layout.preferredWidth", _NUMBER_ANIM)],
    "height": [("Layout.preferredHeight", _NUMBER_ANIM)],
    "border-radius": [("jkRadius", _NUMBER_ANIM)],
    "transform": [("scale", _NUMBER_ANIM), ("rotation", _NUMBER_ANIM), ("jkTx", _NUMBER_ANIM), ("jkTy", _NUMBER_ANIM)],
    "box-shadow": [
        ("jkShadowX", _NUMBER_ANIM), ("jkShadowY", _NUMBER_ANIM), ("jkShadowBlur", _NUMBER_ANIM),
        ("jkShadowSpread", _NUMBER_ANIM), ("jkShadowColor", _COLOR_ANIM),
    ],
    "outline": [("jkOutlineColor", _COLOR_ANIM), ("jkOutlineWidth", _NUMBER_ANIM), ("jkOutlineOffset", _NUMBER_ANIM)],
    "outline-color": [("jkOutlineColor", _COLOR_ANIM)],
}  # fmt: skip
# Solo existen en las cajas (<flex>, Column, Row).
_FLEX_ONLY_ANIM = {"box-shadow", "outline", "outline-color"}
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
        flex = ctx.tag in FLEXES
        if prop == "all":
            props = [n for n in _ANIMATABLE if flex or n not in _FLEX_ONLY_ANIM]
        else:
            props = [prop]
        for name in props:
            if name not in _ANIMATABLE:
                raise StyleValueError(
                    f"transition no puede animar {name!r}; se admiten: {', '.join(_ANIMATABLE)} y all"
                )
            if name in _FLEX_ONLY_ANIM and not flex:
                raise StyleValueError(f"{name} solo existe en <flex>, Column y Row")
            for qml_prop, animation in _ANIMATABLE[name]:
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
        return {"jkBorderWidth": "0"}
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
        out["jkBorderWidth"] = width
    if color is not None:
        out["jkBorderColor"] = color
        out.setdefault("jkBorderWidth", "1")
    return out


def _split_top(value: str, sep: str = ",") -> list[str]:
    """Separa por `sep` fuera de paréntesis: `0 2px 8px rgba(0,0,0,.1), 0 1px 2px #000`."""
    parts, depth, cur = [], 0, ""
    for ch in value:
        depth += ch == "("
        depth -= ch == ")"
        if ch == sep and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return [p for p in parts if p]


def _words_of(value: str) -> list[str]:
    """Palabras separadas por espacios, respetando paréntesis: `1px solid rgba(0, 0, 0, .1)`."""
    return re.findall(r"[^\s(]+(?:\([^)]*\))?", value.strip())


def _box_shadow(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if v == "none":
        return {"jkShadow": "false"}
    shadows = _split_top(v)
    if len(shadows) > 1:
        ctx.notes.append("solo se dibuja la primera sombra de box-shadow")
    lengths: list[str] = []
    color = None
    for part in _words_of(shadows[0]):
        if part == "inset":
            raise StyleValueError("box-shadow: inset no está soportado")
        if _NUM_RE.match(part):
            lengths.append(ctx.number(part))
        elif color is None:
            color = ctx.color(part)
        else:
            raise StyleValueError(f"box-shadow no válido: {value!r}; usa p. ej. 0 2px 8px rgba(0, 0, 0, .15)")
    if not 2 <= len(lengths) <= 4:
        raise StyleValueError(f"box-shadow necesita de 2 a 4 medidas (x, y, desenfoque, extensión): {value!r}")
    lengths += ["0"] * (4 - len(lengths))
    return {
        "jkShadow": "true",
        "jkShadowX": lengths[0],
        "jkShadowY": lengths[1],
        "jkShadowBlur": lengths[2],
        "jkShadowSpread": lengths[3],
        "jkShadowColor": color or "Qt.rgba(0, 0, 0, 0.25)",
    }


def _outline(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if v in ("none", "0"):
        return {"jkOutlineWidth": "0"}
    width = color = None
    for part in _words_of(v):
        if part in ("solid", "none", "auto"):
            continue
        if width is None and _NUM_RE.match(part):
            width = ctx.number(part)
        elif color is None:
            color = ctx.color(part)
        else:
            raise StyleValueError(f"outline no válido: {value!r}; usa p. ej. 2px solid var(--primary)")
    out = {"jkOutlineWidth": width or "2"}
    if color is not None:
        out["jkOutlineColor"] = color
    return out


_CURSORS = {
    "default": "Qt.ArrowCursor", "auto": "Qt.ArrowCursor", "pointer": "Qt.PointingHandCursor",
    "text": "Qt.IBeamCursor", "move": "Qt.SizeAllCursor", "grab": "Qt.OpenHandCursor",
    "grabbing": "Qt.ClosedHandCursor", "not-allowed": "Qt.ForbiddenCursor", "wait": "Qt.WaitCursor",
    "progress": "Qt.BusyCursor", "crosshair": "Qt.CrossCursor", "help": "Qt.WhatsThisCursor",
    "ew-resize": "Qt.SizeHorCursor", "ns-resize": "Qt.SizeVerCursor", "nesw-resize": "Qt.SizeBDiagCursor",
    "nwse-resize": "Qt.SizeFDiagCursor", "col-resize": "Qt.SplitHCursor", "row-resize": "Qt.SplitVCursor",
}  # fmt: skip


def _cursor(value: str, ctx: _Context) -> dict[str, str]:
    return {"jkCursor": _keyword(value, _CURSORS, "cursor")}


_ANGLE_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(deg|turn)?$")


def _box_transform(value: str, ctx: _Context) -> dict[str, str]:
    """`scale(1.05) rotate(5deg) translate(0, -2px)`; reemplaza la transformación entera, como en CSS."""
    out = {"scale": "1", "rotation": "0", "jkTx": "0", "jkTy": "0"}
    v = value.strip()
    if v == "none":
        return out
    funcs = re.findall(r"([a-zA-Z]+)\(([^)]*)\)", v)
    if not funcs or re.sub(r"[a-zA-Z]+\([^)]*\)", "", v).strip():
        raise StyleValueError(f"transform no válido: {value!r}; usa scale(), rotate() y translate()")
    for name, args_text in funcs:
        args = [a.strip() for a in args_text.split(",") if a.strip()]
        if name == "scale" and (len(args) == 1 or (len(args) == 2 and args[0] == args[1])):
            out["scale"] = ctx.number(args[0])
        elif name == "rotate" and len(args) == 1 and (m := _ANGLE_RE.match(args[0])):
            out["rotation"] = f"{float(m.group(1)) * (360 if m.group(2) == 'turn' else 1):g}"
        elif name == "translate" and len(args) in (1, 2):
            out["jkTx"] = ctx.number(args[0])
            out["jkTy"] = ctx.number(args[1]) if len(args) == 2 else "0"
        elif name in ("translateX", "translateY") and len(args) == 1:
            out["jkTx" if name == "translateX" else "jkTy"] = ctx.number(args[0])
        else:
            raise StyleValueError(
                f"transform: {name}({args_text}) no está soportado; usa scale(n), rotate(Ndeg) y translate(x, y)"
            )
    return out


def _weight(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip().lower()
    if v in _WEIGHTS:
        return {"font.weight": str(_WEIGHTS[v])}
    if v.isdigit() and 1 <= int(v) <= 1000:
        return {"font.weight": v}
    raise StyleValueError(f"font-weight no válido: {value!r}")


def _family(value: str, ctx: _Context) -> dict[str, str]:
    plain = lambda v: qml_string(v.strip().strip("\"'"))  # noqa: E731
    return {"font.family": ctx.token(value, plain, '""') or plain(value)}


def _white_space(value: str, ctx: _Context) -> dict[str, str]:
    return {"wrapMode": _keyword(value, {"normal": "Text.Wrap", "nowrap": "Text.NoWrap", "pre-wrap": "Text.Wrap"}, "white-space")}


def _user_select(value: str, ctx: _Context) -> dict[str, str]:
    return {"selectable": _keyword(value, {"text": "true", "auto": "false", "none": "false"}, "user-select")}


def _text_overflow(value: str, ctx: _Context) -> dict[str, str]:
    return {"elide": _keyword(value, {"ellipsis": "Text.ElideRight", "clip": "Text.ElideNone"}, "text-overflow")}


def _variable(value: str, ctx: _Context) -> str:
    """Valor de `--x: …`: color, medida o texto."""
    v = value.strip()
    if _VAR_RE.match(v):
        return ctx.token(v) or "undefined"
    if _NUM_RE.match(v):
        return ctx.number(v)
    try:
        return ctx.color(v)
    except StyleValueError:
        return qml_string(v.strip("\"'"))


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
    return {"jkOverflow": _keyword(value, _words("visible", "hidden", "auto", "scroll"), "overflow")}


def _align_self(value: str, ctx: _Context) -> dict[str, str]:
    v = _keyword(value, {"start": "start", "center": "center", "end": "end", "stretch": "stretch", "auto": ""}, "align-self")
    if v == "stretch":
        return {"jkSelfStretch": "true"}
    return {"jkSelfAlign": qml_string(v)}


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
        return {"jkBasis": "-1"}
    if v.endswith("%"):
        return {"jkBasisPct": _percent(v)}
    return {"jkBasis": ctx.number(v)}


def _flex(value: str, ctx: _Context) -> dict[str, str]:
    """`flex: 1` (= 1 1 0), `flex: 1 0 200px`, `flex: auto` (= 1 1 auto), `flex: none` (= 0 0 auto)."""
    parts = value.split()
    if parts == ["none"]:
        return {"jkFlex": "0", "jkShrink": "0", "jkBasis": "-1"}
    if parts == ["auto"]:
        return {"jkFlex": "1", "jkBasis": "-1"}
    if not 1 <= len(parts) <= 3:
        raise StyleValueError(f"flex admite de 1 a 3 valores (crecer, encoger, base), se recibió {value!r}")
    out = {"jkFlex": _grow(parts[0], "flex")}
    if len(parts) >= 2:
        out["jkShrink"] = _number_text(parts[1], "el segundo valor de flex (encoger)")
    if len(parts) == 3:
        out.update(_basis_value(parts[2], ctx))
    return out


def _flex_grow(value: str, ctx: _Context) -> dict[str, str]:
    # Como en CSS: flex-grow solo no cambia la base (auto), a diferencia de flex: N.
    return {"jkFlex": _grow(value.strip(), "flex-grow"), "jkBasis": "-1"}


def _flex_shrink(value: str, ctx: _Context) -> dict[str, str]:
    return {"jkShrink": _number_text(value, "flex-shrink")}


def _flex_basis(value: str, ctx: _Context) -> dict[str, str]:
    return _basis_value(value.strip(), ctx)


def _order(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if not re.fullmatch(r"-?\d+", v):
        raise StyleValueError(f"order admite un número entero, se recibió {value!r}")
    return {"jkOrder": v}


# margin: auto se guarda por lado y compile_declarations lo junta en jkAutoMargin.
AUTO_MARGIN = "@auto-margin "
_AUTO_BITS = {"top": 1, "right": 2, "bottom": 4, "left": 8}


def _margin_side(side: str, v: str, ctx: _Context) -> dict[str, str]:
    key = f"Layout.{side}Margin"
    if v.strip() == "auto":
        return {key: "0", AUTO_MARGIN + side: "1"}
    return {key: ctx.number(v), AUTO_MARGIN + side: "0"}


def _position(value: str, ctx: _Context) -> dict[str, str]:
    v = _keyword(value, {k: k for k in ("static", "relative", "absolute", "fixed")}, "position")
    return {"jkPosition": qml_string(v)}


_EDGE_PROPS = {"top": "jkTop", "right": "jkRight", "bottom": "jkBottom", "left": "jkLeft"}


def _edge_value(v: str, ctx: _Context) -> str:
    """top/left…: px (número) o porcentaje del bloque contenedor (texto "50%"); `auto`: sin fijar."""
    v = v.strip()
    if v == "auto":
        return "undefined"
    if re.fullmatch(r"-?\d+(?:\.\d+)?%", v):
        return qml_string(v)
    return ctx.number(v)


def _edge(side: str) -> Converter:
    return lambda value, ctx: {_EDGE_PROPS[side]: _edge_value(value, ctx)}


def _inset(value: str, ctx: _Context) -> dict[str, str]:
    parts = value.split()
    if not 1 <= len(parts) <= 4:
        raise StyleValueError(f"inset admite de 1 a 4 valores, se recibió {value!r}")
    order = {1: (0, 0, 0, 0), 2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}[len(parts)]
    return {_EDGE_PROPS[side]: _edge_value(parts[i], ctx) for side, i in zip(_SIDES, order)}


def _z_index(value: str, ctx: _Context) -> dict[str, str]:
    v = value.strip()
    if v == "auto":
        return {"z": "0"}
    if not re.fullmatch(r"-?\d+", v):
        raise StyleValueError(f"z-index admite un número entero, se recibió {value!r}")
    return {"z": v}


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
        name = "jkBorder" + side.capitalize()
        props = _border(value, ctx)
        out = {}
        if "jkBorderWidth" in props:
            out[name] = props["jkBorderWidth"]
        if "jkBorderColor" in props:
            out[name + "Color"] = props["jkBorderColor"]
        return out

    return convert


def _border_side_part(side: str, part: str) -> Converter:
    def convert(value: str, ctx: _Context) -> dict[str, str]:
        name = "jkBorder" + side.capitalize()
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
        return {"jkRadius": ctx.number(parts[0])}
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
            return {f"jk{name}Pct": _percent(v), f"Layout.fill{name}": "false"}
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
    "color": (TEXTUAL | FLEXES, _single("jkColor", "color")),
    "background": (BOXES | FIELDS | {"Text"}, _single("jkBackground", "color")),
    "background-color": (BOXES | FIELDS | {"Text"}, _single("jkBackground", "color")),
    "border": (BOXES | FIELDS | {"Text"}, _border),
    "border-color": (BOXES | FIELDS | {"Text"}, _single("jkBorderColor", "color")),
    "border-width": (BOXES | FIELDS | {"Text"}, _single("jkBorderWidth", "number")),
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
    "font-size": (TEXTUAL | FLEXES | {"Window"}, _single("font.pixelSize", "number")),
    "font-weight": (TEXTUAL | FLEXES | {"Window"}, _weight),
    "font-family": (TEXTUAL | FLEXES | {"Window"}, _family),
    "font-style": (TEXTUAL | FLEXES | {"Window"}, _italic),
    "letter-spacing": (TEXTUAL | FLEXES, _single("font.letterSpacing", "number")),
    "text-transform": (TEXTUAL | FLEXES, _transform),
    "text-align": ({"Text", "TextField", "TextArea"} | FLEXES, _text_align),
    "line-height": ({"Text"} | FLEXES, _line_height),
    "white-space": ({"Text"} | FLEXES, _white_space),
    "text-overflow": ({"Text"} | FLEXES, _text_overflow),
    "user-select": ({"Text"}, _user_select),
    "flex": (ITEMS, _flex),
    "flex-grow": (ITEMS, _flex_grow),
    "flex-shrink": (ITEMS, _flex_shrink),
    "flex-basis": (ITEMS, _flex_basis),
    "order": (ITEMS, _order),
    "margin": (ITEMS, _margin),
    "position": (ITEMS, _position),
    "top": (ITEMS, _edge("top")),
    "right": (ITEMS, _edge("right")),
    "bottom": (ITEMS, _edge("bottom")),
    "left": (ITEMS, _edge("left")),
    "inset": (ITEMS, _inset),
    "z-index": (ITEMS, _z_index),
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
    "transform": (ITEMS, _box_transform),
    "cursor": (ITEMS, _cursor),
    "box-shadow": (FLEXES, _box_shadow),
    "outline": (FLEXES, _outline),
    "outline-width": (FLEXES, _single("jkOutlineWidth", "number")),
    "outline-color": (FLEXES, _single("jkOutlineColor", "color")),
    "outline-offset": (FLEXES, _single("jkOutlineOffset", "number")),
    "pointer-events": (FLEXES, lambda v, ctx: {"jkPointerEvents": _keyword(v, {"auto": "true", "none": "false"}, "pointer-events")}),
    "visibility": (FLEXES, lambda v, ctx: {"jkHidden": _keyword(v, {"visible": "false", "hidden": "true"}, "visibility")}),
}

# Window usa su propia propiedad de color de fondo.
_WINDOW_OVERRIDES = {"background": "color", "background-color": "color"}


def compile_declarations(
    decls: list[Declaration],
    tag: str,
    source: str,
    warnings: list[Diagnostic],
    tokens: list[TokenUse] | None = None,
    local_vars: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Propiedades QML (nombre -> expresión) para el elemento `tag`."""
    tokens = tokens if tokens is not None else []
    props: dict[str, str] = {}

    def warn(msg: str, decl: Declaration, hint: str | None = None) -> None:
        warnings.append(Diagnostic(msg, decl.loc, hint, severity="warning", source=source))

    for decl in decls:
        ctx = _Context(tag, decl, tokens, local_vars)
        if decl.prop.startswith("--"):
            # Variable propia: la ven la caja y todo lo que contiene (también otros componentes).
            if tag not in FLEXES:
                warn(f"las variables propias ({decl.prop}) se definen en <flex>, Column o Row", decl)
                continue
            props[VAR_PREFIX + token_key(decl.prop[2:])] = _variable(decl.value, ctx)
            continue
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
        for note in ctx.notes:
            warn(note, decl)
    if tag in FLEXES:
        # En una caja, el texto no es suyo: lo heredan los <Text> de dentro.
        props = {(TEXT_PREFIX + INHERITED[k] if k in INHERITED else k): v for k, v in props.items()}
        props.pop(BEHAVIOR + "jkColor", None)  # el color heredado no se anima en la caja
    autos = [k for k in props if k.startswith(AUTO_MARGIN)]
    if autos:
        mask = sum(_AUTO_BITS[k[len(AUTO_MARGIN):]] for k in autos if props[k] == "1")
        for k in autos:
            del props[k]
        props["jkAutoMargin"] = str(mask)
    return props
