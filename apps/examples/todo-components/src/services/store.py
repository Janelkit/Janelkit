"""Operaciones puras sobre la lista de tareas (sin interfaz, fáciles de probar)."""
from itertools import count

_ids = count(1)


def new_todo(title: str) -> dict:
    return {"id": next(_ids), "title": title.strip(), "done": False}


def initial() -> list[dict]:
    return [new_todo(t) for t in ("Separar la app en componentes", "Pasar datos con props", "Avisar al padre con eventos")]


def update(todos: list[dict], todo_id: int, **changes) -> list[dict]:
    return [{**t, **changes} if t["id"] == todo_id else t for t in todos]


def remove(todos: list[dict], todo_id: int) -> list[dict]:
    return [t for t in todos if t["id"] != todo_id]
