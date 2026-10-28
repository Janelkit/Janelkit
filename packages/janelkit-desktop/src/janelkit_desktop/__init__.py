"""Servicios del sistema para JanelKit: diálogos nativos, portapapeles y notificaciones.

    from janelkit_desktop import clipboard, dialogs, notify
"""
from __future__ import annotations

from . import clipboard, dialogs
from .notifications import notify

__version__ = "0.0.1.dev0"

__all__ = ["__version__", "clipboard", "dialogs", "notify"]
