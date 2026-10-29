"""Listas, diccionarios y conjuntos reactivos.

Un `state([...])` o `state({...})` guarda su valor como `ReactiveList`,
`ReactiveDict` o `ReactiveSet`: subclases de `list`, `dict` y `set` que
registran quién las lee y avisan cuando se modifican en el sitio. Así
funcionan tanto `todos.value.append(x)` como `todo["done"] = True`.

- La conversión es profunda: los `list`/`dict`/`set` anidados también se
  vuelven reactivos, al guardarse en un `state` o al insertarse en una
  colección reactiva. Las tuplas y los objetos propios no se tocan.
- Cada colección es su propia fuente: cambiar `todo["done"]` solo actualiza lo
  que leyó ese diccionario, no todo lo que lee la lista que lo contiene.
- Como la conversión copia el contenedor, hay que modificar el objeto que
  devuelve el `state` (no el original que se le pasó).
"""
from __future__ import annotations

from typing import Any, Iterable

from . import history as _history
from .effects import Source, batch, check_thread


def reactive(value: Any) -> Any:
    """Convierte `list`/`dict`/`set` (exactamente esos tipos) en su versión reactiva."""
    kind = type(value)
    if kind is list:
        return ReactiveList(value)
    if kind is dict:
        return ReactiveDict(value)
    if kind is set:
        return ReactiveSet(value)
    return value


def to_plain(value: Any, track: bool = False) -> Any:
    """Copia profunda sin colecciones reactivas (para entregar valores a Qt).

    Con `track=True`, el observador en curso pasa a depender del contenido de
    cada colección copiada: un binding que entrega una lista entera a QML se
    recalcula cuando esa lista se modifica en el sitio.
    """
    if isinstance(value, ReactiveList):
        if track:
            value._jk_src._track()
        return [to_plain(v, track) for v in list.__iter__(value)]
    if isinstance(value, ReactiveDict):
        if track:
            value._jk_src._track()
        return {k: to_plain(v, track) for k, v in dict.items(value)}
    if isinstance(value, ReactiveSet):
        if track:
            value._jk_src._track()
        return set(set.__iter__(value))
    to_qml = getattr(type(value), "__jk_qml__", None)  # p. ej. Frames: QML recibe su parte Qt
    if to_qml is not None:
        return to_qml(value)
    return value


def is_reactive(value: Any) -> bool:
    return isinstance(value, (ReactiveList, ReactiveDict, ReactiveSet))


def _same(a: Any, b: Any) -> bool:
    from .state import _same as same

    return same(a, b)


def _reader(base: type, name: str):
    method = getattr(base, name)

    def read(self, *args, **kwargs):
        self._jk_src._track()
        return method(self, *args, **kwargs)

    read.__name__ = name
    return read


def _writer(base: type, name: str):
    method = getattr(base, name)

    def write(self, *args, **kwargs):
        check_thread()
        self._jk_before()
        result = method(self, *args, **kwargs)
        self._jk_changed()
        return result

    write.__name__ = name
    return write


class _Mixin:
    __slots__ = ()
    _jk_src: Source

    def _jk_changed(self) -> None:
        with batch():
            self._jk_src._notify()

    def _jk_before(self) -> None:
        """Antes de modificarse: si hay un paso de `History` abierto, anota el contenido."""
        if _history._step is not None:
            _history._step.touch(self)


_LIST_READS = (
    "__getitem__", "__iter__", "__reversed__", "__len__", "__contains__", "__eq__", "__ne__",
    "__lt__", "__le__", "__gt__", "__ge__", "__add__", "__mul__", "__rmul__", "__repr__",
    "index", "count", "copy",
)  # fmt: skip


class ReactiveList(_Mixin, list):
    __slots__ = ("_jk_src",)

    def __init__(self, iterable: Iterable = ()):
        list.__init__(self, (reactive(v) for v in iterable))
        self._jk_src = Source()

    def _jk_snapshot(self) -> list:
        return list(list.__iter__(self))

    def _jk_restore(self, content: list) -> None:
        list.__setitem__(self, slice(None), content)
        self._jk_changed()

    def __reduce_ex__(self, protocol):
        return (ReactiveList, (list(list.__iter__(self)),))

    def __setitem__(self, index, value):
        check_thread()
        self._jk_before()
        if isinstance(index, slice):
            value = [reactive(v) for v in value]
        else:
            value = reactive(value)
            if _same(list.__getitem__(self, index), value):
                return
        list.__setitem__(self, index, value)
        self._jk_changed()

    def __iadd__(self, other):
        self.extend(other)
        return self

    def __imul__(self, n):
        check_thread()
        self._jk_before()
        list.__imul__(self, n)
        self._jk_changed()
        return self

    def append(self, value):
        check_thread()
        self._jk_before()
        list.append(self, reactive(value))
        self._jk_changed()

    def extend(self, values):
        check_thread()
        self._jk_before()
        list.extend(self, [reactive(v) for v in values])
        self._jk_changed()

    def insert(self, index, value):
        check_thread()
        self._jk_before()
        list.insert(self, index, reactive(value))
        self._jk_changed()

    __delitem__ = _writer(list, "__delitem__")
    pop = _writer(list, "pop")
    remove = _writer(list, "remove")
    clear = _writer(list, "clear")
    sort = _writer(list, "sort")
    reverse = _writer(list, "reverse")


for _name in _LIST_READS:
    setattr(ReactiveList, _name, _reader(list, _name))


_DICT_READS = (
    "__getitem__", "__iter__", "__reversed__", "__len__", "__contains__", "__eq__", "__ne__",
    "__or__", "__repr__", "get", "keys", "values", "items", "copy",
)  # fmt: skip


class ReactiveDict(_Mixin, dict):
    __slots__ = ("_jk_src",)

    def __init__(self, *args, **kwargs):
        dict.__init__(self)
        self._jk_src = Source()
        dict.update(self, ((k, reactive(v)) for k, v in dict(*args, **kwargs).items()))

    def _jk_snapshot(self) -> dict:
        return dict(dict.items(self))

    def _jk_restore(self, content: dict) -> None:
        dict.clear(self)
        dict.update(self, content)
        self._jk_changed()

    def __reduce_ex__(self, protocol):
        return (ReactiveDict, (dict(dict.items(self)),))

    def __setitem__(self, key, value):
        check_thread()
        self._jk_before()
        value = reactive(value)
        if dict.__contains__(self, key) and _same(dict.__getitem__(self, key), value):
            return
        dict.__setitem__(self, key, value)
        self._jk_changed()

    def update(self, *args, **kwargs):
        with batch():
            for key, value in dict(*args, **kwargs).items():
                self[key] = value

    def __ior__(self, other):
        self.update(other)
        return self

    def setdefault(self, key, default=None):
        if not dict.__contains__(self, key):
            self[key] = default
        return self[key]

    __delitem__ = _writer(dict, "__delitem__")
    pop = _writer(dict, "pop")
    popitem = _writer(dict, "popitem")
    clear = _writer(dict, "clear")


for _name in _DICT_READS:
    setattr(ReactiveDict, _name, _reader(dict, _name))


_SET_READS = (
    "__iter__", "__len__", "__contains__", "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
    "__or__", "__and__", "__sub__", "__xor__", "__repr__", "copy", "union", "intersection",
    "difference", "symmetric_difference", "issubset", "issuperset", "isdisjoint",
)  # fmt: skip
_SET_WRITES = (
    "add", "discard", "remove", "pop", "clear", "update", "difference_update",
    "intersection_update", "symmetric_difference_update",
)  # fmt: skip


class ReactiveSet(_Mixin, set):
    __slots__ = ("_jk_src",)

    def __init__(self, iterable: Iterable = ()):
        set.__init__(self, iterable)
        self._jk_src = Source()

    def _jk_snapshot(self) -> set:
        return set(set.__iter__(self))

    def _jk_restore(self, content: set) -> None:
        set.clear(self)
        set.update(self, content)
        self._jk_changed()

    def __reduce_ex__(self, protocol):
        return (ReactiveSet, (set(set.__iter__(self)),))

    def __ior__(self, other):
        self.update(other)
        return self

    def __iand__(self, other):
        self.intersection_update(other)
        return self

    def __isub__(self, other):
        self.difference_update(other)
        return self

    def __ixor__(self, other):
        self.symmetric_difference_update(other)
        return self


for _name in _SET_READS:
    setattr(ReactiveSet, _name, _reader(set, _name))
for _name in _SET_WRITES:
    setattr(ReactiveSet, _name, _writer(set, _name))
