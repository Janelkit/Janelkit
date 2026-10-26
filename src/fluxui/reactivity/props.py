"""Props y eventos de componentes.

En el `<script>` de un componente hijo:

    from fluxui import prop, event

    todo = prop()            # obligatoria: el padre debe pasarla
    compacto = prop(False)   # opcional, con valor por defecto
    borrado = event()        # el padre escucha con on:borrado={...}

    def borrar():
        borrado.emit(todo.value["id"])

Las props son de solo lectura para el hijo y reactivas: cuando el padre cambia
el valor, se actualiza todo lo que las lee. En la plantilla se usan sin
`.value`, como los `state`.
"""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from .state import State

T = TypeVar("T")

REQUIRED: Any = object()


class PropError(AttributeError):
    pass


class Prop(Generic[T]):
    """Vista de solo lectura del valor que pasa el componente padre."""

    __slots__ = ("name", "_state")

    def __init__(self, name: str, source: State[T]):
        self.name = name
        self._state = source

    @property
    def value(self) -> T:
        return self._state.value

    @value.setter
    def value(self, new: T) -> None:
        raise PropError(
            f"la prop '{self.name}' es de solo lectura: la controla el componente padre. "
            "Declara un event() para pedirle el cambio, o copia el valor en un state()."
        )

    def peek(self) -> T:
        return self._state.peek()

    def __repr__(self) -> str:
        return f"prop {self.name} = {self._state.peek()!r}"


class Event:
    """Evento que un componente emite hacia su padre."""

    __slots__ = ("name", "_handler")

    def __init__(self, name: str, handler: Callable[..., Any] | None = None):
        self.name = name
        self._handler = handler

    @property
    def connected(self) -> bool:
        return self._handler is not None

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """Llama al manejador del padre (`on:<nombre>`); no hace nada si no lo hay."""
        if self._handler is not None:
            self._handler(*args, **kwargs)

    __call__ = emit

    def __repr__(self) -> str:
        return f"event {self.name}"


def prop(default: Any = REQUIRED) -> Prop:
    """Declara una prop. Solo es válido en el nivel superior del `<script>`: `nombre = prop(...)`."""
    raise RuntimeError("prop() solo puede usarse en el <script> de un componente .flux, como `nombre = prop(...)`")


def event() -> Event:
    """Declara un evento. Solo es válido en el nivel superior del `<script>`: `nombre = event()`."""
    raise RuntimeError("event() solo puede usarse en el <script> de un componente .flux, como `nombre = event()`")
