"""Deshacer y rehacer: `History`.

    historial = History()

    def mover(tarjeta, origen, destino):
        with historial.step(f"mover «{tarjeta['titulo']}»"):
            origen.remove(tarjeta)
            destino.insert(0, tarjeta)

    historial.undo()   # las dos listas vuelven a como estaban
    historial.redo()

Dentro de `step`, cada `State` asignado y cada lista, diccionario o conjunto
reactivo modificado se anota solo: su valor de antes (la primera vez que cambia
en el paso) y el de después (al cerrarlo). Deshacer devuelve todos a su valor de
antes, en un `batch`; rehacer, al de después. Da igual cuántas veces o en qué
orden cambiaran dentro del paso, y un paso cuesta una copia superficial de cada
colección que toca (no de lo que contiene: un diccionario dentro de una lista es
otra colección, que se anota solo si cambia).

Lo que no es reactivo (un diccionario normal, un archivo) se anota con
`historial.add(nombre, undo=…, redo=…)`: funciones que deshacen y rehacen algo
que ya se hizo. Dentro de un `step` se suman a él.

Lo que cambia fuera de un `step` no se anota. Deshacer después un paso que tocó
lo mismo devuelve el valor que tenía antes del paso.
"""
from __future__ import annotations

import itertools
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from .effects import Source, batch, untracked

_step: "_Step | None" = None  # el paso que se está anotando
_counter = itertools.count(1)


class _Step:
    __slots__ = ("label", "states", "collections", "entries")

    def __init__(self, label: str):
        self.label = label
        self.states: dict[int, tuple[Any, Any]] = {}  # id -> (State, antes)
        self.collections: dict[int, tuple[Any, Any]] = {}  # id -> (colección, contenido de antes)
        self.entries: list[tuple[str, Any]] = []  # en orden: ("state", id), ("coll", id) o ("fn", (deshacer, rehacer))

    def touch_state(self, state: Any, before: Any) -> None:
        key = id(state)
        if key not in self.states:
            self.states[key] = (state, before)
            self.entries.append(("state", key))

    def touch(self, collection: Any) -> None:
        key = id(collection)
        if key not in self.collections:
            self.collections[key] = (collection, collection._jk_snapshot())
            self.entries.append(("coll", key))

    def close(self) -> list[tuple[Callable[[], Any], Callable[[], Any]]]:
        """Lo anotado como pares (deshacer, rehacer), sin lo que acabó como estaba."""
        out = []
        with untracked():
            for kind, item in self.entries:
                if kind == "fn":
                    out.append(item)
                elif kind == "state":
                    state, before = self.states[item]
                    after = state._value
                    if before is not after and not _equal(before, after):
                        out.append((_assign(state, before), _assign(state, after)))
                else:
                    coll, before = self.collections[item]
                    after = coll._jk_snapshot()
                    if not _equal(before, after):
                        out.append((_restore(coll, before), _restore(coll, after)))
        return out


def _equal(a: Any, b: Any) -> bool:
    try:
        return type(a) is type(b) and bool(a == b)
    except Exception:  # noqa: BLE001 - comparaciones ambiguas cuentan como cambio
        return False


def _assign(state: Any, value: Any) -> Callable[[], None]:
    def apply() -> None:
        state.value = value

    return apply


def _restore(collection: Any, content: Any) -> Callable[[], None]:
    return lambda: collection._jk_restore(content)


@contextmanager
def _paused() -> Iterator[None]:
    """Cambia estado sin anotarlo (el propio historial, deshacer y rehacer)."""
    global _step
    outer, _step = _step, None
    try:
        yield
    finally:
        _step = outer


class _Entry:
    __slots__ = ("label", "id", "changes")

    def __init__(self, label: str, id: int, changes: list[tuple[Callable[[], Any], Callable[[], Any]]]):
        self.label = label
        self.id = id
        self.changes = changes


class History:
    """Pila de deshacer y rehacer. Ver el docstring del módulo.

    `can_undo`, `can_redo`, `undo_label`, `redo_label` y `modified` son
    reactivos: se pueden usar en la plantilla (`enabled={historial.can_undo}`).
    """

    def __init__(self, limit: int = 100):
        self.limit = limit
        self._undo: list[_Entry] = []
        self._redo: list[_Entry] = []
        self._base = 0  # la posición que queda al deshacerlo todo
        self._saved = 0
        self._replaying = False
        self._info = Source()

    # -- anotar -----------------------------------------------------------------
    @contextmanager
    def step(self, label: str) -> Iterator[None]:
        """Anota como un solo paso lo que cambie dentro. Un `step` dentro de otro se suma a él."""
        global _step
        if _step is not None or self._replaying:
            with batch():
                yield
            return
        _step = current = _Step(label)
        try:
            with batch():
                yield
        finally:
            _step = None
            self._push(current.label, current.close())

    def add(self, label: str, undo: Callable[[], Any], redo: Callable[[], Any]) -> None:
        """Anota algo que ya se hizo y que el historial no ve (no llama a `redo` ahora)."""
        if self._replaying:
            return
        if _step is not None:
            _step.entries.append(("fn", (undo, redo)))
        else:
            self._push(label, [(undo, redo)])

    def _push(self, label: str, changes: list) -> None:
        if not changes:
            return
        self._undo.append(_Entry(label, next(_counter), changes))
        self._redo.clear()
        if len(self._undo) > self.limit:
            self._base = self._undo.pop(0).id
        self._changed()

    # -- deshacer ----------------------------------------------------------------
    def undo(self) -> str | None:
        """Deshace el último paso. Devuelve su nombre, o None si no había nada."""
        if not self._undo:
            return None
        entry = self._undo.pop()
        self._replay(undo for undo, _ in reversed(entry.changes))
        self._redo.append(entry)
        self._changed()
        return entry.label

    def redo(self) -> str | None:
        """Rehace el último paso deshecho. Devuelve su nombre, o None si no había nada."""
        if not self._redo:
            return None
        entry = self._redo.pop()
        self._replay(redo for _, redo in entry.changes)
        self._undo.append(entry)
        self._changed()
        return entry.label

    def _replay(self, fns: Iterator[Callable[[], Any]]) -> None:
        self._replaying = True
        try:
            with _paused(), batch():
                for fn in fns:
                    fn()
        finally:
            self._replaying = False

    def clear(self) -> None:
        """Olvida los pasos (p. ej. al abrir otro documento). No cambia `modified`."""
        self._base = self._position()
        self._undo.clear()
        self._redo.clear()
        self._changed()

    def mark_saved(self) -> None:
        """Marca lo que hay ahora como guardado: `modified` pasa a False hasta el próximo cambio."""
        self._saved = self._position()
        self._changed()

    def _position(self) -> int:
        return self._undo[-1].id if self._undo else self._base

    def _changed(self) -> None:
        with batch():
            self._info._notify()

    # -- consultas reactivas ------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        self._info._track()
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        self._info._track()
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        """Nombre del paso que se desharía ("" si no hay)."""
        self._info._track()
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        self._info._track()
        return self._redo[-1].label if self._redo else ""

    @property
    def modified(self) -> bool:
        """Si lo que hay difiere de lo marcado con `mark_saved()` (al empezar, de lo inicial)."""
        self._info._track()
        return self._position() != self._saved

    def __repr__(self) -> str:
        return f"History({len(self._undo)} para deshacer, {len(self._redo)} para rehacer)"
