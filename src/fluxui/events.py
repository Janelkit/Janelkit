"""Eventos de `<flex>` (on:pointerdown, on:keydown, on:wheel…): lo que recibe el manejador.

Los nombres siguen a la web. Todos tienen `prevent()` (cancela lo que haría
FluxUI o Qt con el evento: que Espacio active un botón, que la rueda desplace,
que una tecla llegue a un campo de texto) y `stop()` (el evento no sigue hacia
los contenedores de fuera). Ambos solo tienen efecto antes del primer `await`
de un manejador `async def`.

    from fluxui import KeyEvent

    def al_pulsar(event: KeyEvent):
        if event.key == "Delete" and not event.repeat:
            borrar()
            event.prevent()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Event:
    type: str
    prevented: bool = field(default=False, init=False)
    stopped: bool = field(default=False, init=False)

    def prevent(self) -> None:
        """Cancela el comportamiento por defecto del evento."""
        self.prevented = True

    def stop(self) -> None:
        """El evento no sigue hacia los `<flex>` de fuera."""
        self.stopped = True


@dataclass
class _Modifiers:
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False


@dataclass
class PointerEvent(_Modifiers, _Event):
    """on:click, on:dblclick, on:contextmenu, on:pointerdown/up/move/enter/leave."""

    x: float = 0.0  # respecto al elemento que escucha
    y: float = 0.0
    window_x: float = 0.0
    window_y: float = 0.0
    button: str | None = None  # "left", "right", "middle" (None si no hay botón: move, enter)
    buttons: tuple[str, ...] = ()  # pulsados ahora
    pointer: str = "mouse"  # "mouse", "touch", "pen" o "keyboard" (on:click con Espacio o Intro)
    clicks: int = 1


@dataclass
class DragEvent(PointerEvent):
    """on:dragstart, on:dragover, on:drop, on:dragend (arrastrar un `<flex draggable>`).

    `data` es lo que se arrastra: lo pone el manejador de on:dragstart (cualquier objeto
    de Python) y llega igual a on:dragover, on:drop y on:dragend. En on:dragend, `dropped`
    dice si algún on:drop lo recibió (False si se soltó fuera o se canceló con Escape)."""

    data: Any = None
    dropped: bool = False


@dataclass
class KeyEvent(_Modifiers, _Event):
    """on:keydown, on:keyup."""

    key: str = ""  # como en la web: "a", "A", "Enter", "Escape", "ArrowUp", "Delete", " "…
    code: str = ""  # tecla física: "KeyA", "Digit1", "Space"…
    text: str = ""
    repeat: bool = False


@dataclass
class WheelEvent(_Modifiers, _Event):
    """on:wheel. `dx`, `dy` en píxeles (positivo: hacia la derecha y hacia abajo, como en la web)."""

    dx: float = 0.0
    dy: float = 0.0
    x: float = 0.0
    y: float = 0.0


@dataclass
class FocusEvent(_Event):
    """on:focus, on:blur. `reason`: "tab", "click" o "code"."""

    reason: str = "code"


@dataclass
class ResizeEvent(_Event):
    """on:resize."""

    width: float = 0.0
    height: float = 0.0

    def __getitem__(self, key: str) -> float:  # event["width"], como un diccionario
        return {"width": self.width, "height": self.height}[key]
