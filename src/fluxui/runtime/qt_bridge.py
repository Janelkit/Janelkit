"""Puente QObject entre una instancia de plantilla y su vista QML.

Cada plantilla compilada obtiene una clase puente propia, creada
dinámicamente, con una propiedad notificable por binding (`b0`, `b1`, ...)
y una propiedad constante por región dinámica (`m0`, `m1`, ...: el modelo
de su `Repeater`). Así QML solo reevalúa las propiedades cuyo valor cambió.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..reactivity.state import _same

InvokeFn = Callable[[str, list], None]
WriteFn = Callable[[str, Any], None]


def make_bridge_class(binding_ids: list[str], model_ids: list[str] = (), name: str = "FluxBridge") -> type[QObject]:
    attrs: dict[str, Any] = {}
    for bid in binding_ids:
        signal = Signal()
        attrs[f"{bid}Changed"] = signal

        def getter(self, _bid=bid):
            return self._values.get(_bid)

        attrs[bid] = Property("QVariant", getter, notify=signal)

    for mid in model_ids:

        def model_getter(self, _mid=mid):
            return self._models.get(_mid)

        attrs[mid] = Property(QObject, model_getter, constant=True)

    def __init__(self, on_invoke: InvokeFn, on_write: WriteFn, parent: QObject | None = None):
        QObject.__init__(self, parent)
        self._values: dict[str, Any] = {}
        self._models: dict[str, QObject] = {}
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

    def set_model(self, mid: str, model: QObject) -> None:
        """Debe llamarse antes de que QML lea la propiedad (es constante)."""
        self._models[mid] = model

    def model(self, mid: str) -> QObject | None:
        return self._models.get(mid)

    # Qt registra los slots por __name__: deben ser funciones con nombre, no lambdas.
    def invoke(self, handler_id: str, args: list) -> None:
        self._on_invoke(handler_id, list(args or []))

    def write(self, binding_id: str, value: Any) -> None:
        self._on_write(binding_id, value)

    attrs.update(
        __init__=__init__,
        set_value=set_value,
        value=value,
        set_model=set_model,
        model=model,
        invoke=Slot(str, "QVariantList")(invoke),
        write=Slot(str, "QVariant")(write),
    )
    return type(name, (QObject,), attrs)
