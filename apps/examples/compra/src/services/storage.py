"""Guarda la lista en un archivo JSON. Funciones normales (bloqueantes)."""
import itertools
import json
import os
import threading
from pathlib import Path

_lock = threading.Lock()
_numbers = itertools.count(1)
_written = 0  # número del último guardado escrito


def data_file() -> Path:
    # Se consulta en cada llamada: así las pruebas pueden usar otro archivo.
    return Path(os.environ.get("COMPRA_FILE", Path.home() / ".lista-compra.json"))


def load() -> list[dict]:
    file = data_file()
    if not file.exists():
        return []
    return json.loads(file.read_text(encoding="utf-8"))


def next_number() -> int:
    """Número de orden para save(). Se pide en el hilo de la interfaz, en el orden de los cambios."""
    return next(_numbers)


def save(items: list[dict], number: int) -> None:
    # Un guardado cancelado sigue escribiendo en su hilo: el candado evita que dos escriban
    # a la vez y el número, que uno anterior pise al último.
    global _written
    with _lock:
        if number < _written:
            return
        _written = number
        data_file().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
