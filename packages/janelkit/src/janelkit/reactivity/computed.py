"""Valores derivados perezosos con invalidación automática.

`@computed` también vale en un método de una clase: cada instancia tiene su propio
`computed` (se crea la primera vez que se lee y vive lo que vive la instancia):

    class Carrito:
        def __init__(self):
            self.items = state([])

        @computed
        def total(self):
            return sum(i["precio"] for i in self.items.value)

    carrito.total.value      # en la plantilla, {carrito.total}
"""
from __future__ import annotations

import inspect
import types
from typing import Any, Callable, Generic, TypeVar

from .effects import Observer, Source, current_scope

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
    _method: str | None = None  # @computed sobre un método: su nombre en la clase

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

    # -- @computed en un método: un computed por instancia -----------------------------
    def __set_name__(self, owner: type, name: str) -> None:
        if _takes_self(self._fn):
            self._method = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        name = self._method
        if obj is None or name is None:
            return self
        bound: Computed[Any] = Computed(types.MethodType(self._fn, obj))
        # Vive lo que vive la instancia, no lo que vive quien lo leyó primero.
        scope = current_scope()
        if scope is not None:
            scope.discard(bound)
        try:
            vars(obj)[name] = bound  # las siguientes lecturas ya no pasan por aquí
        except TypeError:
            raise TypeError(f"@computed en un método necesita que {type(obj).__name__} tenga __dict__ (sin __slots__)") from None
        return bound

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

    # En un f-string o str() se muestra el valor (y se registra la dependencia, como al leer
    # .value): f"{hub.status}" en una plantilla se actualiza solo. repr() sigue diciendo qué es.
    def __str__(self) -> str:
        return str(self.value)

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)


def computed(fn: Callable[[], T]) -> Computed[T]:
    """Decorador: `@computed def total(): return a.value + b.value`. En un método de una
    clase (`def total(self)`), un computed por instancia."""
    return Computed(fn)


def _takes_self(fn: Callable[..., Any]) -> bool:
    """¿Es `fn` un método (un único parámetro posicional obligatorio)?"""
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    required = [p for p in params if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return len(required) == 1
