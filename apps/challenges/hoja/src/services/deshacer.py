"""Deshacer y rehacer de la hoja, hecho solo con la API pública de JanelKit.

Un paso es una lista de pares (deshacer, rehacer) con un nombre: `add(nombre, undo=,
redo=)` anota algo que ya se hizo. `can_undo`, `can_redo`, `undo_label`, `redo_label`
y `modified` son reactivos.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable, Iterator

from janelkit import batch, state

Par = tuple[Callable[[], Any], Callable[[], Any]]


class Historial:
    def __init__(self, limit: int = 100):
        self.limit = limit
        self._undo: list[tuple[str, int, list[Par]]] = []
        self._redo: list[tuple[str, int, list[Par]]] = []
        self._ids = itertools.count(1)
        self._base = 0  # la posición que queda al deshacerlo todo
        self._saved = 0
        self._busy = False  # deshaciendo o rehaciendo
        self._version = state(0)

    # -- anotar -----------------------------------------------------------------
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

