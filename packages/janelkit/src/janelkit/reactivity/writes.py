"""Registro de escrituras: por dónde se observa qué estado cambia (lo usa janelkit-store).

`State` y las colecciones reactivas avisan a `listener`, si hay uno, justo **antes** de
cada escritura: `listener.state(estado, valor_de_antes)` al asignar un `State`, y
`listener.collection(coleccion)` antes de modificar en el sitio una lista, un
diccionario o un conjunto reactivo (todavía tiene el contenido de antes). Sin nadie
escuchando cuesta una comprobación de `None`.

Desde fuera se usa con `on_write(fn)`: `fn(destino, dueño, antes)` por cada escritura,
donde `dueño` es lo que se le dio con `own()` al `State` o a la colección (o None). Si
`fn` lanza una excepción, la escritura no se hace: así un store estricto impide escribir
fuera de sus acciones.
"""
from __future__ import annotations

from typing import Any, Callable

Callback = Callable[[Any, Any, Any], None]

listener: Any = None
_callbacks: list[Callback] = []


class _Dispatch:
    """El `listener` cuando hay alguien en `on_write`."""

    def state(self, state: Any, before: Any) -> None:
        owner = getattr(state, "_jk_owner", None)
        for fn in tuple(_callbacks):
            fn(state, owner, before)

    def collection(self, collection: Any) -> None:
        for fn in tuple(_callbacks):
            fn(collection, collection._jk_owner, None)


_DISPATCH = _Dispatch()


def on_write(fn: Callback) -> Callable[[], None]:
    """Llama a `fn(destino, dueño, antes)` antes de cada escritura. Devuelve la función que lo quita."""
    global listener
    _callbacks.append(fn)
    listener = _DISPATCH

    def remove() -> None:
        global listener
        if fn in _callbacks:
            _callbacks.remove(fn)
        if not _callbacks:
            listener = None

    return remove


def own(target: Any, owner: Any) -> None:
    """Marca `target` (un `State` o una colección reactiva) y todas las colecciones que
    contiene como de `owner`. Lo que se inserte después en ellas, o se asigne al `State`,
    hereda el dueño."""
    from .collections import adopt
    from .state import State

    if isinstance(target, State):
        target._jk_owner = owner
        adopt(target.peek(), owner)
    else:
        adopt(target, owner)
