"""Ciclo de vida, contexto y referencias de los componentes.

Estas funciones se llaman desde el `<script>` de un componente mientras se
ejecuta (su *preparación*):

    from fluxui import on_mount, on_destroy, provide, inject, ref

    campo = ref()                      # <TextField ref={campo} />

    @on_mount
    def enfocar():
        campo.focus()
        temporizador = iniciar()
        return temporizador.stop       # opcional: se llama al desmontar

    on_destroy(lambda: print("adiós"))

    provide("sesion", sesion)          # visible para todos los descendientes
    tema = inject("tema", "claro")     # lo que provee un antecesor (o el defecto)

No importa Qt: el runtime registra el componente activo con `_setup`.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, Protocol, TypeVar

from .reactivity import State

F = TypeVar("F", bound=Callable[..., Any])
_MISSING: Any = object()


class _Setup(Protocol):
    def add_mount(self, fn: Callable[[], Any]) -> None: ...
    def add_destroy(self, fn: Callable[[], Any]) -> None: ...
    def provide(self, key: Any, value: Any) -> None: ...
    def inject(self, key: Any) -> Any: ...


_stack: list[_Setup] = []


@contextmanager
def _setup(component: _Setup) -> Iterator[None]:
    """Marca `component` como el que se está preparando (lo usa el runtime)."""
    _stack.append(component)
    try:
        yield
    finally:
        _stack.pop()


def _current(fn_name: str) -> _Setup:
    if not _stack:
        raise RuntimeError(
            f"{fn_name}() solo puede llamarse mientras se ejecuta el <script> de un componente "
            "(en el nivel superior o en funciones llamadas desde él), no más tarde desde un evento"
        )
    return _stack[-1]


def on_mount(fn: F) -> F:
    """Ejecuta `fn` cuando la vista del componente ya existe. Si devuelve una función, se llama al desmontar.

    Se puede usar como decorador.
    """
    _current("on_mount").add_mount(fn)
    return fn


def on_destroy(fn: F) -> F:
    """Ejecuta `fn` al desmontar el componente. Se puede usar como decorador."""
    _current("on_destroy").add_destroy(fn)
    return fn


def provide(key: Any, value: Any) -> None:
    """Pone `value` a disposición de todos los descendientes de este componente bajo `key`."""
    _current("provide").provide(key, value)


def inject(key: Any, default: Any = _MISSING) -> Any:
    """Valor que un componente antecesor proveyó con `provide(key, ...)`, o `default`."""
    try:
        return _current("inject").inject(key)
    except LookupError:
        if default is _MISSING:
            raise LookupError(
                f"ningún componente antecesor provee {key!r}; llama a provide({key!r}, valor) en uno de ellos "
                f"o pasa un valor por defecto: inject({key!r}, defecto)"
            ) from None
        return default


class Ref:
    """Referencia a un elemento de la plantilla: `campo = ref()` y `<TextField ref={campo} />`.

    `.value` es reactivo: vale `None` hasta que el elemento existe y vuelve a
    `None` cuando se destruye. Los métodos no hacen nada si el elemento no existe.
    """

    __slots__ = ("_item",)

    def __init__(self) -> None:
        self._item: State[Any] = State(None)

    @property
    def value(self) -> Any:
        """El objeto Qt Quick del elemento (`QQuickItem`), o `None`. Interfaz de Qt: úsalo como último recurso."""
        return self._item.value

    @property
    def exists(self) -> bool:
        return self._item.value is not None

    def _attach(self, item: Any) -> None:
        self._item.value = item

    def _detach(self, item: Any) -> None:
        if self._item.peek() is item:
            self._item.value = None

    def _live(self) -> Any:
        item = self._item.peek()
        if item is None:
            return None
        from shiboken6 import Shiboken

        return item if Shiboken.isValid(item) else None

    def focus(self) -> None:
        """Da el foco del teclado al elemento."""
        item = self._live()
        if item is not None:
            item.forceActiveFocus()

    def blur(self) -> None:
        """Quita el foco del teclado al elemento."""
        item = self._live()
        if item is not None:
            item.setFocus(False)

    def select_all(self) -> None:
        """Selecciona todo el texto (TextField, TextArea)."""
        self._call("selectAll")

    def _call(self, method: str) -> None:
        item = self._live()
        if item is None:
            return
        from PySide6.QtCore import QMetaObject

        if not QMetaObject.invokeMethod(item, method):
            raise TypeError(f"este elemento no admite {method}")

    def __repr__(self) -> str:
        item = self._item.peek()
        return f"ref({type(item).__name__ if item is not None else 'sin elemento'})"


def ref() -> Ref:
    """Crea una referencia para `ref={...}` en la plantilla."""
    return Ref()
