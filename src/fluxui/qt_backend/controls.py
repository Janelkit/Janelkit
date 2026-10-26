"""Catálogo de elementos .flux y su equivalencia en Qt Quick.

Es la única tabla que conoce los nombres QML; el resto del compilador trabaja
con estas especificaciones. Los tipos `Fx*` pertenecen al módulo QML interno
`Flux` (`fluxui/qml/Flux`), que se distribuye con el paquete: aplican el tema
y las reglas de disposición. El usuario nunca escribe QML.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PropSpec:
    qml: str
    type: str = "any"  # "string" | "number" | "bool" | "color" | "any"


@dataclass(frozen=True)
class EventSpec:
    qml_handler: str  # p. ej. "onClicked"
    args: tuple[str, ...] = ()  # expresiones QML que se pasan al manejador Python
    enables: str | None = None  # propiedad booleana que el control necesita activar para emitirlo


@dataclass(frozen=True)
class TwoWaySpec:
    qml_prop: str
    qml_handler: str  # señal que indica un cambio hecho por el usuario


@dataclass(frozen=True)
class ControlSpec:
    qml_type: str
    props: dict[str, PropSpec] = field(default_factory=dict)
    events: dict[str, EventSpec] = field(default_factory=dict)
    two_way: dict[str, TwoWaySpec] = field(default_factory=dict)
    text_prop: str | None = None  # propiedad que recibe el contenido textual
    container: bool = False
    horizontal: bool = False  # contenedores: eje principal horizontal


# Propiedades de disposición comunes a todos los elementos salvo Window.
COMMON_PROPS: dict[str, PropSpec] = {
    "width": PropSpec("Layout.preferredWidth", "number"),
    "height": PropSpec("Layout.preferredHeight", "number"),
    "flex": PropSpec("fxFlex", "number"),
    "visible": PropSpec("visible", "bool"),
    "enabled": PropSpec("enabled", "bool"),
    "opacity": PropSpec("opacity", "number"),
}

_BOX_PROPS = {
    "gap": PropSpec("gap", "number"),
    "padding": PropSpec("padding", "number"),
}

_BOX_EVENTS = {"click": EventSpec("onClicked", enables="fxClickable")}

CONTROLS: dict[str, ControlSpec] = {
    "Window": ControlSpec(
        "FxWindow",
        props={
            "title": PropSpec("title", "string"),
            "width": PropSpec("width", "number"),
            "height": PropSpec("height", "number"),
            "minWidth": PropSpec("minimumWidth", "number"),
            "minHeight": PropSpec("minimumHeight", "number"),
            "background": PropSpec("color", "color"),
        },
        container=True,
    ),
    "Column": ControlSpec("FxColumn", props=dict(_BOX_PROPS), events=dict(_BOX_EVENTS), container=True),
    "Row": ControlSpec("FxRow", props=dict(_BOX_PROPS), events=dict(_BOX_EVENTS), container=True, horizontal=True),
    "Scroll": ControlSpec(
        "FxScroll",
        props={"gap": PropSpec("gap", "number"), "padding": PropSpec("innerPadding", "number")},
        container=True,
    ),
    "Text": ControlSpec(
        "FxText",
        props={"text": PropSpec("text", "string"), "color": PropSpec("fxColor", "color")},
        text_prop="text",
    ),
    "Button": ControlSpec(
        "FxButton",
        props={
            "text": PropSpec("text", "string"),
            "flat": PropSpec("flat", "bool"),
            "variant": PropSpec("variant", "string"),
        },
        events={"click": EventSpec("onClicked")},
        text_prop="text",
    ),
    "TextField": ControlSpec(
        "FxTextField",
        props={
            "value": PropSpec("text", "string"),
            "placeholder": PropSpec("placeholderText", "string"),
            "readonly": PropSpec("readOnly", "bool"),
        },
        events={
            "input": EventSpec("onTextEdited", ("text",)),
            "submit": EventSpec("onAccepted", ("text",)),
        },
        two_way={"value": TwoWaySpec("text", "onTextEdited")},
    ),
    "TextArea": ControlSpec(
        "FxTextArea",
        props={
            "value": PropSpec("text", "string"),
            "placeholder": PropSpec("placeholderText", "string"),
            "readonly": PropSpec("readOnly", "bool"),
        },
        # TextArea no distingue cambios del usuario de los programáticos; escribir
        # el mismo valor de vuelta no notifica, así que no hay bucles.
        two_way={"value": TwoWaySpec("text", "onTextChanged")},
    ),
    "Checkbox": ControlSpec(
        "FxCheckBox",
        props={"checked": PropSpec("checked", "bool"), "text": PropSpec("text", "string")},
        events={"change": EventSpec("onToggled", ("checked",))},
        two_way={"checked": TwoWaySpec("checked", "onToggled")},
        text_prop="text",
    ),
    "Spacer": ControlSpec("FxSpacer"),
}

QML_IMPORTS = ("QtQuick", "QtQuick.Controls", "QtQuick.Layouts", "Flux")


def tag_of(spec: ControlSpec) -> str:
    return next(tag for tag, s in CONTROLS.items() if s is spec)


def prop_spec(spec: ControlSpec, name: str) -> PropSpec | None:
    if spec.qml_type == "FxWindow":
        return spec.props.get(name)
    return spec.props.get(name) or COMMON_PROPS.get(name)


def all_props(spec: ControlSpec) -> list[str]:
    if spec.qml_type == "FxWindow":
        return sorted(spec.props)
    return sorted({*spec.props, *COMMON_PROPS})
