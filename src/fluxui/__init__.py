"""FluxUI: componentes de archivo único para escritorio con Python y Qt Quick."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .reactivity import Computed, State, batch, computed, event, prop, state
from .styling.theme import theme

__version__ = "0.0.1.dev0"

__all__ = ["Computed", "State", "__version__", "batch", "computed", "event", "prop", "run", "state", "theme"]

if TYPE_CHECKING:
    from .qt_backend.application import run
else:

    def run(entry: str | os.PathLike[str], argv: list[str] | None = None) -> int:
        # Importación diferida: `from fluxui import state` no necesita cargar Qt.
        from .qt_backend.application import run as _run

        return _run(entry, argv)

    run.__doc__ = "Compila el componente raíz `entry`, abre la ventana y ejecuta el ciclo de eventos de Qt."
