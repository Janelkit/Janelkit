"""Sesión de aplicación: lo que vive lo que vive una aplicación, no el proceso.

Cada `run()` abre una sesión, y cada `janelkit.inspect.mount()` una nueva, con su carpeta
de datos temporal: así una prueba no ve lo que dejó la anterior. Los paquetes guardan en
`session.data` lo que es de una aplicación (los stores de janelkit-store) y se enteran
de su fin con `session.on_end(fn)` para guardar y liberar. Se usa con
`janelkit.ext.session()`.

La carpeta de datos (`data_dir`) es `JANELKIT_DATA_DIR` si existe; si no, la que fija
`inspect.mount` (temporal) o la carpeta de datos del usuario del sistema (`%APPDATA%`,
`~/Library/Application Support`, `~/.config`) más el nombre de la aplicación, que es el
de la carpeta del proyecto (la de `src/App.janel`).
"""
from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[[], Any])
log = logging.getLogger("janelkit")

DATA_ENV = "JANELKIT_DATA_DIR"


class Session:
    """Una aplicación en marcha (o montada para probarla)."""

    def __init__(self, name: str, folder: Path | None = None):
        self.name = name  # el de la carpeta del proyecto
        self._folder = folder
        self.data: dict[Any, Any] = {}  # para los paquetes: una clave propia cada uno
        self._on_end: list[Callable[[], Any]] = []
        self.ended = False

    @property
    def data_dir(self) -> Path:
        """Carpeta donde guardar los datos de la aplicación (ver el módulo)."""
        env = os.environ.get(DATA_ENV)
        if env:
            return Path(env)
        if self._folder is not None:
            return self._folder
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        return base / (self.name or "janelkit")

    def on_end(self, fn: F) -> F:
        """Llama a `fn()` al terminar la sesión (al cerrar la aplicación o al desmontarla en una prueba)."""
        self._on_end.append(fn)
        return fn

    def end(self) -> None:
        """Termina la sesión: llama a lo registrado con `on_end`, en orden inverso."""
        if self.ended:
            return
        self.ended = True
        for fn in reversed(self._on_end):
            try:
                fn()
            except Exception:  # noqa: BLE001 - lo de un paquete no impide cerrar lo demás
                log.exception("error al terminar la sesión")
        self._on_end.clear()

    def __repr__(self) -> str:
        return f"<sesión {self.name!r}{' terminada' if self.ended else ''}>"


_current: Session | None = None


def current() -> Session | None:
    """La sesión en curso, o None si no hay ninguna aplicación en marcha."""
    return _current


def start(entry: Path, folder: Path | None = None) -> Session:
    """Abre la sesión de la aplicación de `entry` (termina la anterior, si la había)."""
    global _current
    if _current is not None:
        _current.end()
    root = entry.parent.parent if entry.parent.name == "src" else entry.parent
    _current = Session(root.name, folder)
    return _current


def end() -> None:
    global _current
    if _current is not None:
        _current.end()
        _current = None


atexit.register(end)
