"""Catálogo de elementos .janel y su equivalencia en Qt Quick.

Es la única tabla que conoce los nombres QML; el resto del compilador trabaja
con estas especificaciones. Los tipos `Jk*` pertenecen al módulo QML interno
`Janel` (`janelkit/qml/Janel`), que se distribuye con el paquete: aplican el tema
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
    when: str | None = None  # condición QML: el manejador solo se llama si se cumple
    params: tuple[str, ...] = ()  # parámetros de la señal (se declaran: Qt ya no los inyecta)


@dataclass(frozen=True)
class TwoWaySpec:
    qml_prop: str
    qml_handler: str  # señal que indica un cambio hecho por el usuario
    qml_value: str | None = None  # expresión con el valor nuevo (por defecto, qml_prop)
    params: tuple[str, ...] = ()  # parámetros de la señal


@dataclass(frozen=True)
class ControlSpec:
    qml_type: str
    props: dict[str, PropSpec] = field(default_factory=dict)
    events: dict[str, EventSpec] = field(default_factory=dict)
    two_way: dict[str, TwoWaySpec] = field(default_factory=dict)
    text_prop: str | None = None  # propiedad que recibe el contenido textual
    container: bool = False
    horizontal: bool = False  # contenedores: eje principal horizontal
    tag: str | None = None  # elementos propios (QML del proyecto): nombre en la plantilla
    fixed: dict[str, str] = field(default_factory=dict)  # propiedades QML que el compilador fija siempre


# Propiedades de disposición comunes a todos los elementos salvo Window.
COMMON_PROPS: dict[str, PropSpec] = {
    "width": PropSpec("Layout.preferredWidth", "number"),
    "height": PropSpec("Layout.preferredHeight", "number"),
    "flex": PropSpec("jkFlex", "number"),
    "visible": PropSpec("visible", "bool"),
    "enabled": PropSpec("enabled", "bool"),
    "opacity": PropSpec("opacity", "number"),
    "label": PropSpec("Accessible.name", "string"),  # nombre para lectores de pantalla
}

_BOX_PROPS = {
    "gap": PropSpec("gap", "number"),
    "padding": PropSpec("padding", "number"),
}

# Cajas (<flex>, Column, Row): las propiedades de comportamiento y accesibilidad de flex.md.
_BOX_PROPS.update({
    "as": PropSpec("jkRole", "string"),  # papel accesible y teclado (ver ROLES)
    "tabindex": PropSpec("jkTabIndex", "number"),  # 0: en el orden de Tab; -1: solo por código
    "disabled": PropSpec("disabled", "bool"),
    "title": PropSpec("ToolTip.text", "string"),  # descripción emergente
    "draggable": PropSpec("jkDraggable", "bool"),  # se puede arrastrar (on:dragstart…, events.py)
})  # fmt: skip

# Los eventos de las cajas los entrega JanelKit (qt_backend/events.py) con propagación,
# event.prevent() y event.stop(): no son señales de Qt.
ROUTE = "@route"
ROUTED_EVENTS = (
    "click", "dblclick", "contextmenu", "pointerdown", "pointerup", "pointermove",
    "pointerenter", "pointerleave", "wheel", "keydown", "keyup", "focus", "blur", "resize",
    "dragstart", "dragover", "drop", "dragend",
)  # fmt: skip
_BOX_EVENTS = {
    name: EventSpec(ROUTE, enables="jkClickable" if name == "click" else None) for name in ROUTED_EVENTS
}
# Los campos (TextField, TextArea, Select) también reciben por events.py el teclado y el foco.
_FIELD_EVENTS = {name: EventSpec(ROUTE) for name in ("keydown", "keyup", "focus", "blur")}
# Papeles de `as`: los interactivos entran en el orden de Tab y se activan con el teclado.
ROLES = ("box", "button", "link", "checkbox", "switch", "tab", "menuitem", "option",
         "listitem", "list", "menu", "tablist", "dialog", "heading", "region")  # fmt: skip
INTERACTIVE_ROLES = ("button", "link", "checkbox", "switch")

CONTROLS: dict[str, ControlSpec] = {
    "Window": ControlSpec(
        "JkWindow",
        props={
            "title": PropSpec("title", "string"),
            "width": PropSpec("width", "number"),
            "height": PropSpec("height", "number"),
            "minWidth": PropSpec("minimumWidth", "number"),
            "minHeight": PropSpec("minimumHeight", "number"),
            "background": PropSpec("color", "color"),
        },
        events={
            "activate": EventSpec("onActiveChanged", when="active"),
            "deactivate": EventSpec("onActiveChanged", when="!active"),
        },
        container=True,
    ),
    # Elemento base (en minúscula): la caja con flexbox de la web. Column y Row son atajos suyos.
    "flex": ControlSpec(
        "JkFlex",
        props={
            **_BOX_PROPS,
            "direction": PropSpec("direction", "string"),  # row | column | row-reverse | column-reverse
            "wrap": PropSpec("wrap", "bool"),
            "align": PropSpec("alignItems", "string"),
            "justify": PropSpec("justifyContent", "string"),
            # Estados para :checked, :selected y :expanded (y, más adelante, la accesibilidad).
            "checked": PropSpec("checked", "bool"),
            "selected": PropSpec("selected", "bool"),
            "expanded": PropSpec("expanded", "bool"),
        },
        events=dict(_BOX_EVENTS),
        container=True,
        horizontal=True,
    ),
    "Column": ControlSpec("JkColumn", props=dict(_BOX_PROPS), events=dict(_BOX_EVENTS), container=True),
    "Row": ControlSpec("JkRow", props=dict(_BOX_PROPS), events=dict(_BOX_EVENTS), container=True, horizontal=True),
    "Scroll": ControlSpec(
        "JkScroll",
        props={"gap": PropSpec("gap", "number"), "padding": PropSpec("innerPadding", "number")},
        container=True,
    ),
    "List": ControlSpec(
        "JkList",
        props={
            "gap": PropSpec("gap", "number"),
            "padding": PropSpec("innerPadding", "number"),
            "animate": PropSpec("animate", "bool"),
            "follow": PropSpec("follow", "bool"),
        },
        events={
            "top": EventSpec("onReachedTop"),
            "bottom": EventSpec("onReachedBottom"),
            "scroll": EventSpec("onScrolled", ("info",), enables="jkScrollHandled", params=("info",)),
        },
    ),
    "Text": ControlSpec(
        "JkText",
        props={
            "text": PropSpec("text", "string"),
            "color": PropSpec("jkColor", "color"),
            "format": PropSpec("format", "string"),  # "plain" | "markdown" | "html"
            "selectable": PropSpec("selectable", "bool"),  # se puede seleccionar y copiar
        },
        # Sin on:link, los enlaces se abren en el navegador.
        events={"link": EventSpec("onLinkActivated", ("link",), enables="jkLinkHandled", params=("link",))},
        text_prop="text",
    ),
    "Button": ControlSpec(
        "JkButton",
        props={
            "text": PropSpec("text", "string"),
            "flat": PropSpec("flat", "bool"),
            "variant": PropSpec("variant", "string"),
        },
        events={"click": EventSpec("onClicked")},
        text_prop="text",
    ),
    "TextField": ControlSpec(
        "JkTextField",
        props={
            "value": PropSpec("text", "string"),
            "placeholder": PropSpec("placeholderText", "string"),
            "readonly": PropSpec("readOnly", "bool"),
        },
        events={
            "input": EventSpec("onTextEdited", ("text",)),
            "submit": EventSpec("onAccepted", ("text",)),
            **_FIELD_EVENTS,
        },
        two_way={"value": TwoWaySpec("text", "onTextEdited")},
    ),
    "TextArea": ControlSpec(
        "JkTextArea",
        props={
            "value": PropSpec("jkValue", "string"),
            "placeholder": PropSpec("placeholderText", "string"),
            "readonly": PropSpec("readOnly", "bool"),
        },
        # JkTextArea emite userEdited solo con los cambios del usuario (no con los de Python).
        events={"input": EventSpec("onUserEdited", ("text",), params=("text",)), **_FIELD_EVENTS},
        two_way={"value": TwoWaySpec("jkValue", "onUserEdited", "text", params=("text",))},
    ),
    "Checkbox": ControlSpec(
        "JkCheckBox",
        props={"checked": PropSpec("checked", "bool"), "text": PropSpec("text", "string")},
        events={"change": EventSpec("onToggled", ("checked",))},
        two_way={"checked": TwoWaySpec("checked", "onToggled")},
        text_prop="text",
    ),
    "Switch": ControlSpec(
        "JkSwitch",
        props={"checked": PropSpec("checked", "bool"), "text": PropSpec("text", "string")},
        events={"change": EventSpec("onToggled", ("checked",))},
        two_way={"checked": TwoWaySpec("checked", "onToggled")},
        text_prop="text",
    ),
    "Slider": ControlSpec(
        "JkSlider",
        props={
            "value": PropSpec("value", "number"),
            "min": PropSpec("from", "number"),
            "max": PropSpec("to", "number"),
            "step": PropSpec("stepSize", "number"),
        },
        events={"change": EventSpec("onMoved", ("value",))},
        two_way={"value": TwoWaySpec("value", "onMoved")},
    ),
    "Select": ControlSpec(
        "JkSelect",
        props={
            "options": PropSpec("options"),
            "value": PropSpec("value"),
            "placeholder": PropSpec("placeholder", "string"),
        },
        events={"change": EventSpec("onActivated", ("currentValue",)), **_FIELD_EVENTS},
        two_way={"value": TwoWaySpec("value", "onActivated", "currentValue")},
    ),
    "RadioGroup": ControlSpec(
        "JkRadioGroup",
        props={
            "options": PropSpec("options"),
            "value": PropSpec("value"),
            "horizontal": PropSpec("horizontal", "bool"),
        },
        events={"change": EventSpec("onPicked", ("choice",), params=("choice",))},
        two_way={"value": TwoWaySpec("value", "onPicked", "choice", params=("choice",))},
    ),
    "Tabs": ControlSpec(
        "JkTabs",
        props={"options": PropSpec("options"), "value": PropSpec("value")},
        events={"change": EventSpec("onPicked", ("choice",), params=("choice",))},
        two_way={"value": TwoWaySpec("value", "onPicked", "choice", params=("choice",))},
    ),
    "Image": ControlSpec(
        "JkImage",
        props={"src": PropSpec("src", "string"), "fit": PropSpec("fit", "string"), "alt": PropSpec("alt", "string")},
        # Las rutas relativas se resuelven desde la carpeta del .janel (la del QML generado).
        fixed={"jkBase": 'Qt.resolvedUrl(".")'},
    ),
    "ProgressBar": ControlSpec(
        "JkProgressBar",
        props={
            "value": PropSpec("value", "number"),
            "max": PropSpec("to", "number"),
            "indeterminate": PropSpec("indeterminate", "bool"),
        },
    ),
    "Shortcut": ControlSpec(
        "JkShortcut",
        props={"keys": PropSpec("keys", "string")},
        events={"activate": EventSpec("onActivated")},
    ),
    "Pages": ControlSpec("JkPages"),  # stack={nav}: lo trata el compilador (como ref)
    "Sections": ControlSpec("JkPages"),  # of={secciones}: una <Pages> por sección, dentro
    "Spacer": ControlSpec("JkSpacer"),
}

QML_IMPORTS = ("QtQuick", "QtQuick.Controls", "QtQuick.Layouts", "Janel")

# Elementos base: se escriben en minúscula (los componentes y controles, en mayúscula).
BASE_ELEMENTS = tuple(tag for tag in CONTROLS if tag[:1].islower())

# Valores admitidos en los atributos de texto de los elementos base (se validan si son literales).
CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("flex", "direction"): ("row", "column", "row-reverse", "column-reverse"),
    ("flex", "align"): ("start", "center", "end", "stretch", "baseline"),
    ("flex", "justify"): ("start", "center", "end", "space-between", "space-around", "space-evenly"),
    **{(tag, "as"): ROLES for tag in ("flex", "Column", "Row")},
}


def tag_of(spec: ControlSpec) -> str:
    return spec.tag or next(tag for tag, s in CONTROLS.items() if s is spec)


def prop_spec(spec: ControlSpec, name: str) -> PropSpec | None:
    if spec.qml_type == "JkWindow":
        return spec.props.get(name)
    return spec.props.get(name) or COMMON_PROPS.get(name)


def all_props(spec: ControlSpec) -> list[str]:
    if spec.qml_type == "JkWindow":
        return sorted(spec.props)
    return sorted({*spec.props, *COMMON_PROPS})
