"""Stores para JanelKit: los datos compartidos de una aplicación, en un solo sitio.

    from janelkit_store import store, field, use

    @store(strict=True, persist="carrito")
    class Carrito:
        items: list[dict] = []

        def agregar(self, item):
            self.items.append(item)

    carrito = use(Carrito)     # en un .janel: la misma instancia en todas las ventanas

Ver `_store.py` (stores) y `_files.py` (`persisted`).
"""
from __future__ import annotations

from janelkit.ext import inspector

from ._files import Persisted, persisted
from ._store import Change, Mutation, StoreError, field, mutations, reset, snapshot, store, subscribe, use

__version__ = "0.1.0"
__all__ = [
    "Change", "Mutation", "Persisted", "StoreError", "__version__", "field", "mutations", "persisted", "reset",
    "snapshot", "store", "subscribe", "use",
]  # fmt: skip


@inspector("store")
def _inspect_store(app: object, cls: type, key: object = None) -> object:
    """`app.store(Carrito, key=None)` en janelkit.inspect: la instancia de la aplicación montada."""
    return use(cls, key)


@inspector("mutations")
def _inspect_mutations(app: object) -> list[Mutation]:
    """`app.mutations()` en janelkit.inspect: las mutaciones de la aplicación montada."""
    return mutations()
