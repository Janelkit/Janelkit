"""Inspección de una aplicación FluxUI sin ventana visible: base para pruebas y herramientas.

    from fluxui.inspect import mount

    def test_contador():
        with mount("src/App.flux") as app:
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
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

# Tipos QML de FluxUI -> nombre del elemento en la plantilla.
_TAGS = {
    "FxWindow": "Window", "FxColumn": "Column", "FxRow": "Row", "FxScroll": "Scroll", "FxList": "List",
    "FxText": "Text", "FxButton": "Button", "FxTextField": "TextField", "FxTextArea": "TextArea",
    "FxCheckBox": "Checkbox", "FxSwitch": "Switch", "FxSlider": "Slider", "FxSelect": "Select",
    "FxRadioGroup": "RadioGroup", "FxTabs": "Tabs", "FxImage": "Image", "FxProgressBar": "ProgressBar",
    "FxShortcut": "Shortcut", "FxSpacer": "Spacer",
}  # fmt: skip


class InspectError(AssertionError):
    """Un elemento no se encontró o no admite la acción pedida."""


def _tag(item: Any) -> str:
    name = item.metaObject().className()
    for qml_type, tag in _TAGS.items():
        if name == qml_type or name.startswith(qml_type + "_"):
            return tag
    name = name.split("_QMLTYPE")[0].split("_QML_")[0]
    # Raíz de un componente: el tipo se llama como su archivo («Card.flux», o «Card.flux.r3»
    # tras recargas de flux dev).
    return name.split(".flux")[0]


class Element:
    """Un elemento de la vista. `item` es el objeto Qt Quick (interfaz de Qt, no de FluxUI)."""

    def __init__(self, app: "MountedApp", item: Any):
        self._app = app
        self.item = item

    def __repr__(self) -> str:
        label = self.text or self.id
        return f"<{self.tag}{f' {label!r}' if label else ''}>"

    # -- lectura ------------------------------------------------------------
    @property
    def tag(self) -> str:
        """Nombre del elemento en la plantilla (`Button`, `Text`…) o del tipo QML propio."""
        return _tag(self.item)

    @property
    def id(self) -> str:
        return self.item.objectName()

    @property
    def text(self) -> str | None:
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
        tag = self.tag
        if tag in ("TextField", "TextArea"):
            return self.item.property("text")
        if tag in ("Checkbox", "Switch"):
            return self.item.property("checked")
        if tag == "Select":
            return self.item.property("currentValue")
        if tag == "RadioGroup":
            return self.item.property("fxCurrent")
        if tag == "Tabs":
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

    # -- acciones -----------------------------------------------------------
    def click(self) -> "Element":
        """Pulsa un botón, una casilla/interruptor (la alterna) o una caja con on:click."""
        tag = self.tag
        self._require_enabled("click")
        if tag in ("Checkbox", "Switch"):
            return self.check(not self.item.property("checked"))
        if tag == "Button":
            press(self.item)
        elif tag == "Shortcut":
            self._invoke("activated")
        else:
            # Como un clic real: lo recibe el contenedor más cercano con on:click (una fila, una tarjeta).
            target = self.item
            while target is not None and target.property("fxClickable") is not True:
                target = target.parentItem()
            if target is None:
                raise InspectError(f"{self!r} no se puede pulsar (ni él ni sus contenedores tienen on:click)")
            _invoke(target, "clicked")
        return self._settle()

    def type(self, text: str) -> "Element":
        """Sustituye el texto de un TextField o TextArea como si lo escribiera el usuario."""
        self._require(("TextField", "TextArea"), "type")
        self._require_enabled("type")
        self.item.setProperty("text", text)
        if self.tag == "TextField":
            self._invoke("textEdited")
        return self._settle()

    def submit(self) -> "Element":
        """Pulsa Intro en un TextField (on:submit)."""
        self._require(("TextField",), "submit")
        self._invoke("accepted")
        return self._settle()

    def check(self, checked: bool = True) -> "Element":
        """Marca o desmarca una casilla o interruptor."""
        self._require(("Checkbox", "Switch"), "check")
        self._require_enabled("check")
        if bool(self.item.property("checked")) != checked:
            self._invoke("toggle")
            self._invoke("toggled")
        return self._settle()

    def slide(self, value: float) -> "Element":
        """Mueve un Slider a `value`."""
        self._require(("Slider",), "slide")
        self.item.setProperty("value", value)
        self._invoke("moved")
        return self._settle()

    def choose(self, option: Any) -> "Element":
        """Elige una opción (por valor o por texto) en Select, RadioGroup o Tabs."""
        tag = self._require(("Select", "RadioGroup", "Tabs"), "choose")
        self._require_enabled("choose")
        if tag == "Select":
            from PySide6.QtCore import Q_ARG

            for i, (label, value) in enumerate(_options(self.item.property("options"))):
                if option in (value, label):
                    self.item.setProperty("currentIndex", i)
                    self._invoke("activated", Q_ARG(int, i))
                    return self._settle()
        else:
            kind = "QQuickRadioButton" if tag == "RadioGroup" else "QQuickTabButton"
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

    # -- utilidades -----------------------------------------------------------
    def _tab_value(self) -> Any:
        options = _options(self.item.property("options"))
        index = self.item.property("currentIndex")
        return options[index][1] if 0 <= index < len(options) else None

    def _require(self, tags: tuple[str, ...], action: str) -> str:
        if self.tag not in tags:
            raise InspectError(f"{self!r} no admite {action}() (solo {', '.join(tags)})")
        return self.tag

    def _require_enabled(self, action: str) -> None:
        if not self.enabled:
            raise InspectError(f"{self!r} está desactivado: el usuario no podría hacer {action}()")

    def _invoke(self, method: str, *args: Any) -> None:
        _invoke(self.item, method, *args)

    def _settle(self) -> "Element":
        self._app.process()
        return self


def _options(options: Any) -> list[tuple[str, Any]]:
    """(texto, valor) de las opciones, con las mismas reglas que Fx.options en QML."""
    if hasattr(options, "toVariant"):  # QJSValue (PySide6 < 6.8)
        options = options.toVariant()
    out = []
    for o in options or []:
        if isinstance(o, dict) and "label" in o:
            out.append((str(o["label"]), o.get("value", o["label"])))
        else:
            out.append((str(o), o))
    return out


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


def _invoke(item: Any, method: str, *args: Any) -> None:
    from PySide6.QtCore import QMetaObject

    if not QMetaObject.invokeMethod(item, method, *args):
        raise InspectError(f"no se pudo invocar {method} en {item.metaObject().className()}")


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
        return [
            Element(self, i) for i in self._walk(root)
            if _tag(i) in _TAGS.values() or not i.metaObject().className().startswith("QQuick")
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
        """Elementos que cumplen todos los criterios dados."""
        out = []
        for el in self.elements():
            if visible_only and not el.visible:
                continue
            if tag is not None and el.tag != tag:
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
        found = self.find_all(tag, **criteria)
        if len(found) != 1:
            what = ", ".join([*([f"tag={tag!r}"] if tag else []), *(f"{k}={v!r}" for k, v in criteria.items())])
            raise InspectError(f"se esperaba un elemento con {what}; hay {len(found)}: {found[:5]}")
        return found[0]

    def texts(self) -> list[str]:
        """Textos visibles de los elementos <Text>, en orden de lectura (de arriba abajo)."""
        from PySide6.QtCore import QPointF

        labels = [el.item for el in self.find_all("Text")]
        labels.sort(key=lambda i: (round(i.mapToScene(QPointF(0, 0)).y()), i.mapToScene(QPointF(0, 0)).x()))
        return [i.property("text") for i in labels]

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

    # -- notificaciones y diálogos -----------------------------------------------
    def notifications(self) -> list[dict[str, str]]:
        """Notificaciones enviadas con `notify` (`{"title", "message"}`), de la más antigua a la más reciente."""
        from . import notifications

        return notifications.sent()

    def dialogs(self) -> list[Any]:
        from . import dialogs

        return dialogs.pending()

    def answer_dialog(self, result: Any = True) -> None:
        """Responde al diálogo abierto: una ruta (archivos), True/False (aceptar/cancelar)."""
        from PySide6.QtCore import Q_ARG, QUrl

        pending = self.dialogs()
        if not pending:
            raise InspectError("no hay ningún diálogo abierto")
        dialog = pending[-1]
        if result is False or result is None:
            _invoke(dialog, "reject")
        elif isinstance(result, (str, Path)):
            prop = "selectedFolder" if dialog.metaObject().className().startswith("QQuickFolderDialog") else "selectedFile"
            dialog.setProperty(prop, QUrl.fromLocalFile(str(Path(result).resolve())))
            _invoke(dialog, "done", Q_ARG(int, 1))
        elif dialog.property("buttons") is not None and dialog.metaObject().className().startswith("QQuickMessageDialog"):
            _invoke(dialog, "done", Q_ARG(int, 0x400))  # Aceptar
        else:
            _invoke(dialog, "done", Q_ARG(int, 1))
        self.wait(0.01)

    # -- internos -------------------------------------------------------------
    @staticmethod
    def _walk(root: Any) -> list[Any]:
        out, stack = [], [root]
        while stack:
            item = stack.pop()
            out.append(item)
            stack.extend(reversed(item.childItems()))
        return out


@contextmanager
def mount(entry: str | os.PathLike[str], headless: bool = True) -> Iterator[MountedApp]:
    """Compila y monta `entry` (p. ej. "src/App.flux"); lo desmonta al salir del bloque.

    Con `headless=True` (por defecto) y si aún no existe la aplicación Qt, usa
    la plataforma `offscreen`: no se muestra ninguna ventana.
    """
    from PySide6.QtGui import QGuiApplication

    if headless and QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from .compiler import compile_file
    from .qt_backend.application import Application

    path = Path(entry).resolve()
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    application = Application.current or Application([])
    mounted = application.mount(compile_file(path))
    app = MountedApp(application, mounted)
    app.process()
    try:
        yield app
    finally:
        if mounted in application.mounted:
            application.unmount(mounted)
        application.process_events()
