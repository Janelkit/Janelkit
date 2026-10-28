"""Estado que se recuerda entre sesiones: `persisted(clave, valor_inicial)`.

    from janelkit import persisted

    tema = persisted("tema", "claro")          # un State: se lee y se escribe con .value
    recientes = persisted("recientes", [])     # recientes.value.append(x) también se guarda

- Es un `State` normal (reactivo, con `.value`, `.set()`, `.update()`). Al crearlo
  lee el valor guardado; si no hay ninguno (o el archivo no se puede leer), usa el
  valor inicial.
- Cada cambio se guarda en disco agrupado: una escritura como mucho cada 300 ms
  y, en todo caso, al cerrar la aplicación. Los cambios en el sitio de listas y
  diccionarios cuentan.
- La clave es global a la aplicación: dos `persisted` con la misma clave son el
  mismo objeto (el segundo valor inicial se ignora). Letras, cifras, `.`, `_` y `-`.
- El valor debe poder guardarse en JSON: textos, números, booleanos, None, listas
  y diccionarios con claves de texto. Las tuplas vuelven como listas.
- Se guarda un archivo `<clave>.json` en la carpeta de datos de la aplicación:
  `JANELKIT_DATA_DIR` si existe; si no, la carpeta de datos del usuario del sistema
  (`%APPDATA%`, `~/Library/Application Support`, `~/.config`) más el nombre de la
  aplicación, que es el de la carpeta del proyecto (la de `src/App.janel`). Con
  `janelkit.inspect.mount` se usa una carpeta temporal, salvo que `JANELKIT_DATA_DIR` diga otra.

Es para preferencias y datos pequeños: cada cambio reescribe el archivo entero.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, TypeVar

from .reactivity import Effect, State
from .reactivity.collections import to_plain
from .reactivity.effects import current_scope

T = TypeVar("T")
log = logging.getLogger("janelkit")

DATA_ENV = "JANELKIT_DATA_DIR"
DELAY_MS = 300
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

_app_name = ""
_folder_override: Path | None = None  # la de mount(): una carpeta temporal por prueba
_registry: dict[str, "Persisted[Any]"] = {}


class Persisted(State[T]):
    """Un `State` que se guarda en `<carpeta de datos>/<clave>.json` al cambiar."""

    def __init__(self, key: str, initial: T, file: Path):
        self.key = key
        self.file = file
        super().__init__(_load(file, initial))
        self._saved = _dump(to_plain(self.peek()))  # lo que hay (o habría) en disco
        self._pending: str | None = None
        self._timer: Any = None
        # Vigila el valor en profundidad. Fuera del ámbito del componente: la clave es de
        # toda la aplicación y sigue guardándose aunque se desmonte quien la creó.
        scope = current_scope()
        self._watch = Effect(self._changed)
        if scope is not None:
            scope.discard(self._watch)

    def _changed(self) -> None:
        text = _dump(to_plain(self.value, track=True))
        if text == self._saved:
            self._pending = None
            return
        self._pending = text
        self._schedule()

    def _schedule(self) -> None:
        from PySide6.QtCore import QCoreApplication, QTimer

        if QCoreApplication.instance() is None:  # sin bucle de Qt (un script, una prueba sin app)
            self.flush()
            return
        if self._timer is None:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.flush)
        if not self._timer.isActive():
            self._timer.start(DELAY_MS)

    def flush(self) -> None:
        """Escribe ya lo pendiente (normalmente no hace falta: se hace solo)."""
        text, self._pending = self._pending, None
        if text is None:
            return
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_name(self.file.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.file)  # atómico: un corte no deja el archivo a medias
            self._saved = text
        except OSError as exc:
            log.error("no se pudo guardar %r en %s: %s", self.key, self.file, exc)

    def __repr__(self) -> str:
        return f"persisted({self.key!r}, {self.peek()!r})"


def persisted(key: str, initial: T) -> Persisted[T]:
    """Un `state` que se recuerda entre sesiones (ver el módulo)."""
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError(f"clave no válida para persisted: {key!r} (usa letras, cifras, '.', '_' y '-')")
    found = _registry.get(key)
    if found is not None:
        return found
    _dump(to_plain(initial))  # un valor inicial que no se puede guardar falla aquí, no al guardar
    created = Persisted(key, initial, data_folder() / f"{key}.json")
    _registry[key] = created
    return created


def data_folder() -> Path:
    """Carpeta donde `persisted` guarda los valores."""
    env = os.environ.get(DATA_ENV)
    if env:
        return Path(env)
    if _folder_override is not None:
        return _folder_override
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / (_app_name or "janelkit")


def use_app(entry: Path, folder: Path | None = None) -> None:
    """La aplicación que arranca (run, mount): fija su nombre y empieza con las claves de cero."""
    global _app_name, _folder_override
    flush_all()
    root = entry.parent.parent if entry.parent.name == "src" else entry.parent
    _app_name = root.name
    _folder_override = folder
    _registry.clear()


def flush_all() -> None:
    for item in list(_registry.values()):
        item.flush()


def _load(file: Path, initial: Any) -> Any:
    try:
        text = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return initial
    except OSError as exc:
        log.warning("no se pudo leer %s: %s; se usa el valor inicial", file, exc)
        return initial
    try:
        return json.loads(text)
    except ValueError as exc:
        log.warning("%s no es JSON válido (%s); se usa el valor inicial", file, exc)
        return initial


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"persisted solo guarda valores JSON (texto, números, listas, diccionarios…): {exc}") from None


atexit.register(flush_all)
