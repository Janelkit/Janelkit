"""Puente QObject entre una instancia de componente y su vista QML.

Cada componente compilado obtiene una clase puente propia, creada
dinámicamente, con una propiedad notificable por binding (`b0`, `b1`, ...).
Así QML solo reevalúa las propiedades cuyo valor cambió.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..reactivity.state import _same

InvokeFn = Callable[[str, list], None]
WriteFn = Callable[[str, Any], None]


def make_bridge_class(binding_ids: list[str], name: str = "FluxBridge") -> type[QObject]:
    attrs: dict[str, Any] = {}
    for bid in binding_ids:
        signal = Signal()
        attrs[f"{bid}Changed"] = signal

        def getter(self, _bid=bid):
            return self._values.get(_bid)

        attrs[bid] = Property("QVariant", getter, notify=signal)

    def __init__(self, on_invoke: InvokeFn, on_write: WriteFn):
        QObject.__init__(self)
        self._values: dict[str, Any] = {}
        self._on_invoke = on_invoke
        self._on_write = on_write

    def set_value(self, bid: str, value: Any) -> bool:
        """Actualiza una propiedad; solo notifica a QML si el valor cambió."""
        if bid in self._values and _same(self._values[bid], value):
            return False
        self._values[bid] = value
        getattr(self, f"{bid}Changed").emit()
        return True

    def value(self, bid: str) -> Any:
        return self._values.get(bid)

    # Qt registra los slots por __name__: deben ser funciones con nombre, no lambdas.
    def invoke(self, handler_id: str, args: list) -> None:
        self._on_invoke(handler_id, list(args or []))

    def write(self, binding_id: str, value: Any) -> None:
        self._on_write(binding_id, value)

    attrs.update(
        __init__=__init__,
        set_value=set_value,
        value=value,
        invoke=Slot(str, "QVariantList")(invoke),
        write=Slot(str, "QVariant")(write),
    )
    return type(name, (QObject,), attrs)
