"""JanelKit: componentes de archivo único para escritorio con Python y Qt Quick."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .reactivity import (
    Computed,
    Effect,
    Event,
    Prop,
    PropError,
    State,
    batch,
    computed,
    effect,
    event,
    prop,
    state,
    untracked,
)
from .locale import locale
from .events import DragEvent, FocusEvent, KeyEvent, PointerEvent, ResizeEvent, WheelEvent
from .lifecycle import Ref, before_leave, inject, on_destroy, on_mount, provide, ref
from .pages import PageStack, Sections, navigation, pages, sections
from .storage import Persisted, persisted
from .styling.theme import theme
from .tasks import Task, background, spawn, task
from .timers import Timer, interval, timeout
from .windows import open_window

__version__ = "0.0.1.dev0"

# API pública: lo que se importa desde `janelkit` es estable dentro de una
# versión menor (ver docs/api.md). Cualquier otro módulo es interno.
__all__ = [
    "Computed",
    "Effect",
    "DragEvent",
    "Event",
    "FocusEvent",
    "KeyEvent",
    "Prop",
    "PageStack",
    "Persisted",
    "PointerEvent",
    "PropError",
    "Ref",
    "Sections",
    "ResizeEvent",
    "State",
    "Task",
    "Timer",
    "WheelEvent",
    "__version__",
    "background",
    "batch",
    "before_leave",
    "computed",
    "effect",
    "event",
    "inject",
    "interval",
    "locale",
    "navigation",
    "on_destroy",
    "on_mount",
    "pages",
    "persisted",
    "open_window",
    "prop",
    "provide",
    "ref",
    "run",
    "sections",
    "spawn",
    "state",
    "task",
    "theme",
    "timeout",
    "untracked",
]

if TYPE_CHECKING:
    from .qt_backend.application import run
else:

    def run(entry: str | os.PathLike[str], argv: list[str] | None = None) -> int:
        # Importación diferida: `from janelkit import state` no necesita cargar Qt.
        from .qt_backend.application import run as _run

        return _run(entry, argv)

    run.__doc__ = "Compila el componente raíz `entry`, abre la ventana y ejecuta el ciclo de eventos de Qt."
