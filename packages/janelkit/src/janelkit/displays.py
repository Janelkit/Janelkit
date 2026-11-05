"""Pantallas conectadas, como lista reactiva.

    from janelkit import screens

    screens.value          # [Screen(index=0, name="DELL U2720Q", width=2560, height=1440, primary=True, …), …]

    <window title="Proyección" screen={1 if len(screens) > 1 else 0} fullscreen={True}>
    {#each screens as s}<text>{s.name}: {s.width}×{s.height}</text>{/each}

- Cambia sola al conectar o desconectar una pantalla, al cambiar la principal o la resolución.
- Está vacía hasta que la aplicación arranca (`janelkit.run` o `janelkit.inspect.mount`).
- Es de solo lectura: un `computed`.
"""
from __future__ import annotations

from typing import Any, NamedTuple

from .reactivity import Computed, State


class Screen(NamedTuple):
    """Una pantalla. `x`, `y`, `width` y `height` en píxeles lógicos del escritorio virtual."""

    index: int
    name: str
    width: int
    height: int
    x: int
    y: int
    primary: bool
    scale: float  # píxeles físicos por píxel lógico (1.0, 1.5, 2.0…)


_screens: State[list[Screen]] = State([])
screens: Computed[list[Screen]] = Computed(lambda: list(_screens.value))
screens.__name__ = "screens"
_connected: set[int] = set()  # pantallas cuyas señales ya se escuchan
_apps: set[int] = set()  # aplicaciones ya conectadas


def _read(qt_app: Any) -> list[Screen]:
    primary = qt_app.primaryScreen()
    out = []
    for index, screen in enumerate(qt_app.screens()):
        geometry = screen.geometry()
        out.append(Screen(index, screen.name(), geometry.width(), geometry.height(), geometry.x(), geometry.y(),
                          screen is primary or screen == primary, float(screen.devicePixelRatio())))
    return out


def _refresh(qt_app: Any) -> None:
    for screen in qt_app.screens():
        if id(screen) not in _connected:
            _connected.add(id(screen))
            screen.geometryChanged.connect(lambda *_: _refresh(qt_app))
    _screens.value = _read(qt_app)  # una lista igual no avisa a nadie


def connect(qt_app: Any) -> None:
    """La llama la aplicación al arrancar: rellena la lista y la mantiene al día."""
    if id(qt_app) in _apps:
        return
    _apps.add(id(qt_app))
    qt_app.screenAdded.connect(lambda *_: _refresh(qt_app))
    qt_app.screenRemoved.connect(lambda *_: _refresh(qt_app))
    qt_app.primaryScreenChanged.connect(lambda *_: _refresh(qt_app))
    _refresh(qt_app)
