"""Modelo de notas: datos y operaciones puras, sin interfaz."""
from __future__ import annotations

from datetime import datetime
from itertools import count

_ids = count(1)

TAGS = ["general", "trabajo", "ideas"]


def new_note(title: str = "", body: str = "", tag: str = "general") -> dict:
    return {"id": next(_ids), "title": title, "body": body, "tag": tag, "updated": datetime.now()}


def samples() -> list[dict]:
    return [
        new_note("Bienvenida", "JanelKit compila cada archivo .janel a Qt Quick.\nLa lógica sigue siendo Python.", "general"),
        new_note("Componentes", "Esta app usa Sidebar, NoteCard y NoteEditor: props hacia abajo, eventos hacia arriba.", "ideas"),
        new_note("Temas", "Prueba el botón de tema: todos los colores salen de tokens como var(--surface).", "trabajo"),
    ]


def matches(note: dict, query: str) -> bool:
    q = query.strip().lower()
    return not q or q in note["title"].lower() or q in note["body"].lower()


def excerpt(body: str, length: int = 70) -> str:
    text = " ".join(body.split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def when(moment: datetime) -> str:
    return moment.strftime("%d/%m %H:%M")


def save(notes: list[dict], note_id: int, **fields) -> list[dict]:
    updated = [{**n, **fields, "updated": datetime.now()} if n["id"] == note_id else n for n in notes]
    # La nota editada pasa arriba de la lista.
    return sorted(updated, key=lambda n: n["updated"], reverse=True)


def delete(notes: list[dict], note_id: int) -> list[dict]:
    return [n for n in notes if n["id"] != note_id]
