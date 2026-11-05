"""Stores: los datos compartidos de una aplicación, en una clase.

    from janelkit import computed
    from janelkit_store import store, field

    @store(strict=True, persist="carrito")
    class Carrito:
        items: list[dict] = []                 # campo: reactivo, sin .value
        nota: str = field("", bind=True)       # en un store estricto, solo estos admiten bind:
        _cache: dict = {}                      # con _: interno (ni reactivo, ni se anota, ni se guarda)

        @computed
        def total(self) -> float:              # derivado, en caché
            return sum(i["precio"] for i in self.items)

        def agregar(self, item):               # cada método es una acción
            self.items.append(item)

- **Campos:** cada anotación de la clase es un campo reactivo con su valor por defecto
  (copiado para cada instancia). Se leen y escriben como atributos normales, sin `.value`;
  en la plantilla, `{carrito.total}`.
- **Acciones:** cada método (salvo `setup`, `teardown` y los `__dunder__`) es una acción:
  agrupa sus cambios en un `batch`, se anota como una `Mutation` y, en un store estricto, es
  el único sitio desde el que se puede escribir. En un método `async`, lo que cambia tras un
  `await` sigue contando como de esa acción. Lo que crea una acción (un `effect`, un
  `timeout`) es del store.
- **Instancias:** `use(Carrito)` da la de la sesión (la misma en todas las ventanas y
  vistas; una nueva en cada `janelkit.inspect.mount`), y `use(Documento, key=ruta)`, una
  por clave, que se libera al desmontarse el último componente que la pidió. `Carrito()`
  crea una suelta, para probar sin Qt.
- **Seguir los cambios:** `subscribe(instancia, fn)`; `JANELKIT_STORE_LOG=1` registra cada
  `Mutation` en el logger `janelkit_store`.
"""
from __future__ import annotations

import contextvars
import copy
import functools
import inspect
import logging
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, TypeVar

from janelkit import Computed, State, batch, on_destroy, untracked
from janelkit.ext import Scope, on_write, own, session

from ._files import KEY, JsonFile, data_dir, dump, load, plain, watch

C = TypeVar("C", bound=type)
log = logging.getLogger("janelkit_store")
LOG_ENV = "JANELKIT_STORE_LOG"
_HOOKS = ("setup", "teardown")
_MISSING: Any = object()


class StoreError(RuntimeError):
    """Uso no permitido de un store (escribir fuera de una acción en uno estricto, use() sin aplicación…)."""


@dataclass(frozen=True)
class Change:
    """Lo que cambió en un campo durante una acción. `old` y `new` son copias (con tipos normales)
    y solo se hacen si alguien observa (`subscribe`, `JANELKIT_STORE_LOG`); si no, son None."""

    field: str
    kind: str  # "set": se asignó; "mutate": se modificó en el sitio
    old: Any = None
    new: Any = None


@dataclass(frozen=True)
class Mutation:
    """Una acción que cambió algo: qué store, con qué clave, qué acción y qué campos."""

    store: str
    key: Any
    action: str | None  # nombre del método, "bind:campo" o None (fuera de una acción, store no estricto)
    changes: tuple[Change, ...]
    instance: Any = dc_field(default=None, compare=False, repr=False)

    def __str__(self) -> str:
        where = self.store if self.key is None else f"{self.store}[{self.key!r}]"
        return f"{where}.{self.action or '(sin acción)'}: {', '.join(c.field for c in self.changes)}"


# -- declarar ----------------------------------------------------------------------------
class _FieldSpec:
    __slots__ = ("default", "bind", "persist")

    def __init__(self, default: Any, bind: bool, persist: bool):
        self.default, self.bind, self.persist = default, bind, persist


def field(default: Any = None, *, bind: bool = False, persist: bool = True) -> Any:
    """Un campo con opciones: `bind=True` admite `bind:` en un store estricto; `persist=False`
    no se guarda con `persist=`."""
    return _FieldSpec(default, bind, persist)


class _Field:
    """Descriptor de un campo: un `State` por instancia, leído y escrito sin `.value`."""

    def __init__(self, name: str, default: Any, bind: bool, persist: bool):
        self.name, self.default, self.bind, self.persist = name, default, bind, persist

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return _data(obj).states[self.name].value

    def __set__(self, obj: Any, value: Any) -> None:
        data = _data(obj)
        frame = _current.get()
        if frame is not None and frame.instance is obj:
            data.states[self.name].value = value
            return
        if data.meta.strict:
            raise _outside(data, self.name)
        with _acting(obj, None):  # una asignación desde fuera: una mutación sin acción
            data.states[self.name].value = value

    def __jk_bind__(self, obj: Any, value: Any) -> None:
        """`bind:` desde la plantilla (janelkit): una acción «bind:campo»."""
        data = _data(obj)
        if data.meta.strict and not self.bind:
            raise StoreError(
                f"{data.meta.name}.{self.name} no admite bind: en un store estricto; "
                f"declara {self.name} = field(..., bind=True) o escríbelo con un método"
            )
        with _acting(obj, f"bind:{self.name}"):
            data.states[self.name].value = value


class _Derived:
    """`@computed` en un store: se lee sin `.value` (un computed por instancia)."""

    def __init__(self, name: str, template: Computed):
        self.name, self.template = name, template

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        bound = obj.__dict__.get(self.name)
        if not isinstance(bound, Computed):
            with _data(obj).scope.active():
                bound = self.template.__get__(obj, type(obj))  # crea el de la instancia y lo guarda
        return bound.value

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError(f"{type(obj).__name__}.{self.name} es un valor derivado (@computed): no se asigna")


class _Meta:
    def __init__(self, cls: type, fields: dict[str, _Field], private: dict[str, Any], strict: bool, persist: str | None):
        self.name = cls.__name__
        self.fields = fields
        self.private = private
        self.strict = strict
        self.persist = persist


def store(cls: C | None = None, *, strict: bool = False, persist: str | None = None) -> Any:
    """Decorador de clase: convierte sus anotaciones en campos y sus métodos en acciones (ver el módulo).

    `strict=True`: fuera de los métodos del store solo se lee (escribir da `StoreError`), y
    `bind:` solo vale con los campos `field(..., bind=True)`. `persist="clave"`: los campos
    públicos se guardan en `<carpeta de datos>/<clave>.json` y se leen al crearse."""
    if persist is not None and not KEY.fullmatch(persist):
        raise ValueError(f"clave no válida para persist: {persist!r} (usa letras, cifras, '.', '_' y '-')")

    def make(target: C) -> C:
        return _make_store(target, strict, persist)

    return make(cls) if cls is not None else make


def _make_store(cls: Any, strict: bool, persist: str | None) -> Any:
    if "__init__" in cls.__dict__:
        raise StoreError(f"{cls.__name__}: un store no define __init__; prepara lo que haga falta en setup(self)")
    fields: dict[str, _Field] = {}
    private: dict[str, Any] = {}
    for name in cls.__dict__.get("__annotations__", {}):
        if name.startswith("__"):
            continue
        value = cls.__dict__.get(name, _MISSING)
        spec = value if isinstance(value, _FieldSpec) else _FieldSpec(None if value is _MISSING else value, False, True)
        if name.startswith("_"):
            private[name] = spec.default
            continue
        fields[name] = _Field(name, spec.default, spec.bind, spec.persist)
        setattr(cls, name, fields[name])
    for name, value in list(cls.__dict__.items()):
        if isinstance(value, Computed):
            setattr(cls, name, _Derived(name, value))
        elif inspect.isfunction(value) and not (name.startswith("__") and name.endswith("__")) and name not in _HOOKS:
            if name in fields:
                raise StoreError(f"{cls.__name__}.{name} es a la vez un campo y un método")
            setattr(cls, name, _action(value, name))
    cls.__jk_store__ = _Meta(cls, fields, private, strict, persist)

    def __init__(self: Any, **values: Any) -> None:
        unknown = set(values) - set(fields) - set(private)
        if unknown:
            raise TypeError(f"{cls.__name__} no tiene los campos {', '.join(sorted(unknown))}; tiene {', '.join(fields)}")
        _start(self, None, values, saving=False)

    cls.__init__ = __init__
    if "__repr__" not in cls.__dict__:
        cls.__repr__ = lambda self: f"<store {cls.__name__}{'' if _data(self).key is None else f' {_data(self).key!r}'}>"
    return cls


# -- instancias -----------------------------------------------------------------------------
class _FieldOwner:
    """Dueño de los datos de un campo (janelkit.ext.own): así se sabe de qué campo es una escritura."""

    __slots__ = ("instance", "field")

    def __init__(self, instance: Any, field: str):
        self.instance, self.field = instance, field


class _Data:
    def __init__(self, meta: _Meta, key: Any):
        self.meta = meta
        self.key = key
        self.states: dict[str, State] = {}
        self.scope = Scope()
        self.subscribers: list[Callable[[Mutation], Any]] = []
        self.file: JsonFile | None = None
        self.saving: Scope | None = None
        self.users = 0  # componentes que la pidieron con use(..., key=)


def _meta_of(cls: Any) -> _Meta:
    meta = getattr(cls, "__jk_store__", None)
    if not isinstance(meta, _Meta):
        raise TypeError(f"{getattr(cls, '__name__', cls)!r} no es un store: decora la clase con @store")
    return meta


def _data(obj: Any) -> _Data:
    return obj.__dict__["_jk_store"]


def _start(obj: Any, key: Any, values: dict[str, Any], saving: bool) -> None:
    """Prepara una instancia: campos, lo guardado (persist=), dueño de los datos y setup()."""
    meta = _meta_of(type(obj))
    data = obj.__dict__["_jk_store"] = _Data(meta, key)
    for name, default in meta.private.items():
        obj.__dict__[name] = values[name] if name in values else copy.deepcopy(default)
    initial = {name: values[name] if name in values else copy.deepcopy(f.default) for name, f in meta.fields.items()}
    persistent = [name for name, f in meta.fields.items() if f.persist]
    if saving and meta.persist:
        file = data_dir() / f"{meta.persist}.json"
        stored = load(file, {})
        if isinstance(stored, dict):
            initial.update({k: v for k, v in stored.items() if k in persistent and k not in values})
        data.file = JsonFile(file, dump({k: plain(initial[k]) for k in persistent}, f"@store(persist=) de {meta.name}"))
    for name, value in initial.items():
        data.states[name] = State(value)
        own(data.states[name], _FieldOwner(obj, name))
    _listen()
    setup = getattr(type(obj), "setup", None)
    if setup is not None:
        params = len(inspect.signature(setup).parameters)
        with _acting(obj, "setup", silent=True):
            setup(obj, key) if params > 1 else setup(obj)
    if data.file is not None:
        states = data.states
        data.saving = watch(lambda: {k: plain(states[k].value) for k in persistent}, data.file,
                            f"@store(persist=) de {meta.name}")  # fmt: skip


def _finish(obj: Any) -> None:
    """Fin de una instancia: teardown(), lo pendiente al disco y su ámbito liberado."""
    data = _data(obj)
    teardown = getattr(type(obj), "teardown", None)
    if teardown is not None:
        try:
            with _acting(obj, "teardown", silent=True):
                teardown(obj)
        except Exception:  # noqa: BLE001 - no impide guardar ni liberar
            log.exception("error en %s.teardown()", data.meta.name)
    if data.saving is not None:
        data.saving.dispose()
    if data.file is not None:
        data.file.flush()
    data.scope.dispose()


_SESSION_KEY = "janelkit_store.instances"
_LOG_KEY = "janelkit_store.mutations"


def use(cls: type, key: Any = None) -> Any:
    """La instancia de `cls` de esta aplicación (la misma en todas las ventanas y vistas).

    Con `key`, una por clave; si se pide en el script de un componente, se libera cuando
    se desmonta el último que la pidió. Sin aplicación en marcha es un error: para probar
    un store sin Qt, crea una instancia suelta (`Carrito()`)."""
    meta = _meta_of(cls)
    current = session()
    if current is None:
        raise StoreError(
            f"use({meta.name}) necesita una aplicación en marcha (run o janelkit.inspect.mount); "
            f"para probarlo sin Qt, crea una instancia suelta: {meta.name}()"
        )
    instances = current.data.get(_SESSION_KEY)
    if instances is None:
        instances = current.data[_SESSION_KEY] = {}

        def end() -> None:
            for obj in reversed(list(instances.values())):
                _finish(obj)
            instances.clear()

        current.on_end(end)
    found = instances.get((cls, key))
    if found is None:
        found = cls.__new__(cls)
        instances[(cls, key)] = found  # antes de setup: un setup que pide otro store que lo pide a él no se repite
        try:
            _start(found, key, {}, saving=True)
        except BaseException:
            instances.pop((cls, key), None)
            raise
    if key is not None:
        data = _data(found)
        try:
            on_destroy(lambda: _release(instances, cls, key, found))
            data.users += 1
        except RuntimeError:
            pass  # pedida fuera del script de un componente: vive lo que la sesión
    return found


def _release(instances: dict, cls: type, key: Any, obj: Any) -> None:
    data = _data(obj)
    data.users -= 1
    if data.users <= 0 and instances.get((cls, key)) is obj:
        del instances[(cls, key)]
        _finish(obj)


# -- acciones y cambios ------------------------------------------------------------------------
class _Frame:
    """Una acción en curso (o «sin acción»): lo que cambió en ella, por campo."""

    __slots__ = ("instance", "action", "silent", "changes")

    def __init__(self, instance: Any, action: str | None, silent: bool = False):
        self.instance, self.action, self.silent = instance, action, silent
        self.changes: dict[str, list[Any]] | None = None  # campo -> [tipo, antes]


_current: contextvars.ContextVar[_Frame | None] = contextvars.ContextVar("janelkit_store_action", default=None)


class _acting:
    """Ejecuta un bloque como acción `action` de `obj` (o se une a la que ya está en curso)."""

    __slots__ = ("obj", "frame", "token", "scope")

    def __init__(self, obj: Any, action: str | None, silent: bool = False):
        self.obj = obj
        running = _current.get()
        self.frame = None if running is not None and running.instance is obj else _Frame(obj, action, silent)
        self.token: Any = None
        self.scope: Any = None

    def __enter__(self) -> None:
        if self.frame is not None:
            self.token = _current.set(self.frame)
            self.scope = _data(self.obj).scope.active()
            self.scope.__enter__()

    def __exit__(self, *exc: Any) -> None:
        if self.frame is not None:
            self.scope.__exit__(*exc)
            _current.reset(self.token)
            _emit(self.frame)


def _action(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def run_async(self: Any, *args: Any, **kwargs: Any) -> Any:
            with _acting(self, name):  # contextvars: la acción sigue siendo esta tras cada await
                return await fn(self, *args, **kwargs)

        return run_async

    @functools.wraps(fn)
    def run(self: Any, *args: Any, **kwargs: Any) -> Any:
        with _acting(self, name):
            with batch():
                return fn(self, *args, **kwargs)

    return run


_listening = False
_pending: dict[int, _Frame] = {}  # cambios en el sitio fuera de una acción (stores no estrictos)


def _listen() -> None:
    global _listening
    if not _listening:
        on_write(_on_write)
        _listening = True


def _on_write(target: Any, owner: Any, before: Any) -> None:
    """Antes de cada escritura de estado (janelkit.ext.on_write): ¿de qué store y campo es?"""
    if type(owner) is not _FieldOwner:
        return
    obj, name = owner.instance, owner.field
    data = _data(obj)
    frame = _current.get()
    if frame is None or frame.instance is not obj:
        if data.meta.strict:
            raise _outside(data, name)
        frame = _pending.get(id(obj))
        if frame is None:  # un cambio en el sitio desde fuera: se anota al terminar lo que se está haciendo
            frame = _pending[id(obj)] = _Frame(obj, None)
            _later(frame)
    if frame.changes is None:
        frame.changes = {}
    entry = frame.changes.get(name)
    is_set = isinstance(target, State)
    if entry is None:
        old = None
        if _observed(data):
            with untracked():
                old = plain(before if is_set else data.states[name].peek())
        frame.changes[name] = ["set" if is_set else "mutate", old]
    elif is_set:
        entry[0] = "set"


def _later(frame: _Frame) -> None:
    def flush() -> None:
        _pending.pop(id(frame.instance), None)
        _emit(frame)

    from PySide6.QtCore import QCoreApplication, QTimer

    if QCoreApplication.instance() is None:  # sin bucle de Qt: no se puede esperar al cambio
        _pending.pop(id(frame.instance), None)
        return
    QTimer.singleShot(0, flush)


def _outside(data: _Data, name: str) -> StoreError:
    return StoreError(
        f"{data.meta.name}.{name}: en un store estricto solo se escribe dentro de sus métodos; "
        f"añade un método a {data.meta.name} que lo haga, o usa @store(strict=False)"
    )


def _observed(data: _Data) -> bool:
    return bool(data.subscribers) or bool(os.environ.get(LOG_ENV))


def _emit(frame: _Frame) -> None:
    if not frame.changes or frame.silent:
        return
    obj = frame.instance
    data = _data(obj)
    observed = _observed(data)
    with untracked():
        changes = tuple(
            Change(name, kind, old, plain(data.states[name].peek()) if observed else None)
            for name, (kind, old) in frame.changes.items()
        )
    mutation = Mutation(data.meta.name, data.key, frame.action, changes, obj)
    current = session()
    if current is not None:
        current.data.setdefault(_LOG_KEY, []).append(mutation)
    if os.environ.get(LOG_ENV):
        log.info("%s", mutation)
    for fn in tuple(data.subscribers):
        try:
            fn(mutation)
        except Exception:  # noqa: BLE001 - un suscriptor no impide avisar a los demás
            log.exception("error en un suscriptor de %s", data.meta.name)


# -- funciones del módulo -------------------------------------------------------------------
def subscribe(obj: Any, fn: Callable[[Mutation], Any]) -> Callable[[], None]:
    """Llama a `fn(mutation)` tras cada acción que cambie algo en `obj`. Devuelve la función que lo quita."""
    data = _data(obj)
    data.subscribers.append(fn)

    def cancel() -> None:
        if fn in data.subscribers:
            data.subscribers.remove(fn)

    return cancel


def snapshot(obj: Any) -> dict[str, Any]:
    """Copia de los campos públicos, con tipos normales (para guardar, comparar o mostrar)."""
    data = _data(obj)
    with untracked():
        return {name: plain(state.peek()) for name, state in data.states.items()}


def reset(obj: Any) -> None:
    """Devuelve los campos a sus valores por defecto (una acción «reset»)."""
    data = _data(obj)
    with _acting(obj, "reset"), batch():
        for name, f in data.meta.fields.items():
            data.states[name].value = copy.deepcopy(f.default)


def mutations() -> list[Mutation]:
    """Las mutaciones de la sesión en curso, de la más antigua a la más reciente."""
    current = session()
    return list(current.data.get(_LOG_KEY, ())) if current is not None else []
