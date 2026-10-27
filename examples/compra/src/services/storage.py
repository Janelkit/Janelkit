"""Guarda la lista en un archivo JSON. Funciones normales (bloqueantes)."""
import json
import os
from pathlib import Path


def data_file() -> Path:
    # Se consulta en cada llamada: así las pruebas pueden usar otro archivo.
    return Path(os.environ.get("COMPRA_FILE", Path.home() / ".lista-compra.json"))


def load() -> list[dict]:
    file = data_file()
    if not file.exists():
        return []
    return json.loads(file.read_text(encoding="utf-8"))


def save(items: list[dict]) -> None:
    data_file().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
