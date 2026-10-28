"""Valores derivados perezosos con invalidación automática."""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from .effects import Observer, Source

T = TypeVar("T")

_UNSET = object()


_IMMUTABLE = (type(None), bool, int, float, complex, str, bytes, range)


def _same(old: object, new: object) -> bool:
    """Mismo valor, solo para valores inmutables sencillos: un objeto mutable (una lista
    reactiva, un diccionario) puede haber cambiado por dentro aunque sea el mismo."""
    return type(old) is type(new) and _immutable(old) and _immutable(new) and old == new


def _immutable(value: object) -> bool:
    if isinstance(value, (tuple, frozenset)):
        return all(_immutable(v) for v in value)
    return isinstance(value, _IMMUTABLE)


class Computed(Observer, Source, Generic[T]):
    _certain = False  # avisa de que quizá cambió: quien lo lea lo recalcula para saberlo

    """Valor calculado a partir de otros estados; se recalcula solo al leerse tras un cambio."""

    def __init__(self, fn: Callable[[], T]):
        Source.__init__(self)
        Observer.__init__(self)
        self._fn = fn
        self._value: object = _UNSET
        self._dirty = True
        self._version = 0  # sube cada vez que el valor cambia (ver Effect._needs_run)
        self.__name__ = getattr(fn, "__name__", "computed")

    @property
    def value(self) -> T:
        if self._dirty or self.disposed:
            result = self._fn() if self.disposed else self._collect(self._fn)
            if not _same(self._value, result):
                self._version += 1
            self._value = result
            self._dirty = self.disposed
        self._track()
        return self._value  # type: ignore[return-value]

    def peek(self) -> T:
        from .effects import untracked

        with untracked():
            return self.value

    def _mark_stale(self, certain: bool = True) -> None:
        if not self._dirty:
            self._dirty = True
            self._notify()

    def __repr__(self) -> str:
        shown = "<sin calcular>" if self._value is _UNSET else repr(self._value)
        return f"computed {self.__name__} = {shown}"


def computed(fn: Callable[[], T]) -> Computed[T]:
    """Decorador: `@computed def total(): return a.value + b.value`."""
    return Computed(fn)
