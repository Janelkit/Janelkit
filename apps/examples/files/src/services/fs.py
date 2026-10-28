"""Acceso al sistema de archivos. Funciones síncronas y bloqueantes: la interfaz las
ejecuta en otro hilo con `await background(...)`."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

PREVIEW_BYTES = 20_000
TEXT_SUFFIXES = {
    ".txt", ".md", ".py", ".janel", ".qml", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg",
    ".csv", ".html", ".css", ".js", ".ts", ".xml", ".log", ".rst", ".bat", ".sh", ".ps1",
}  # fmt: skip


def list_dir(folder: str, show_hidden: bool = False) -> list[dict]:
    """Contenido de `folder`: carpetas y archivos con nombre, tamaño y fecha."""
    entries = []
    with os.scandir(folder) as it:
        for entry in it:
            if not show_hidden and entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
                is_dir = entry.is_dir()
            except OSError:  # enlaces rotos, permisos
                continue
            entries.append(
                {
                    "path": entry.path,
                    "name": entry.name,
                    "is_dir": is_dir,
                    "size": 0 if is_dir else stat.st_size,
                    "modified": stat.st_mtime,
                }
            )
    return entries


def read_preview(path: str) -> str:
    """Primeros caracteres de un archivo de texto, o una explicación si no se puede mostrar."""
    p = Path(path)
    if p.suffix.lower() not in TEXT_SUFFIXES:
        return f"Sin vista previa para archivos {p.suffix or 'sin extensión'}."
    with p.open("rb") as f:
        data = f.read(PREVIEW_BYTES + 1)
    text = data[:PREVIEW_BYTES].decode("utf-8", errors="replace")
    return text + ("\n…" if len(data) > PREVIEW_BYTES else "")


def format_size(size: int, exact: bool = False) -> str:
    if exact:
        return f"{size:,} B".replace(",", ".")
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def format_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M")
