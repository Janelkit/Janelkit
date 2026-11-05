"""Guardar en JSON en la carpeta de datos de la sesión: `persisted()` y los stores con `persist=`.

    from janelkit_store import persisted

    tema = persisted("tema", "claro")          # un State: se lee y se escribe con .value
    recientes = persisted("recientes", [])     # recientes.value.append(x) también se guarda

- Cada cambio se guarda agrupado: una escritura como mucho cada 300 ms y, en todo caso,
  al terminar la sesión (al cerrar la aplicación o desmontarla en una prueba). Los
  cambios en el sitio de listas y diccionarios cuentan. La escritura es atómica.
- El archivo es `<clave>.json` en la carpeta de datos de la sesión
  (`janelkit.ext.session().data_dir`): `JANELKIT_DATA_DIR`, la temporal de
  `janelkit.inspect.mount`, o la carpeta de datos del usuario más el nombre del proyecto.
- Solo valores JSON: textos, números, booleanos, None, listas y diccionarios con claves
  de texto.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, TypeVar

from janelkit import State, effect, untracked
from janelkit.ext import Scope, Session, session

T = TypeVar("T")
log = logging.getLogger("janelkit_store")

DELAY_MS = 300
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_REGISTRY = "janelkit_store.persisted"
_loose: dict[str, "Persisted[Any]"] = {}  # sin aplicación en marcha (un script)


def plain(value: Any) -> Any:
    """Copia profunda con tipos normales (las colecciones reactivas son subclases de list/dict/set).

    Leerla dentro de un `effect` registra la dependencia de cada colección que recorre."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, set):
        return set(value)
    return value


def dump(value: Any, what: str) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{what} solo guarda valores JSON (texto, números, listas, diccionarios…): {exc}") from None


def load(file: Path, default: Any) -> Any:
    try:
        text = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    except OSError as exc:
        log.warning("no se pudo leer %s: %s; se usa el valor inicial", file, exc)
        return default
    try:
        return json.loads(text)
    except ValueError as exc:
        log.warning("%s no es JSON válido (%s); se usa el valor inicial", file, exc)
        return default


def data_dir() -> Path:
    current = session()
    return (current or Session("")).data_dir


class JsonFile:
    """Un archivo que se reescribe agrupando los cambios (como mucho cada DELAY_MS)."""

    def __init__(self, file: Path, saved: str):
        self.file = file
        self._saved = saved  # lo que hay (o habría) en disco
        self._pending: str | None = None
        self._timer: Any = None

    def changed(self, text: str) -> None:
        if text == self._saved:
            self._pending = None
            return
        self._pending = text
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
            log.error("no se pudo guardar %s: %s", self.file, exc)


def watch(read: Callable[[], Any], out: JsonFile, what: str) -> Scope:
    """Guarda en `out` lo que devuelve `read()` cada vez que cambia. Devuelve el ámbito del efecto."""
    scope = Scope()  # no es de quien lo creó: los datos son de toda la aplicación
    with scope.active():
        effect(lambda: out.changed(dump(read(), what)))
    return scope


class Persisted(State[T]):
    """Un `State` que se guarda en `<carpeta de datos>/<clave>.json` al cambiar."""

    def __init__(self, key: str, initial: T, file: Path):
        self.key = key
        self.file = file
        super().__init__(load(file, initial))
        with untracked():
            self._out = JsonFile(file, dump(plain(self.value), "persisted"))
        self._scope = watch(lambda: plain(self.value), self._out, "persisted")

    def flush(self) -> None:
        """Escribe ya lo pendiente (normalmente no hace falta: se hace solo)."""
        self._out.flush()

    def __repr__(self) -> str:
        return f"persisted({self.key!r}, {self.peek()!r})"


def persisted(key: str, initial: T) -> Persisted[T]:
    """Un `state` que se recuerda entre sesiones (ver el módulo). La misma clave da el mismo objeto."""
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError(f"clave no válida para persisted: {key!r} (usa letras, cifras, '.', '_' y '-')")
    registry = _registry()
    found = registry.get(key)
    if found is not None:
        return found
    dump(plain(initial), "persisted")  # un valor inicial que no se puede guardar falla aquí, no al guardar
    created = Persisted(key, initial, data_dir() / f"{key}.json")
    registry[key] = created
    return created


def _registry() -> dict[str, "Persisted[Any]"]:
    current = session()
    if current is None:
        return _loose
    registry = current.data.get(_REGISTRY)
    if registry is None:
        registry = current.data[_REGISTRY] = {}

        def end() -> None:
            for item in list(registry.values()):
                item.flush()
                item._scope.dispose()

        current.on_end(end)
    return registry
