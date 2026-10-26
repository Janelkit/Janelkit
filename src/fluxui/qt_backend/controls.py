"""Catálogo de elementos .flux y su equivalencia en Qt Quick / Qt Quick Controls.

Es la única tabla que conoce los nombres QML; el resto del compilador trabaja
con estas especificaciones.
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
    defaults: dict[str, str] = field(default_factory=dict)  # literales QML


COMMON_PROPS: dict[str, PropSpec] = {
    "width": PropSpec("width", "number"),
    "height": PropSpec("height", "number"),
    "visible": PropSpec("visible", "bool"),
    "enabled": PropSpec("enabled", "bool"),
    "opacity": PropSpec("opacity", "number"),
}

_LAYOUT_PROPS = {
    "gap": PropSpec("spacing", "number"),
    "padding": PropSpec("padding", "number"),
}

CONTROLS: dict[str, ControlSpec] = {
    "Window": ControlSpec(
        "ApplicationWindow",
        props={
            "title": PropSpec("title", "string"),
            "width": PropSpec("width", "number"),
            "height": PropSpec("height", "number"),
            "minWidth": PropSpec("minimumWidth", "number"),
            "minHeight": PropSpec("minimumHeight", "number"),
            "background": PropSpec("color", "color"),
        },
        container=True,
        defaults={"visible": "true", "width": "640", "height": "480"},
    ),
    "Column": ControlSpec("Column", props=dict(_LAYOUT_PROPS), container=True),
    "Row": ControlSpec("Row", props=dict(_LAYOUT_PROPS), container=True),
    "Text": ControlSpec(
        "Label",
        props={"text": PropSpec("text", "string"), "color": PropSpec("color", "color")},
        text_prop="text",
    ),
    "Button": ControlSpec(
        "Button",
        props={"text": PropSpec("text", "string"), "flat": PropSpec("flat", "bool")},
        events={"click": EventSpec("onClicked")},
        text_prop="text",
    ),
    "TextField": ControlSpec(
        "TextField",
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
    "Checkbox": ControlSpec(
        "CheckBox",
        props={"checked": PropSpec("checked", "bool"), "text": PropSpec("text", "string")},
        events={"change": EventSpec("onToggled", ("checked",))},
        two_way={"checked": TwoWaySpec("checked", "onToggled")},
        text_prop="text",
    ),
}

QML_IMPORTS = ("QtQuick", "QtQuick.Controls")


def prop_spec(spec: ControlSpec, name: str) -> PropSpec | None:
    return spec.props.get(name) or COMMON_PROPS.get(name)


def all_props(spec: ControlSpec) -> list[str]:
    return sorted({*spec.props, *COMMON_PROPS})
