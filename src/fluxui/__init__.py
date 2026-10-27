"""FluxUI: componentes de archivo único para escritorio con Python y Qt Quick."""
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
from . import dialogs
from .i18n import i18n, t
from .lifecycle import Ref, inject, on_destroy, on_mount, provide, ref
from .notifications import notify
from .pages import PageStack, pages
from .styling.theme import theme
from .tasks import Task, background, spawn, task
from .timers import Timer, interval, timeout
from .windows import open_window

__version__ = "0.0.1.dev0"

# API pública: lo que se importa desde `fluxui` es estable dentro de una
# versión menor (ver docs/api.md). Cualquier otro módulo es interno.
__all__ = [
    "Computed",
    "Effect",
    "Event",
    "Prop",
    "PageStack",
    "PropError",
    "Ref",
    "State",
    "Task",
    "Timer",
    "__version__",
    "background",
    "batch",
    "computed",
    "dialogs",
    "effect",
    "i18n",
    "event",
    "inject",
    "interval",
    "notify",
    "on_destroy",
    "on_mount",
    "pages",
    "open_window",
    "prop",
    "provide",
    "ref",
    "run",
    "spawn",
    "state",
    "t",
    "task",
    "theme",
    "timeout",
    "untracked",
]

if TYPE_CHECKING:
    from .qt_backend.application import run
else:

    def run(entry: str | os.PathLike[str], argv: list[str] | None = None) -> int:
        # Importación diferida: `from fluxui import state` no necesita cargar Qt.
        from .qt_backend.application import run as _run

        return _run(entry, argv)

    run.__doc__ = "Compila el componente raíz `entry`, abre la ventana y ejecuta el ciclo de eventos de Qt."
