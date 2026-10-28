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

Arrastrar y soltar también va por el filtro: al pulsar sobre un `<flex draggable>` y
moverse más que la distancia de arrastre del sistema, el arrastre empieza (on:dragstart)
y Qt Quick deja de recibir ese puntero (no hay clic al soltar). Una copia de la caja
sigue al puntero; la caja con on:drop que hay debajo se marca (:drag-over) y recibe
on:dragover y, al soltar, on:drop. Escape lo cancela. Cerca del borde de una zona con
desplazamiento (<List>, <Scroll>, overflow: auto), esta se desplaza sola. Todo dentro
de una ventana.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QEvent, QObject, QPointF, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QGuiApplication, QPointingDevice
from PySide6.QtQml import QQmlComponent, qmlEngine

from ..events import DragEvent, FocusEvent, KeyEvent, PointerEvent, ResizeEvent, WheelEvent

from shiboken6 import Shiboken


def _key(obj: QObject) -> int:
    return Shiboken.getCppPointer(obj)[0]


def _alive(obj: Any) -> bool:
    return obj is not None and Shiboken.isValid(obj)


POINTER = ("pointerdown", "pointerup", "pointermove", "dblclick", "contextmenu", "wheel")
HOVER = ("pointerenter", "pointerleave")
KEYS = ("keydown", "keyup")
DRAG = ("dragstart", "dragover", "drop", "dragend")
ROUTED = (*POINTER, *HOVER, *KEYS, *DRAG, "focus", "blur", "resize", "click")

# Desplazamiento automático al arrastrar: a menos de EDGE px del borde de una zona con
# desplazamiento, esta avanza hasta SPEED px por paso de 16 ms (más cuanto más cerca).
_EDGE = 40
_SPEED = 18

# La copia que sigue al puntero: una imagen de la caja, tomada al empezar.
_GHOST_QML = b"""import QtQuick
ShaderEffectSource {
    property bool fxDecoration: true  // events.py no la cuenta como elemento bajo el puntero
    live: false
    enabled: false
    opacity: 0.85
    z: 1000000
}
"""

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
class _Drag:
    source: Any  # el <flex draggable>
    window: Any
    data: Any = None
    offset: QPointF | None = None  # del puntero a la esquina de la caja
    ghost: Any = None
    zone: Any = None  # caja con on:drop bajo el puntero (:drag-over)
    pos: QPointF | None = None  # último punto del puntero (en la escena)
    scrolls: list = field(default_factory=list)  # [(Flickable, dx, dy)] que se desplazan solos


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
        self._press: tuple[Any, QPointF] | None = None  # <flex draggable> pulsado, y dónde
        self._drag: _Drag | None = None
        self._ghosts: dict[int, QQmlComponent] = {}  # por motor de QML
        self._autoscroll = QTimer(self)
        self._autoscroll.setInterval(16)
        self._autoscroll.timeout.connect(self._scroll_step)

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
        if self._drag is not None or self._press is not None:
            handled = self._dragging(window, event, kind)
            if handled is not None:
                return handled
        if kind == T.MouseMove:
            return self._move(window, event)
        if kind in (T.MouseButtonPress, T.MouseButtonDblClick):
            self._set_reason("click")
            if kind == T.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._press_draggable(window, event)
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

    # -- arrastrar y soltar ----------------------------------------------------
    def _press_draggable(self, window: Any, event: Any) -> None:
        if self._counts["drop"] <= 0 and self._counts["dragstart"] <= 0:
            return
        pos = event.scenePosition()
        for item in self._chain_at(window, pos):
            if item.property("fxDraggable") is True and item.isEnabled():
                self._press = (item, pos)
                return

    def _dragging(self, window: Any, event: Any, kind: QEvent.Type) -> bool | None:
        """El filtro con una caja pulsada o arrastrándose. None: lo de siempre."""
        T = QEvent.Type
        if self._drag is None:  # pulsada: ¿empieza el arrastre?
            if kind == T.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                source, start = self._press
                pos = event.scenePosition()
                if (pos - start).manhattanLength() < QGuiApplication.styleHints().startDragDistance():
                    return None
                self._press = None
                if _alive(source) and self._start_drag(window, source, start, event):
                    return True
                return None
            if kind in (T.MouseButtonRelease, T.MouseButtonPress) or (kind == T.MouseMove and not event.buttons()):
                self._press = None
            return None
        if kind == T.MouseMove:
            self._drag_move(event.scenePosition(), event)
            return True
        if kind == T.MouseButtonRelease:
            self._drop(event.scenePosition(), event)
            return True
        if kind in (T.MouseButtonPress, T.MouseButtonDblClick):
            return True
        if kind == T.KeyPress and event.key() == Qt.Key.Key_Escape:
            self._end_drag(dropped=False)
            return True
        if kind in (T.KeyPress, T.KeyRelease):
            return True  # el teclado no hace nada mientras se arrastra
        return None

    def _drag_event(self, kind: str, item: Any, pos: QPointF, event: Any = None) -> DragEvent:
        local = item.mapFromScene(pos)
        mods = _modifiers(event.modifiers() if event is not None else QGuiApplication.keyboardModifiers())
        data = self._drag.data if self._drag is not None else None
        return DragEvent(kind, x=local.x(), y=local.y(), window_x=pos.x(), window_y=pos.y(), button="left",
                         data=data, **mods)

    @staticmethod
    def _ancestors(item: Any) -> list[Any]:
        chain = []
        while item is not None:
            chain.append(item)
            item = item.parentItem()
        return chain

    def _start_drag(self, window: Any, source: Any, start: QPointF, event: Any) -> bool:
        data = None
        for item in self._ancestors(source):
            listener = self._get(item)
            if listener is None or "dragstart" not in listener.handlers:
                continue
            local = item.mapFromScene(start)
            ev = DragEvent("dragstart", x=local.x(), y=local.y(), window_x=start.x(), window_y=start.y(),
                           button="left", data=data, **_modifiers(event.modifiers()))
            listener.call("dragstart", ev)
            data = ev.data
            if ev.prevented:
                return False
            if ev.stopped:
                break
        # Qt Quick deja de seguir este puntero: lo que lo tenía (un clic a medias) se cancela.
        for point in event.points():
            event.setExclusiveGrabber(point, None)
            event.clearPassiveGrabbers(point)
        self._drag = _Drag(source, window, data, offset=start - source.mapToScene(QPointF(0, 0)))
        self._drag.ghost = self._make_ghost(source)
        source.setProperty("fxDragging", True)
        self._drag_move(event.scenePosition(), event)
        return True

    def _make_ghost(self, source: Any) -> Any:
        engine = qmlEngine(source)
        if engine is None:
            return None
        comp = self._ghosts.get(id(engine))
        if comp is None:
            comp = QQmlComponent(engine)
            comp.setData(QByteArray(_GHOST_QML), QUrl("fluxui-drag-ghost.qml"))
            self._ghosts[id(engine)] = comp
        ghost = comp.create()
        if ghost is None:
            return None
        ghost.setParentItem(self._drag.window.contentItem())
        ghost.setProperty("sourceItem", source)
        ghost.setWidth(source.width())
        ghost.setHeight(source.height())
        return ghost

    def _drag_move(self, pos: QPointF, event: Any) -> None:
        drag = self._drag
        drag.pos = pos
        if drag.ghost is not None and _alive(drag.ghost):
            drag.ghost.setPosition(drag.window.contentItem().mapFromScene(pos - drag.offset))
        chain = self._chain_at(drag.window, pos)
        drag.scrolls = [s for item in chain if item.inherits("QQuickFlickable") and (s := self._edge(item, pos))]
        if drag.scrolls and not self._autoscroll.isActive():
            self._autoscroll.start()
        zone = None
        for item in chain:
            listener = self._get(item)
            if listener is not None and "drop" in listener.handlers and item.isEnabled():
                zone = item
                break
        if zone is not drag.zone:
            if drag.zone is not None and _alive(drag.zone):
                drag.zone.setProperty("fxDragOver", False)
            if zone is not None:
                zone.setProperty("fxDragOver", True)
            drag.zone = zone
        if self._counts["dragover"] > 0:
            self._bubble(chain, "dragover", lambda item: self._drag_event("dragover", item, pos, event))

    @staticmethod
    def _edge(flick: Any, pos: QPointF) -> tuple[Any, float, float] | None:
        """(flick, dx, dy) si el punto está cerca de un borde hacia el que aún se puede desplazar."""
        p = flick.mapFromScene(pos)
        w, h = flick.width(), flick.height()

        def speed(near: float) -> float:
            return _SPEED * (1 - max(near, 0) / _EDGE) + 1

        x, y = flick.property("contentX"), flick.property("contentY")
        ox, oy = flick.property("originX"), flick.property("originY")
        max_x = ox + max(flick.property("contentWidth") - w, 0)
        max_y = oy + max(flick.property("contentHeight") - h, 0)
        dx = -speed(p.x()) if p.x() < _EDGE and x > ox else speed(w - p.x()) if w - p.x() < _EDGE and x < max_x else 0
        dy = -speed(p.y()) if p.y() < _EDGE and y > oy else speed(h - p.y()) if h - p.y() < _EDGE and y < max_y else 0
        return (flick, dx, dy) if dx or dy else None

    @Slot()
    def _scroll_step(self) -> None:
        drag = self._drag
        if drag is None or not drag.scrolls:
            self._autoscroll.stop()
            return
        for flick, dx, dy in drag.scrolls:
            if not _alive(flick):
                continue
            w, h = flick.width(), flick.height()
            ox, oy = flick.property("originX"), flick.property("originY")
            if dx:
                x = flick.property("contentX") + dx
                flick.setProperty("contentX", min(max(x, ox), ox + max(flick.property("contentWidth") - w, 0)))
            if dy:
                y = flick.property("contentY") + dy
                flick.setProperty("contentY", min(max(y, oy), oy + max(flick.property("contentHeight") - h, 0)))
        self._drag_move(drag.pos, None)  # lo que hay bajo el puntero cambió

    def _drop(self, pos: QPointF, event: Any) -> None:
        drag = self._drag
        dropped = False
        for item in self._chain_at(drag.window, pos):
            listener = self._get(item)
            if listener is None or "drop" not in listener.handlers or not item.isEnabled():
                continue
            ev = self._drag_event("drop", item, pos, event)
            listener.call("drop", ev)
            dropped = True
            if ev.stopped:
                break
        self._end_drag(dropped)

    def _end_drag(self, dropped: bool) -> None:
        drag, self._drag = self._drag, None
        self._autoscroll.stop()
        if drag.ghost is not None and _alive(drag.ghost):
            drag.ghost.setParentItem(None)
            drag.ghost.deleteLater()
        if drag.zone is not None and _alive(drag.zone):
            drag.zone.setProperty("fxDragOver", False)
        if not _alive(drag.source):
            return  # el on:drop la quitó (p. ej. la movió a otra lista): no hay a quién avisar
        drag.source.setProperty("fxDragging", False)
        for item in self._ancestors(drag.source):
            listener = self._get(item)
            if listener is None or "dragend" not in listener.handlers:
                continue
            ev = DragEvent("dragend", data=drag.data, dropped=dropped, button="left")
            listener.call("dragend", ev)
            if ev.stopped:
                break

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
            item = self._scan(item, item.mapFromScene(pos))
        items.reverse()
        return items

    @staticmethod
    def _scan(item: Any, local: QPointF) -> Any:
        """Como childAt, pero en el orden en que Qt dibuja (por `z`, y a igual `z` el último)
        y sin las decoraciones de una caja (bordes por lado, contorno). childAt solo mira el
        orden de los hijos: en una ListView, un elemento vacío de z 0 tapaba las filas (z 1).

        Si ningún hijo contiene el punto, vale uno cuyo contenido se sale de él y lo
        contiene (como en Qt, sin `clip` un hijo fuera de su padre recibe el puntero): una
        fila de <List animate> que aún se desliza fuera del alto nuevo de la lista."""
        children = [c for c in item.childItems() if c.isVisible() and c.property("fxDecoration") is not True]
        found = None
        for child in children:
            if found is not None and child.z() < found.z():
                continue
            p = child.mapFromItem(item, local)
            if 0 <= p.x() < child.width() and 0 <= p.y() < child.height():
                found = child
        if found is not None:
            return found
        for child in children:
            if found is not None and child.z() < found.z():
                continue
            if not child.clip() and child.childItems() and child.childrenRect().contains(child.mapFromItem(item, local)):
                found = child
        return found

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
