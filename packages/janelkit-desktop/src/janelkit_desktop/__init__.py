"""Servicios del sistema para JanelKit: diálogos nativos y portapapeles.

    from janelkit_desktop import clipboard, dialogs
"""
from __future__ import annotations

from . import clipboard, dialogs

__version__ = "0.2.0.0"

__all__ = ["__version__", "clipboard", "dialogs"]

# Lo que se quitó en la serie 0.2: importarlo da un error que dice qué hacer.
_REMOVED = {
    name: f"{name} se quitó de janelkit-desktop en la 0.2 (notificaciones y bandeja del sistema). "
    "Para avisar dentro de la aplicación, usa un aviso en la propia ventana (un {#if} con un timeout); "
    "ver la sección «Cambios» del README de janelkit-desktop."
    for name in ("notify", "notifications")
}


def __getattr__(name: str):
    if name in _REMOVED:
        raise ImportError(_REMOVED[name])
    raise AttributeError(f"module 'janelkit_desktop' has no attribute {name!r}")
