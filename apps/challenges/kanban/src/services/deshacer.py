"""Deshacer y rehacer del tablero, hecho solo con la API pública de JanelKit.

Un paso es una lista de pares (deshacer, rehacer) con un nombre. `step(nombre, raiz)`
anota solo: copia por encima cada lista y diccionario al que se llega desde `raiz`
antes del paso y, al cerrarlo, anota los que cambiaron. Deshacer los devuelve a como
estaban **en el sitio** (los mismos objetos), así que `{#each}` con clave mueve las
filas en vez de volver a crearlas.

`can_undo`, `can_redo`, `undo_label`, `redo_label` y `modified` son reactivos.
"""
from __future__ import annotations

import itertools
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from janelkit import batch, state, untracked

Par = tuple[Callable[[], Any], Callable[[], Any]]


class Historial:
    def __init__(self, limit: int = 100):
        self.limit = limit
        self._undo: list[tuple[str, int, list[Par]]] = []
        self._redo: list[tuple[str, int, list[Par]]] = []
        self._ids = itertools.count(1)
        self._base = 0  # la posición que queda al deshacerlo todo
        self._saved = 0
        self._busy = False  # dentro de un paso, o deshaciendo/rehaciendo
        self._version = state(0)

    # -- anotar -----------------------------------------------------------------
    @contextmanager
    def step(self, label: str, root: Any) -> Iterator[None]:
        """Anota como un paso lo que cambie, dentro, en las colecciones de `root`."""
        if self._busy:
            with batch():
                yield
            return
        before = _contents(root)
        self._busy = True
        try:
            with batch():
                yield
        finally:
            self._busy = False
            changes = []
            with untracked():
                for coll, old in before.values():
                    new = _copy(coll)
                    if not _same(old, new):
                        changes.append((_restore(coll, old), _restore(coll, new)))
            self._push(label, changes)

    def add(self, label: str, undo: Callable[[], Any], redo: Callable[[], Any]) -> None:
        """Anota algo que ya se hizo (no llama a `redo` ahora)."""
        if not self._busy:
            self._push(label, [(undo, redo)])

    def _push(self, label: str, changes: list[Par]) -> None:
        if not changes:
            return
        self._undo.append((label, next(self._ids), changes))
        self._redo.clear()
        if len(self._undo) > self.limit:
            self._base = self._undo.pop(0)[1]
        self._changed()

    # -- deshacer ----------------------------------------------------------------
    def undo(self) -> str | None:
        if not self._undo:
            return None
        entry = self._undo.pop()
        self._replay(undo for undo, _ in reversed(entry[2]))
        self._redo.append(entry)
        self._changed()
        return entry[0]

    def redo(self) -> str | None:
        if not self._redo:
            return None
        entry = self._redo.pop()
        self._replay(redo for _, redo in entry[2])
        self._undo.append(entry)
        self._changed()
        return entry[0]

    def _replay(self, fns: Iterator[Callable[[], Any]]) -> None:
        self._busy = True
        try:
            with batch():
                for fn in fns:
                    fn()
        finally:
            self._busy = False

    def clear(self) -> None:
        self._base = self._position()
        self._undo.clear()
        self._redo.clear()
        self._changed()

    def mark_saved(self) -> None:
        self._saved = self._position()
        self._changed()

    def _position(self) -> int:
        return self._undo[-1][1] if self._undo else self._base

    def _changed(self) -> None:
        self._version.value = self._version.peek() + 1

    # -- consultas reactivas ------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        self._version.value
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        self._version.value
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        self._version.value
        return self._undo[-1][0] if self._undo else ""

    @property
    def redo_label(self) -> str:
        self._version.value
        return self._redo[-1][0] if self._redo else ""

    @property
    def modified(self) -> bool:
        self._version.value
        return self._position() != self._saved


def _contents(root: Any) -> dict[int, tuple[Any, Any]]:
    """Cada lista y diccionario al que se llega desde `root`, con una copia por encima."""
    out: dict[int, tuple[Any, Any]] = {}
    pending = [root]
    with untracked():
        while pending:
            coll = pending.pop()
            if id(coll) in out:
                continue
            out[id(coll)] = (coll, _copy(coll))
            values = coll.values() if isinstance(coll, dict) else coll
            pending.extend(v for v in values if isinstance(v, (list, dict)))
    return out


def _copy(coll: Any) -> Any:
    return dict(coll) if isinstance(coll, dict) else list(coll)


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, dict):
        return list(a) == list(b) and all(_value_same(a[k], b[k]) for k in a)
    return len(a) == len(b) and all(_value_same(x, y) for x, y in zip(a, b))


def _value_same(x: Any, y: Any) -> bool:
    if x is y:
        return True
    if isinstance(x, (list, dict, set)) or type(x) is not type(y):
        return False
    return bool(x == y)


def _restore(coll: Any, content: Any) -> Callable[[], None]:
    def apply() -> None:
        if isinstance(coll, dict):
            coll.clear()
            coll.update(content)
        else:
            coll[:] = content

    return apply
