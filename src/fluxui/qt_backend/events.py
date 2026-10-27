"""Eventos de `<flex>` con propagación (on:pointerdown, on:keydown, on:wheel…).

Un filtro en cada ventana ve los eventos del ratón, la rueda y el teclado *antes*
que Qt Quick. Busca los elementos afectados (los que están bajo el puntero, o el
que tiene el foco) y llama a sus manejadores de Python de dentro afuera, como en
la web. Si alguno llama a `event.stop()`, el evento no sigue hacia fuera; si llama
a `event.prevent()`, el filtro se queda el evento y Qt Quick no lo recibe (no hay
clic, ni desplazamiento, ni texto escrito).

Los manejadores se ejecutan en el momento, en el hilo de la interfaz: por eso
`prevent()` y `stop()` funcionan sin JavaScript.

`on:click` no pasa por el filtro: lo emite el propio `<flex>` (FxBox.qml), con lo
que un control de Qt que se queda el clic (un `<Button>` dentro de una fila) sigue
impidiendo el clic de la fila, como hasta ahora.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QTimer, Slot
from PySide6.QtGui import QGuiApplication, QPointingDevice

from ..events import FocusEvent, KeyEvent, PointerEvent, ResizeEvent, WheelEvent

from shiboken6 import Shiboken


def _key(obj: QObject) -> int:
    return Shiboken.getCppPointer(obj)[0]


def _alive(obj: Any) -> bool:
    return obj is not None and Shiboken.isValid(obj)


POINTER = ("pointerdown", "pointerup", "pointermove", "dblclick", "contextmenu", "wheel")
HOVER = ("pointerenter", "pointerleave")
KEYS = ("keydown", "keyup")
ROUTED = (*POINTER, *HOVER, *KEYS, "focus", "blur", "resize", "click")

_BUTTONS = {
    Qt.MouseButton.LeftButton: "left",
    Qt.MouseButton.RightButton: "right",
    Qt.MouseButton.MiddleButton: "middle",
}
_KEY_NAMES = {
    Qt.Key.Key_Return: "Enter", Qt.Key.Key_Enter: "Enter", Qt.Key.Key_Escape: "Escape",
    Qt.Key.Key_Tab: "Tab", Qt.Key.Key_Backtab: "Tab", Qt.Key.Key_Backspace: "Backspace",
    Qt.Key.Key_Delete: "Delete", Qt.Key.Key_Insert: "Insert", Qt.Key.Key_Home: "Home",
    Qt.Key.Key_End: "End", Qt.Key.Key_PageUp: "PageUp", Qt.Key.Key_PageDown: "PageDown",
    Qt.Key.Key_Left: "ArrowLeft", Qt.Key.Key_Right: "ArrowRight", Qt.Key.Key_Up: "ArrowUp",
    Qt.Key.Key_Down: "ArrowDown", Qt.Key.Key_Shift: "Shift", Qt.Key.Key_Control: "Control",
    Qt.Key.Key_Alt: "Alt", Qt.Key.Key_Meta: "Meta", Qt.Key.Key_CapsLock: "CapsLock",
    Qt.Key.Key_Menu: "ContextMenu", Qt.Key.Key_Space: " ",
    **{getattr(Qt.Key, f"Key_F{n}"): f"F{n}" for n in range(1, 13)},
}  # fmt: skip


def _key_names(key: int, text: str) -> tuple[str, str]:
    """(key, code) como en la web."""
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        letter = chr(key)
        return (text if text.isprintable() and text else letter.lower()), f"Key{letter}"
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return (text or chr(key)), f"Digit{chr(key)}"
    if key in _KEY_NAMES:
        name = _KEY_NAMES[key]
        return name, "Space" if name == " " else name
    if text and text.isprintable():
        return text, ""
    return "Unidentified", ""


def _modifiers(mods: Any) -> dict[str, bool]:
    return {
        "ctrl": bool(mods & Qt.KeyboardModifier.ControlModifier),
        "shift": bool(mods & Qt.KeyboardModifier.ShiftModifier),
        "alt": bool(mods & Qt.KeyboardModifier.AltModifier),
        "meta": bool(mods & Qt.KeyboardModifier.MetaModifier),
    }


@dataclass
class _Listener:
    item: Any  # QQuickItem
    bridge: Any  # puente de la plantilla (fx)
    handlers: dict[str, str]  # tipo -> id del manejador

    def call(self, kind: str, event: Any) -> None:
        self.bridge._owner.bridge_invoke(self.handlers[kind], [event])

    @property
    def alive(self) -> bool:
        return _alive(self.item)


class EventRouter(QObject):
    def __init__(self) -> None:
        super().__init__()
        # Sin conectar a `destroyed` (PySide puede caerse al destruir el motor de QML): lo
        # que muere se descubre al usarlo, y cada cierto número de registros se limpia.
        self._listeners: dict[int, _Listener] = {}
        self._counts: Counter[str] = Counter()
        self._registered = 0
        self._inside: list[_Listener] = []  # bajo el puntero (on:pointerenter/leave)
        self._reason = "code"
        self._click_stopped = False
        self._resized: dict[int, _Listener] = {}

    # -- registro (desde FxBox.qml) ------------------------------------------
    @Slot(QObject)
    def listen(self, item: Any, watch: bool = True) -> None:
        on = item.property("fxOn")
        if hasattr(on, "toVariant"):
            on = on.toVariant()
        handlers = {str(k): str(v) for k, v in dict(on or {}).items()}
        key = _key(item)
        if not handlers:
            return
        bridge = item.property("fxBridge")
        old = self._listeners.get(key)
        if old is not None:
            # El mismo objeto, ya registrado. Ojo: un objeto nuevo en la dirección de uno
            # destruido puede llegar con el mismo envoltorio de Python; por eso se comparan
            # también sus manejadores.
            if old.alive and old.item is item and old.handlers == handlers and old.bridge is bridge:
                return
            self._forget(key)
        listener = _Listener(item, bridge, handlers)
        self._listeners[key] = listener
        self._counts.update(handlers.keys())
        self._registered += 1
        if self._registered % 256 == 0:
            for k in [k for k, entry in self._listeners.items() if not entry.alive]:
                self._forget(k)
        if watch:  # desde una entrega de eventos, la ventana ya se vigila
            self._watch(item.window())
        item.windowChanged.connect(self._watch)
        if "focus" in handlers or "blur" in handlers:
            item.activeFocusChanged.connect(lambda focused, l=listener: self._focus(l, focused))
        if "resize" in handlers:
            item.widthChanged.connect(lambda *_, k=key: self._resize(k))
            item.heightChanged.connect(lambda *_, k=key: self._resize(k))

    def _forget(self, key: int) -> None:
        listener = self._listeners.pop(key, None)
        if listener is not None:
            self._counts.subtract(listener.handlers.keys())
            self._inside = [entry for entry in self._inside if entry is not listener]
            self._resized.pop(key, None)

    def _watch(self, window: Any) -> None:
        if window is not None:
            window.installEventFilter(self)  # instalarlo otra vez no lo duplica

    # -- on:click (lo emite FxBox) -------------------------------------------
    @Slot(QObject, float, float, int)
    def click(self, item: Any, x: float, y: float, button: int) -> None:
        """Un clic (ratón) o una activación con el teclado (x < 0) en un `<flex>` con on:click."""
        keyboard = x < 0
        chain = [item]
        if keyboard:  # el ratón ya avisa a cada contenedor con on:click; el teclado, no
            parent = item.parentItem()
            while parent is not None:
                chain.append(parent)
                parent = parent.parentItem()
        for target in chain:
            # Sin registro previo: lo que escucha on:click lo dice el propio elemento (fxOn).
            on = target.property("fxOn")
            if hasattr(on, "toVariant"):
                on = on.toVariant()
            if not isinstance(on, dict) or "click" not in on or self._click_stopped:
                continue
            listener = _Listener(target, target.property("fxBridge"), {"click": str(on["click"])})
            local = QPointF(target.width() / 2, target.height() / 2) if keyboard else target.mapFromItem(item, QPointF(x, y))
            scene = target.mapToScene(local)
            event = PointerEvent(
                "click",
                x=local.x(),
                y=local.y(),
                window_x=scene.x(),
                window_y=scene.y(),
                button="left" if keyboard else _BUTTONS.get(Qt.MouseButton(button), "left"),
                pointer="keyboard" if keyboard else "mouse",
                **_modifiers(QGuiApplication.keyboardModifiers()),
            )
            listener.call("click", event)
            if event.stopped:
                # Los contenedores de fuera reciben el mismo clic justo después (en esta misma
                # entrega de Qt): se ignora hasta que vuelva el bucle de eventos.
                self._click_stopped = True
                QTimer.singleShot(0, self._unstop_click)
                break

    def _unstop_click(self) -> None:
        self._click_stopped = False

    # -- filtro de la ventana -------------------------------------------------
    def eventFilter(self, window: QObject, event: QEvent) -> bool:  # noqa: N802 - API de Qt
        kind = event.type()
        T = QEvent.Type
        if kind == T.MouseMove:
            return self._move(window, event)
        if kind in (T.MouseButtonPress, T.MouseButtonDblClick):
            self._set_reason("click")
            prevented = self._pointer(window, event, "pointerdown")
            if kind == T.MouseButtonDblClick:
                prevented = self._pointer(window, event, "dblclick") or prevented
            return prevented
        if kind == T.MouseButtonRelease:
            prevented = self._pointer(window, event, "pointerup")
            if event.button() == Qt.MouseButton.RightButton:
                prevented = self._pointer(window, event, "contextmenu") or prevented
            return prevented
        if kind == T.Wheel:
            return self._wheel(window, event)
        if kind in (T.KeyPress, T.KeyRelease):
            return self._keyboard(window, event, "keydown" if kind == T.KeyPress else "keyup")
        if kind == T.Leave:
            self._hover([])
        return False

    def _set_reason(self, reason: str) -> None:
        # El foco que cambie mientras Qt entrega este evento cambia «por» él.
        self._reason = reason
        QTimer.singleShot(0, self._reset_reason)

    def _reset_reason(self) -> None:
        self._reason = "code"

    def _chain_at(self, window: Any, pos: QPointF) -> list[Any]:
        """Elementos bajo el punto, del más profundo al más externo."""
        items = []
        item = window.contentItem()
        while item is not None:
            items.append(item)
            local = item.mapFromScene(pos)
            child = item.childAt(local.x(), local.y())
            if child is not None and child.property("fxDecoration") is True:
                child = self._scan(item, local)
            item = child
        items.reverse()
        return items

    @staticmethod
    def _scan(item: Any, local: QPointF) -> Any:
        """Como childAt, sin las decoraciones de una caja (bordes por lado, contorno)."""
        for child in reversed(item.childItems()):
            if not child.isVisible() or child.property("fxDecoration") is True:
                continue
            p = child.mapFromItem(item, local)
            if 0 <= p.x() < child.width() and 0 <= p.y() < child.height():
                return child
        return None

    def _get(self, item: Any) -> _Listener | None:
        key = _key(item)
        listener = self._listeners.get(key)
        if listener is None or (listener.alive and listener.item is item):
            return listener
        # El registro es de un objeto ya destruido que ocupaba la misma dirección (PySide
        # puede reutilizar su envoltorio): vale lo que dice el objeto que hay ahora.
        self._forget(key)
        if _alive(item) and item.property("fxListen") is True:
            self.listen(item, watch=False)
            return self._listeners.get(key)
        return None

    def _bubble(self, chain: list[Any], kind: str, make: Callable[[Any], Any]) -> bool:
        prevented = False
        for item in chain:
            listener = self._get(item)
            if listener is None or kind not in listener.handlers or not item.isEnabled():
                continue
            if item.property("fxPointerEvents") is False and kind in POINTER:
                continue
            event = make(item)
            listener.call(kind, event)
            prevented = prevented or event.prevented
            if event.stopped:
                break
        return prevented

    def _pointer_event(self, kind: str, item: Any, event: Any, pos: QPointF, button: str | None) -> PointerEvent:
        local = item.mapFromScene(pos)
        buttons = tuple(name for b, name in _BUTTONS.items() if event.buttons() & b)
        device = event.pointingDevice()
        ptype = device.pointerType() if device is not None else None
        pointer = {QPointingDevice.PointerType.Finger: "touch", QPointingDevice.PointerType.Pen: "pen"}.get(ptype, "mouse")
        return PointerEvent(
            kind,
            x=local.x(),
            y=local.y(),
            window_x=pos.x(),
            window_y=pos.y(),
            button=button,
            buttons=buttons,
            pointer=pointer,
            clicks=2 if kind == "dblclick" else 1,
            **_modifiers(event.modifiers()),
        )

    def _pointer(self, window: Any, event: Any, kind: str) -> bool:
        if self._counts[kind] <= 0:
            return False
        pos = event.scenePosition()
        button = _BUTTONS.get(event.button())
        chain = self._chain_at(window, pos)
        return self._bubble(chain, kind, lambda item: self._pointer_event(kind, item, event, pos, button))

    def _move(self, window: Any, event: Any) -> bool:
        moving = self._counts["pointermove"] > 0
        hovering = self._counts["pointerenter"] > 0 or self._counts["pointerleave"] > 0
        if not (moving or hovering):
            return False
        pos = event.scenePosition()
        chain = self._chain_at(window, pos)
        if hovering:
            inside = [entry for entry in map(self._get, chain) if entry is not None]
            self._hover([entry for entry in inside if set(entry.handlers) & set(HOVER)], event, pos)
        if moving:
            return self._bubble(chain, "pointermove", lambda item: self._pointer_event("pointermove", item, event, pos, None))
        return False

    def _hover(self, inside: list[_Listener], event: Any = None, pos: QPointF | None = None) -> None:
        """pointerenter/pointerleave: sin propagación; primero salen los de dentro, luego entran los de fuera."""
        before, self._inside = [entry for entry in self._inside if entry.alive], inside
        for listener in before:
            if listener not in inside and "pointerleave" in listener.handlers:
                self._hover_event(listener, "pointerleave", event, pos)
        for listener in reversed(inside):
            if listener not in before and "pointerenter" in listener.handlers:
                self._hover_event(listener, "pointerenter", event, pos)

    def _hover_event(self, listener: _Listener, kind: str, event: Any, pos: QPointF | None) -> None:
        if event is None or pos is None:
            listener.call(kind, PointerEvent(kind))
        else:
            listener.call(kind, self._pointer_event(kind, listener.item, event, pos, None))

    def _wheel(self, window: Any, event: Any) -> bool:
        if self._counts["wheel"] <= 0:
            return False
        pos = event.scenePosition()
        pixels = event.pixelDelta()
        if not pixels.isNull():
            dx, dy = -pixels.x(), -pixels.y()
        else:  # un paso de rueda (120) son unos 100 px, como en los navegadores
            angle = event.angleDelta()
            dx, dy = -angle.x() / 1.2, -angle.y() / 1.2

        def make(item: Any) -> WheelEvent:
            local = item.mapFromScene(pos)
            return WheelEvent("wheel", dx=dx, dy=dy, x=local.x(), y=local.y(), **_modifiers(event.modifiers()))

        return self._bubble(self._chain_at(window, pos), "wheel", make)

    def _keyboard(self, window: Any, event: Any, kind: str) -> bool:
        if kind == "keydown" and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self._set_reason("tab")
        menu = kind == "keyup" and event.key() == Qt.Key.Key_Menu and self._counts["contextmenu"] > 0
        if self._counts[kind] <= 0 and not menu:
            return False
        chain = []
        item = window.activeFocusItem()
        while item is not None:
            chain.append(item)
            item = item.parentItem()
        key, code = _key_names(event.key(), event.text())

        def make(item: Any) -> KeyEvent:
            return KeyEvent(kind, key=key, code=code, text=event.text(), repeat=event.isAutoRepeat(), **_modifiers(event.modifiers()))

        prevented = self._bubble(chain, kind, make) if self._counts[kind] > 0 else False
        if menu:  # la tecla de menú abre el menú contextual del elemento con el foco
            prevented = self._bubble(chain, "contextmenu", self._keyboard_pointer) or prevented
        return prevented

    @staticmethod
    def _keyboard_pointer(item: Any) -> PointerEvent:
        local = QPointF(item.width() / 2, item.height() / 2)
        scene = item.mapToScene(local)
        return PointerEvent("contextmenu", x=local.x(), y=local.y(), window_x=scene.x(), window_y=scene.y(), pointer="keyboard")

    # -- foco y tamaño ---------------------------------------------------------
    def _focus(self, listener: _Listener, focused: bool) -> None:
        kind = "focus" if focused else "blur"
        if kind in listener.handlers:
            listener.call(kind, FocusEvent(kind, reason=self._reason))

    def _resize(self, key: int) -> None:
        # Ancho y alto cambian por separado: un solo on:resize cuando vuelve el bucle de eventos.
        if not self._resized:
            QTimer.singleShot(0, self._flush_resized)
        listener = self._listeners.get(key)
        if listener is not None:
            self._resized[key] = listener

    def _flush_resized(self) -> None:
        pending, self._resized = self._resized, {}
        for listener in pending.values():
            if not listener.alive:
                continue
            item = listener.item
            listener.call("resize", ResizeEvent("resize", width=item.width(), height=item.height()))


router = EventRouter()
