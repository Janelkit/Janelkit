"""Estado observable: `state(valor)` y acceso mediante `.value`."""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from .collections import reactive
from .effects import Source, batch, check_thread, untracked

T = TypeVar("T")


def _same(a: Any, b: Any) -> bool:
    if a is b:
        return True
    if type(a) is not type(b):
        return False
    try:
        with untracked():
            return bool(a == b)
    except Exception:  # noqa: BLE001 - comparaciones ambiguas (p. ej. arrays) cuentan como cambio
        return False


class State(Source, Generic[T]):
    """Valor observable. Leer `.value` registra la dependencia; asignarlo notifica.

    Las listas, diccionarios y conjuntos se guardan como colecciones reactivas
    (ver `collections.py`): `items.value.append(x)` también notifica. Para otros
    objetos modificados en el sitio, llama a `notify()`.
    """

    def __init__(self, initial: T):
        super().__init__()
        self._value = reactive(initial)

    @property
    def value(self) -> T:
        self._track()
        return self._value

    @value.setter
    def value(self, new: T) -> None:
        check_thread()
        new = reactive(new)
        if _same(self._value, new):
            return
        self._value = new
        with batch():
            self._notify()

    def set(self, new: T) -> None:
        self.value = new

    def update(self, fn: Callable[[T], T]) -> None:
        self.value = fn(self._value)

    def notify(self) -> None:
        """Avisa de un cambio hecho en el sitio que FluxUI no puede detectar (p. ej. un objeto propio)."""
        with batch():
            self._notify()

    def peek(self) -> T:
        """Lee el valor sin registrar dependencia."""
        return self._value

    def __repr__(self) -> str:
        return f"state({self._value!r})"


def state(initial: T) -> State[T]:
    return State(initial)
