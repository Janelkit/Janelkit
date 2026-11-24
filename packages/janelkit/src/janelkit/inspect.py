"""Inspección de una aplicación JanelKit sin ventana visible: base para pruebas y herramientas.

    from janelkit.inspect import mount

    def test_contador():
        with mount("src/App.janel") as app:
            app.find(text="Clicks: 0").click()
            assert app.find(id="contador").text == "Clicks: 1"
            assert app.get("count") == 1

            app.find(placeholder="Tu nombre").type("Ana")
            assert "Hola, Ana" in app.texts()

            app.wait(0.1)          # deja correr tareas asíncronas un momento
            app.wait(until=lambda: not app.get("cargando"))

Las acciones imitan al usuario (emiten las mismas señales que un clic o una
tecla), así que pasan por los mismos manejadores y `bind:` que en la app real.
Esta API es pública; un plugin de pytest con más comodidades es un proyecto aparte.
"""
from __future__ import annotations

import asyncio
import functools
import os
import shutil
import sys
import tempfile
import time
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .compiler.legacy import LEGACY_TAGS

# Tipos QML de JanelKit -> nombre del elemento en la plantilla.
_TAGS = {
    "JkWindow": "window", "JkColumn": "column", "JkRow": "row", "JkScroll": "scroll", "JkList": "list",
    "JkText": "text", "JkButton": "button", "JkTextField": "textfield", "JkTextArea": "textarea",
    "JkCheckBox": "checkbox", "JkSwitch": "switch", "JkSlider": "slider", "JkSelect": "select",
    "JkRadioGroup": "radiogroup", "JkTabs": "tabs", "JkImage": "image", "JkProgressBar": "progressbar",
    "JkShortcut": "shortcut", "JkSpacer": "spacer", "JkFlex": "flex",
    "JkFlexColumn": "column", "JkFlexRow": "row", "JkQtBox": "flex",
}  # fmt: skip
# Piezas internas de JanelKit que no son elementos de la plantilla.
_INTERNAL = (
    "JkPolisher", "JkSides", "JkScroller", "JkShadow", "JkOutline", "JkTextInherit", "JkRemote", "JkBlocker",
    "JkHover", "JkTap", "JkRole", "JkTranslate", "JkTextBox", "JkTextLinks",
)


@contextmanager
def _as_user() -> Iterator[None]:
    """Para un evento real de ratón o teclado (`QTest`): un manejador `async` que lance arranca
    mientras se procesa el evento, y necesita ver el bucle de asyncio activo, como en `exec()`."""
    from .qt_backend.application import Application

    app = Application.current
    if app is None:
        yield
        return
    with app.loop_running():
        yield


def _move_pointer(window: Any, pos: Any) -> None:
    from PySide6.QtTest import QTest

    with _as_user():
        QTest.mouseMove(window, pos)


# Nombres de KeyEvent.key (como en la web) que Qt escribe de otra forma.
_KEY_NAMES = {
    "ArrowUp": "Up", "ArrowDown": "Down", "ArrowLeft": "Left", "ArrowRight": "Right",
    "PageUp": "PgUp", "PageDown": "PgDown", " ": "Space",
}  # fmt: skip


def _send_keys(window: Any, keys: str) -> None:
    """Pulsa y suelta una combinación como en <shortcut>: "Ctrl+D", "Alt+Right", "Delete".
    También acepta los nombres de `event.key` ("ArrowRight", "PageDown")."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    from PySide6.QtTest import QTest

    *mods, key = keys.split("+") if keys != "+" else ["+"]
    seq = QKeySequence("+".join([*mods, _KEY_NAMES.get(key, key)]))
    if seq.count() != 1 or seq[0].key() == Qt.Key.Key_unknown:
        raise InspectError(f"no entiendo la combinación de teclas {keys!r} (p. ej. 'Ctrl+D', 'Alt+Right', 'Delete')")
    combo = seq[0]
    with _as_user():
        QTest.keyClick(window, combo.key(), combo.keyboardModifiers())


def _use_system_fonts() -> None:
    """En Windows, la plataforma `offscreen` no busca las fuentes del sistema: sin esto, el texto
    de las capturas sale como recuadros y se mide con una fuente de reserva."""
    if sys.platform != "win32" or os.environ.get("QT_QPA_FONTDIR"):
        return
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    if fonts.is_dir():
        os.environ["QT_QPA_FONTDIR"] = str(fonts)


class InspectError(AssertionError):
    """Un elemento no se encontró o no admite la acción pedida."""


def _tag(item: Any) -> str:
    name = item.metaObject().className()
    for qml_type, tag in _TAGS.items():
        if name == qml_type or name.startswith(qml_type + "_"):
            return tag
    name = name.split("_QMLTYPE")[0].split("_QML_")[0]
    # Raíz de un componente: el tipo se llama como su archivo («Card.janel», o «Card.janel.r3»
    # tras recargas de janel dev).
    return name.split(".janel")[0]


def _kind(item: Any) -> str:
    """El elemento integrado que es `item`, aunque sea la raíz de un componente
    (un `Otra.janel` cuya raíz es `<text>` es un <text>); si no lo es, su `_tag`."""
    meta = item.metaObject()
    while meta is not None:
        name = meta.className()
        for qml_type, tag in _TAGS.items():
            if name == qml_type or name.startswith(qml_type + "_"):
                return tag
        meta = meta.superClass()
    return _tag(item)


class Element:
    """Un elemento de la vista. `item` es el objeto Qt Quick (interfaz de Qt, no de JanelKit)."""

    def __init__(self, app: "MountedApp", item: Any):
        self._app = app
        self.item = item

    def __repr__(self) -> str:
        label = self.text or self.id
        return f"<{self.tag}{f' {label!r}' if label else ''}>"

    # -- búsqueda dentro ----------------------------------------------------
    def find_all(self, tag: str | None = None, **criteria: Any) -> list["Element"]:
        """Como `MountedApp.find_all`, pero solo entre lo que hay dentro de este elemento
        (sin contarlo a él): `app.find("Tarjeta", label="Beta").find_all("button")`."""
        return self._app._search(self.item, tag, within=self, **criteria)

    def find(self, tag: str | None = None, **criteria: Any) -> "Element":
        """El único elemento dentro de este que cumple los criterios. Error si hay cero o varios.

        Sirve cuando el mismo texto o `label` aparece en varios sitios (una pestaña y un botón
        «Muestra 1»): `app.find(label="Pestañas").find(text="Muestra 1")`."""
        return self._app._one(self.find_all(tag, **criteria), tag, criteria, within=self)

    # -- lectura ------------------------------------------------------------
    @property
    def tag(self) -> str:
        """Nombre del elemento en la plantilla (`button`, `text`…) o del tipo QML propio."""
        return _tag(self.item)

    @property
    def _kind(self) -> str:
        return _kind(self.item)

    @property
    def id(self) -> str:
        return self.item.objectName()

    @property
    def text(self) -> str | None:
        """Texto que muestra el elemento (un `<text>`, un botón, una casilla). Los campos no tienen:
        lo escrito en un `<textfield>` o `<textarea>` es su `value`."""
        if self._kind in ("textfield", "textarea"):
            return None
        value = self.item.property("text")
        return value if isinstance(value, str) else None

    @property
    def label(self) -> str | None:
        """Nombre accesible (`label="..."` en la plantilla), o None."""
        from PySide6.QtQml import QQmlEngine, QQmlProperty

        context = QQmlEngine.contextForObject(self.item)
        if context is None:
            return None
        value = QQmlProperty(self.item, "Accessible.name", context).read()
        return value or None

    @property
    def value(self) -> Any:
        """Valor actual de un control (texto, marcado, número u opción elegida)."""
        tag = self._kind
        if tag in ("textfield", "textarea"):
            return self.item.property("text")
        if tag in ("checkbox", "switch"):
            return self.item.property("checked")
        if tag == "select":
            return self.item.property("currentValue")
        if tag == "radiogroup":
            return self.item.property("jkCurrent")
        if tag == "tabs":
            return self._tab_value()
        return self.item.property("value")

    @property
    def visible(self) -> bool:
        return bool(self.item.isVisible())

    @property
    def enabled(self) -> bool:
        return bool(self.item.property("enabled"))

    def prop(self, name: str) -> Any:
        """Lee una propiedad Qt del elemento (último recurso)."""
        return self.item.property(name)

    def style(self, name: str) -> Any:
        """El valor de un estilo tal como quedó aplicado (de `<style>`, `class`, `style=`, estados…),
        por su nombre CSS: `elemento.style("background")`.

        Los colores salen como `"#rrggbb"`, o `"rgba(r, g, b, a)"` si son transparentes; los
        tamaños, en píxeles; `font-weight`, como número (400, 700). `width` y `height` son el
        tamaño que tiene el elemento. `None` si el elemento no tiene ese estilo."""
        if name in ("width", "height"):
            return float(self.item.width() if name == "width" else self.item.height())
        if name not in _STYLES:
            raise InspectError(f"style({name!r}): no se puede leer; se pueden leer: {', '.join(sorted([*_STYLES, 'width', 'height']))}")
        qml = _STYLES[name]
        if qml == "jkBackground" and self.item.isWindowType():
            qml = "color"  # <window> guarda su fondo en color
        if qml.startswith("font."):
            if self.item.metaObject().indexOfProperty("font") < 0:
                return None
            font = self.item.property("font")
            return float(font.pixelSize()) if qml == "font.pixelSize" else int(font.weight().value)
        if self.item.metaObject().indexOfProperty(qml) < 0:
            return None
        value = self.item.property(qml)
        return _css_color(value) if hasattr(value, "alphaF") else float(value)

    # -- acciones -----------------------------------------------------------
    def click(self, x: float | None = None, y: float | None = None) -> "Element":
        """Pulsa un botón, una casilla/interruptor (la alterna), una pestaña, una opción de <radiogroup>
        o una caja con on:click.

        Con `x` o `y` (respecto al elemento; el que falte, en el centro) es un clic real del
        ratón en ese punto: lo recibe lo que haya allí, y on:click llega con esa posición (en
        un `<video>`, también con `image_x`/`image_y`)."""
        tag = self._kind
        self._require_enabled("click")
        if x is not None or y is not None:
            from PySide6.QtCore import Qt
            from PySide6.QtTest import QTest

            with _as_user():
                QTest.mouseClick(self._app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._point(x, y))
            return self._settle()
        if tag in ("checkbox", "switch"):
            return self.check(not self.item.property("checked"))
        if tag == "button":
            press(self.item)
        elif tag == "shortcut":
            self._invoke("activated")
        elif self.item.inherits("QQuickTabButton") or self.item.inherits("QQuickRadioButton"):
            press(self.item)  # una pestaña de <tabs> o una opción de <radiogroup>, encontrada por su texto
        else:
            # Como un clic real: lo recibe el contenedor más cercano con on:click (una fila, una tarjeta).
            target = self.item
            while target is not None and target.property("jkClickable") is not True:
                target = target.parentItem()
            if target is None:
                raise InspectError(f"{self!r} no se puede pulsar (ni él ni sus contenedores tienen on:click)")
            _invoke(target, "clicked")
        return self._settle()

    def type(self, text: str) -> "Element":
        """Sustituye el texto de un <textfield> o <textarea> como si lo escribiera el usuario."""
        self._require(("textfield", "textarea"), "type")
        self._require_enabled("type")
        self.item.setProperty("text", text)
        if self._kind == "textfield":
            self._invoke("textEdited")
        return self._settle()

    def submit(self) -> "Element":
        """Pulsa Intro en un <textfield> (on:submit)."""
        self._require(("textfield",), "submit")
        self._invoke("accepted")
        return self._settle()

    def check(self, checked: bool = True) -> "Element":
        """Marca o desmarca una casilla o interruptor."""
        self._require(("checkbox", "switch"), "check")
        self._require_enabled("check")
        if bool(self.item.property("checked")) != checked:
            self._invoke("toggle")
            self._invoke("toggled")
        return self._settle()

    def slide(self, value: float) -> "Element":
        """Mueve un <slider> a `value`."""
        self._require(("slider",), "slide")
        self.item.setProperty("value", value)
        self._invoke("moved")
        return self._settle()

    def choose(self, option: Any) -> "Element":
        """Elige una opción (por valor o por texto) en <select>, <radiogroup> o <tabs>."""
        tag = self._require(("select", "radiogroup", "tabs"), "choose")
        self._require_enabled("choose")
        if tag == "select":
            from PySide6.QtCore import Q_ARG

            for i, (label, value) in enumerate(_options(self.item.property("options"))):
                if option in (value, label):
                    self.item.setProperty("currentIndex", i)
                    self._invoke("activated", Q_ARG(int, i))
                    return self._settle()
        else:
            kind = "QQuickRadioButton" if tag == "radiogroup" else "QQuickTabButton"
            for button in self._app._walk(self.item):
                data = button.property("modelData") if button.inherits(kind) else None
                if hasattr(data, "toVariant"):  # QJSValue (según la versión de PySide6)
                    data = data.toVariant()
                if isinstance(data, dict) and option in (data.get("value"), data.get("label")):
                    press(button)  # como un clic real: marca el botón y emite clicked
                    return self._settle()
        raise InspectError(f"{self!r} no tiene la opción {option!r}")

    def focus(self) -> "Element":
        self.item.forceActiveFocus()
        return self._settle()

    def key(self, keys: str) -> "Element":
        """Da el foco al elemento y pulsa una combinación de teclas ("Ctrl+D", "Alt+Right",
        "Delete", "Escape"): llega a sus on:keydown/on:keyup y a los de sus contenedores."""
        self.focus()
        _send_keys(self._app.window, keys)
        return self._settle()

    def screenshot(self, path: str | os.PathLike | None = None) -> Any:
        """Captura solo este elemento: la de la ventana, recortada a su rectángulo. Ver `MountedApp.screenshot`."""
        from PySide6.QtCore import QRectF

        self._app.process()
        image = _grab(self.item.window())
        ratio = image.devicePixelRatio()
        box = self.item.mapRectToScene(QRectF(0, 0, self.item.width(), self.item.height()))
        image = image.copy(*(round(v * ratio) for v in (box.x(), box.y(), box.width(), box.height())))
        return _save(image, path)

    def double_click(self, x: float | None = None, y: float | None = None) -> "Element":
        """Doble clic real en el centro del elemento, o en (`x`, `y`) respecto a él (on:dblclick)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        self._require_enabled("double_click")
        with _as_user():
            QTest.mouseDClick(self._app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._point(x, y))
        return self._settle()

    def right_click(self, x: float | None = None, y: float | None = None) -> "Element":
        """Clic con el botón derecho en el centro del elemento, o en (`x`, `y`) respecto a él (on:contextmenu)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        self._require_enabled("right_click")
        with _as_user():
            QTest.mouseClick(self._app.window, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, self._point(x, y))
        return self._settle()

    def hover(self, x: float | None = None, y: float | None = None) -> "Element":
        """Pone el puntero del ratón sobre el centro del elemento, o en (`x`, `y`) respecto a él
        (activa sus estilos :hover; on:pointerenter y on:pointermove)."""
        from PySide6.QtCore import QPoint

        point = self._point(x, y)
        _move_pointer(self._app.window, point + QPoint(1, 1))  # ver unhover()
        _move_pointer(self._app.window, point)
        return self._settle()

    def unhover(self) -> "Element":
        """Saca el puntero del ratón de la ventana."""
        from PySide6.QtCore import QPoint

        # Dos puntos distintos: un movimiento al mismo sitio que el anterior no genera evento.
        _move_pointer(self._app.window, QPoint(-50, -50))
        _move_pointer(self._app.window, QPoint(-60, -60))
        return self._settle()

    def press(self, x: float | None = None, y: float | None = None) -> "Element":
        """Mantiene pulsado el botón del ratón sobre el elemento, en su centro o en (`x`, `y`)
        respecto a él (estilos :pressed, on:pointerdown) hasta release()."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        with _as_user():
            QTest.mousePress(self._app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._point(x, y))
        return self._settle()

    def release(self, x: float | None = None, y: float | None = None) -> "Element":
        """Suelta el botón del ratón en el centro del elemento o en (`x`, `y`) respecto a él (on:pointerup)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        with _as_user():
            QTest.mouseRelease(self._app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._point(x, y))
        return self._settle()

    def scroll_into_view(self) -> "Element":
        """Desplaza los `<scroll>` y `<list>` que lo contienen lo justo para que se vea entero
        (si no cabe, su borde de arriba). Para mirarlo o capturarlo con `screenshot()`."""
        from PySide6.QtCore import Q_ARG

        target = self.item
        parent = target.parentItem()
        while parent is not None:
            if parent.inherits("QQuickScrollView") and parent.metaObject().indexOfMethod("scrollTo(QVariant)") >= 0:
                _invoke(parent, "scrollTo", Q_ARG("QVariant", target))  # el de <scroll>, como ref.scroll_to(ref)
            elif parent.inherits("QQuickListView"):
                _show_in_flickable(parent, target)
            parent = parent.parentItem()
        return self._settle()

    def drag_to(self, target: "Element", *, x: float | None = None, y: float | None = None,
                cancel: bool = False) -> "Element":
        """Arrastra el elemento (un `<flex draggable>`) y lo suelta sobre `target`: en su
        centro, o en (`x`, `y`) respecto a él. Con `cancel=True` pulsa Escape en vez de soltar."""
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtTest import QTest

        window = self._app.window

        def end() -> QPoint:  # el destino puede estar moviéndose (una lista animada): se le sigue
            local = QPointF(target.item.width() / 2 if x is None else x, target.item.height() / 2 if y is None else y)
            return target.item.mapToScene(local).toPoint()

        start = self._point()
        with _as_user():
            QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
            self._settle()
            for i in range(1, 6):  # varios pasos: pasa la distancia de arrastre y recorre el camino
                to = end()
                QTest.mouseMove(window, start + QPoint((to.x() - start.x()) * i // 5, (to.y() - start.y()) * i // 5))
                self._settle()
            if cancel:
                QTest.keyClick(window, Qt.Key.Key_Escape)
            QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end())
        return self._settle()

    def _point(self, x: float | None = None, y: float | None = None) -> Any:
        """El punto (`x`, `y`) del elemento en la ventana; el que falte, en el centro."""
        from PySide6.QtCore import QPointF

        local = QPointF(self.item.width() / 2 if x is None else x, self.item.height() / 2 if y is None else y)
        return self.item.mapToScene(local).toPoint()

    def _center(self) -> Any:
        return self._point()

    # -- utilidades -----------------------------------------------------------
    def _tab_value(self) -> Any:
        options = _options(self.item.property("options"))
        index = self.item.property("currentIndex")
        return options[index][1] if 0 <= index < len(options) else None

    def _require(self, tags: tuple[str, ...], action: str) -> str:
        if self._kind not in tags:
            raise InspectError(f"{self!r} no admite {action}() (solo {', '.join(tags)})")
        return self._kind

    def _require_enabled(self, action: str) -> None:
        if not self.enabled:
            raise InspectError(f"{self!r} está desactivado: el usuario no podría hacer {action}()")

    def _invoke(self, method: str, *args: Any) -> None:
        _invoke(self.item, method, *args)

    def _settle(self) -> "Element":
        self._app.process()
        return self


def _options(options: Any) -> list[tuple[str, Any]]:
    """(texto, valor) de las opciones, con las mismas reglas que Jk.options en QML."""
    if hasattr(options, "toVariant"):  # QJSValue (PySide6 < 6.8)
        options = options.toVariant()
    out = []
    for o in options or []:
        if isinstance(o, dict) and "label" in o:
            out.append((str(o["label"]), o.get("value", o["label"])))
        else:
            out.append((str(o), o))
    return out


# Nombre CSS -> propiedad QML que lo guarda en los elementos del núcleo (ver compiler/css.py).
_STYLES = {
    "background": "jkBackground", "background-color": "jkBackground", "color": "jkColor",
    "border-color": "jkBorderColor", "border-width": "jkBorderWidth", "border-radius": "jkRadius",
    "opacity": "opacity", "font-size": "font.pixelSize", "font-weight": "font.weight",
}  # fmt: skip


def _css_color(color: Any) -> str:
    if color.alpha() == 255:
        return color.name()  # "#rrggbb"
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {round(color.alphaF(), 3):g})"


def _show_in_flickable(view: Any, target: Any) -> None:
    """Mueve `contentY` de una vista desplazable (una <list>) lo justo para que se vea `target`."""
    top = target.mapToItem(view.property("contentItem"), 0, 0).y()
    y, height = view.property("contentY"), view.height()
    if top < y:
        view.setProperty("contentY", top)
    elif top + target.height() > y + height:
        view.setProperty("contentY", min(top, top + target.height() - height))


def press(item: Any) -> None:
    """Pulsa un botón de Qt Quick como lo haría el usuario: marca/desmarca si es conmutable y emite clicked.

    `AbstractButton.click()` solo es invocable desde Qt 6.8; antes se reproduce con toggle() y las señales.
    """
    meta = item.metaObject()
    if meta.indexOfMethod("click()") >= 0:
        _invoke(item, "click")
        return
    if item.property("checkable") and not (item.property("autoExclusive") and item.property("checked")):
        _invoke(item, "toggle")
        if meta.indexOfSignal("toggled()") >= 0:
            _invoke(item, "toggled")
    _invoke(item, "clicked")


_extensions: dict[str, Callable[..., Any]] = {}


def add_inspector(name: str, fn: Callable[..., Any]) -> None:
    """Registra `fn(app, ...)` como `MountedApp.<name>` (lo usa `janelkit.ext.inspector`)."""
    if name.startswith("_") or name in vars(MountedApp):
        raise ValueError(f"MountedApp ya tiene {name!r} o no es un nombre válido")
    _extensions[name] = fn


def _invoke(item: Any, method: str, *args: Any) -> None:
    from PySide6.QtCore import QMetaObject

    if not QMetaObject.invokeMethod(item, method, *args):
        raise InspectError(f"no se pudo invocar {method} en {item.metaObject().className()}")


def _grab(window: Any) -> Any:
    if window is None:
        raise InspectError("el elemento no está en ninguna ventana: no se puede capturar")
    return window.grabWindow()


def _save(image: Any, path: str | os.PathLike | None) -> Any:
    if image.isNull():
        raise InspectError("la captura salió vacía (¿la ventana tiene tamaño?)")
    if path is not None and not image.save(os.fspath(path)):
        raise InspectError(f"no se pudo guardar la captura en {os.fspath(path)}")
    return image


class MountedApp:
    """Una vista montada para inspeccionarla."""

    def __init__(self, application: Any, mounted: Any):
        self.application = application
        self.mounted = mounted

    @property
    def window(self) -> Any:
        return self.mounted.root

    # -- estado ---------------------------------------------------------------
    @property
    def namespace(self) -> dict[str, Any]:
        """Variables del script del componente raíz (los `state` sin desenvolver)."""
        return self.mounted.instance.namespace

    def get(self, name: str) -> Any:
        """Valor de una variable del script raíz, desenvolviendo `state`, `computed` y props."""
        value = self.namespace[name]
        return value.value if hasattr(value, "value") and hasattr(value, "peek") else value

    def windows(self) -> list["MountedApp"]:
        """Las otras ventanas abiertas (con `open_window`), de la más antigua a la más reciente.

        Cada una se inspecciona igual que la principal: `app.windows()[-1].texts()`.
        """
        return [MountedApp(self.application, m) for m in self.application.mounted if m is not self.mounted]

    # -- búsqueda -------------------------------------------------------------
    def elements(self) -> list[Element]:
        """Elementos de la plantilla (integrados y QML propios), sin las piezas internas de cada control."""
        root = self.window.contentItem() if hasattr(self.window, "contentItem") else self.window
        return self._elements(root)

    def _elements(self, root: Any) -> list[Element]:
        return [
            Element(self, i) for i in self._walk(root)
            if _tag(i) in _TAGS.values()
            or not i.metaObject().className().startswith(("QQuick", *_INTERNAL))
        ]  # fmt: skip

    def find_all(
        self,
        tag: str | None = None,
        *,
        text: str | None = None,
        id: str | None = None,
        placeholder: str | None = None,
        label: str | None = None,
        visible_only: bool = True,
    ) -> list[Element]:
        """Elementos que cumplen todos los criterios dados.

        `tag` acepta el nombre de un componente o el elemento integrado que es su raíz:
        la raíz `<text>` de `Otra.janel` aparece con `find("Otra")` y con `find("text")`.
        Los nombres de 0.1 (`find("Text")`) aún valen, con un `DeprecationWarning`.
        Para buscar solo dentro de un elemento: `elemento.find_all(...)`.
        """
        root = self.window.contentItem() if hasattr(self.window, "contentItem") else self.window
        return self._search(root, tag, text=text, id=id, placeholder=placeholder, label=label, visible_only=visible_only)

    def _search(
        self,
        root: Any,
        tag: str | None = None,
        *,
        text: str | None = None,
        id: str | None = None,
        placeholder: str | None = None,
        label: str | None = None,
        visible_only: bool = True,
        within: Element | None = None,
    ) -> list[Element]:
        tags = (tag,)
        if tag in LEGACY_TAGS:
            warnings.warn(
                f'find("{tag}"): los elementos del núcleo se escriben en minúscula desde 0.2: find("{LEGACY_TAGS[tag]}")',
                DeprecationWarning,
                stacklevel=4 if sys._getframe(2).f_code.co_name == "find" else 3,
            )
            tags = (tag, LEGACY_TAGS[tag])
        out = []
        for el in self._elements(root):
            if within is not None and el.item is root:
                continue  # dentro de un elemento: sin contarlo a él
            if visible_only and not el.visible:
                continue
            if tag is not None and el.tag not in tags and el._kind not in tags:
                continue
            if text is not None and el.text != text:
                continue
            if id is not None and el.id != id:
                continue
            if placeholder is not None and el.prop("placeholderText") != placeholder:
                continue
            if label is not None and el.label != label:
                continue
            out.append(el)
        return out

    def find(self, tag: str | None = None, **criteria: Any) -> Element:
        """El único elemento que cumple los criterios. Error si hay cero o varios."""
        return self._one(self.find_all(tag, **criteria), tag, criteria)

    @staticmethod
    def _one(found: list[Element], tag: str | None, criteria: dict[str, Any], within: Element | None = None) -> Element:
        if len(found) != 1:
            what = ", ".join([*([f"tag={tag!r}"] if tag else []), *(f"{k}={v!r}" for k, v in criteria.items())])
            where = f" dentro de {within!r}" if within is not None else ""
            raise InspectError(f"se esperaba un elemento con {what}{where}; hay {len(found)}: {found[:5]}")
        return found[0]

    def texts(self) -> list[str]:
        """Textos visibles de los elementos <text>, en orden de lectura (de arriba abajo)."""
        from PySide6.QtCore import QPointF

        labels = [el.item for el in self.find_all("text")]
        labels.sort(key=lambda i: (round(i.mapToScene(QPointF(0, 0)).y()), i.mapToScene(QPointF(0, 0)).x()))
        return [i.property("text") for i in labels]

    def resize(self, width: int, height: int) -> None:
        """Cambia el tamaño de la ventana (en píxeles lógicos), como si el usuario la arrastrara.

        Sin pantalla no hay límite: sirve para capturar entera una vista más alta que la
        ventana. Una ventana real no puede ser mayor que la pantalla."""
        self.window.resize(int(width), int(height))
        self.process()

    def key(self, keys: str) -> None:
        """Pulsa una combinación de teclas en la ventana, sobre lo que tenga el foco
        (atajos de <shortcut>: "Ctrl+Z", "Ctrl+Shift+Z", "F5")."""
        _send_keys(self.window, keys)
        self.process()

    # -- tiempo ---------------------------------------------------------------
    def process(self) -> None:
        """Procesa los eventos pendientes de Qt (y la disposición de las listas)."""
        from shiboken6 import Shiboken

        self.application.process_events()
        if Shiboken.isValid(self.window):
            root = self.window.contentItem() if hasattr(self.window, "contentItem") else self.window
            for item in self._walk(root):
                if item.inherits("QQuickListView"):
                    _invoke(item, "forceLayout")
        self.application.process_events()

    def screenshot(self, path: str | os.PathLike | None = None) -> Any:
        """Captura la ventana como `QImage` y, si se da `path`, la guarda (el formato sale de la extensión).

        Con `headless=True` (plataforma `offscreen`) la imagen tiene la disposición y los colores,
        pero sin vídeo, y los emojis de color pueden salir como recuadros: para revisar a ojo usa `headless=False`.
        """
        self.process()
        root = self.window
        return _save(_grab(root if root.isWindowType() else root.window()), path)

    def wait(self, seconds: float = 0.0, until: Callable[[], bool] | None = None, timeout: float = 5.0) -> None:
        """Deja correr el bucle (tareas asíncronas, temporizadores) `seconds`, o hasta que `until()` sea cierto."""

        async def run() -> None:
            if until is None:
                await asyncio.sleep(seconds)
                return
            deadline = time.monotonic() + timeout
            while not until():
                if time.monotonic() > deadline:
                    raise InspectError(f"la condición no se cumplió en {timeout} s")
                await asyncio.sleep(0.01)

        self.application.run_until(run(), timeout=timeout + 1 if until else max(seconds + 1, timeout))
        self.process()

    def __getattr__(self, name: str) -> Any:
        # Métodos que añaden otros paquetes con `janelkit.ext.inspector` (p. ej. `dialogs()`).
        method = _extensions.get(name)
        if method is None:
            hint = "" if name.startswith("_") else "; si lo añade una extensión (como dialogs() de janelkit-desktop o store() de janelkit-store), impórtala"
            raise AttributeError(f"MountedApp no tiene {name!r}{hint}")
        return functools.partial(method, self)

    # -- internos -------------------------------------------------------------
    @staticmethod
    def _walk(root: Any) -> list[Any]:
        from PySide6.QtQml import qmlContext

        out, stack = [], [root]
        while stack:
            item = stack.pop()
            out.append(item)
            children = item.childItems()
            parent = item.parentItem()
            if parent is not None and parent.inherits("QQuickListView") and item is parent.property("contentItem"):
                # Filas de <list animate> que salen: ya no cuentan (índice -1), aunque se vean un momento.
                children = [c for c in children if (ctx := qmlContext(c)) is None or ctx.contextProperty("index") != -1]
            stack.extend(reversed(children))
        return out


@contextmanager
def mount(
    entry: str | os.PathLike[str], headless: bool = True, size: tuple[int, int] | None = None
) -> Iterator[MountedApp]:
    """Compila y monta `entry` (p. ej. "src/App.janel"); lo desmonta al salir del bloque.

    `size=(ancho, alto)` cambia el tamaño de la ventana al montarla (`MountedApp.resize`).

    Con `headless=True` (por defecto) y si aún no existe la aplicación Qt, usa
    la plataforma `offscreen`: no se muestra ninguna ventana. Al salir se olvidan los
    módulos de la carpeta de la app: otra app con un `services/` o `components/` del
    mismo nombre se puede montar después en el mismo proceso.
    """
    from PySide6.QtGui import QGuiApplication

    if headless and QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _use_system_fonts()
    from . import session
    from .compiler import compile_file
    from .qt_backend.application import Application

    path = Path(entry).resolve()
    added = str(path.parent) not in sys.path
    if added:
        sys.path.insert(0, str(path.parent))
    before = set(sys.modules)
    application = Application.current or Application([])
    # Una sesión por montaje, con una carpeta de datos temporal: los paquetes (persisted, stores)
    # no tocan los datos reales del usuario, y una prueba no ve lo que dejó la anterior.
    data = Path(tempfile.mkdtemp(prefix="janelkit-data-"))
    session.start(path, data)
    try:
        mounted = application.mount(compile_file(path))
        app = MountedApp(application, mounted)
        app.process()
        if size is not None:
            app.resize(*size)
        try:
            yield app
        finally:
            if mounted in application.mounted:
                application.unmount(mounted)
            application.process_events()
    finally:
        session.end()
        shutil.rmtree(data, ignore_errors=True)
        if added and str(path.parent) in sys.path:
            sys.path.remove(str(path.parent))
        _forget_modules(path.parent, set(sys.modules) - before)


def _forget_modules(folder: Path, names: set[str]) -> None:
    """Quita de `sys.modules` los módulos (y paquetes) importados desde `folder`."""
    for name in names:
        module = sys.modules.get(name)
        places = [getattr(module, "__file__", None) or "", *(getattr(module, "__path__", None) or [])]
        if any(p and Path(p).resolve().is_relative_to(folder) for p in places):
            del sys.modules[name]
