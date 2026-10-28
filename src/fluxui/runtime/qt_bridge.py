"""Puente QObject entre una instancia de plantilla y su vista QML.

Cada plantilla compilada obtiene una clase puente propia, creada
dinámicamente, con una propiedad notificable por binding (`b0`, `b1`, ...)
y una propiedad constante por región dinámica (`m0`, `m1`, ...: el modelo
de su `Repeater`). Así QML solo reevalúa las propiedades cuyo valor cambió.
"""
from __future__ import annotations

from typing import Any, Protocol

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..reactivity.collections import to_plain
from ..reactivity.state import _same



class BridgeOwner(Protocol):
    """Quien recibe lo que QML comunica a través del puente."""

    def bridge_invoke(self, handler_id: str, args: list) -> None: ...
    def bridge_write(self, binding_id: str, value: Any) -> None: ...
    def bridge_ref(self, ref_id: str, item: QObject, attached: bool) -> None: ...
    def bridge_mounted(self, item: QObject) -> None: ...


# Las clases puente nunca se liberan: QML guarda en caché la información de
# cada QMetaObject por su dirección, y si una clase se liberase, otra nueva
# podría ocupar la misma dirección y heredar una caché que no le corresponde.
# Además, clases con la misma forma se reutilizan entre compilaciones.
_classes: dict[tuple, type[QObject]] = {}


def make_bridge_class(binding_ids: list[str], model_ids: list[str] = (), name: str = "FluxBridge") -> type[QObject]:
    key = (name, tuple(binding_ids), tuple(model_ids))
    cls = _classes.get(key)
    if cls is None:
        cls = _classes[key] = _make_bridge_class(binding_ids, model_ids, name)
    return cls


def _make_bridge_class(binding_ids: list[str], model_ids: list[str], name: str) -> type[QObject]:
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

    def __init__(self, owner: BridgeOwner, parent: QObject | None = None):
        QObject.__init__(self, parent)
        self._values: dict[str, Any] = {}
        self._models: dict[str, QObject] = {}
        self._owner = owner

    def set_value(self, bid: str, value: Any) -> bool:
        """Actualiza una propiedad; solo notifica a QML si el valor cambió."""
        value = to_plain(value)
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
        self._owner.bridge_invoke(handler_id, list(args or []))

    def write(self, binding_id: str, value: Any) -> None:
        self._owner.bridge_write(binding_id, value)

    def setRef(self, ref_id: str, item: QObject, attached: bool) -> None:
        self._owner.bridge_ref(ref_id, item, attached)

    def mounted(self, item: QObject) -> None:
        self._owner.bridge_mounted(item)

    # Salida animada (out:/transition:): FxTransition anima la raíz al recibir leave().
    attrs["leave"] = Signal()

    attrs.update(
        __init__=__init__,
        set_value=set_value,
        value=value,
        set_model=set_model,
        model=model,
        invoke=Slot(str, "QVariantList")(invoke),
        write=Slot(str, "QVariant")(write),
        setRef=Slot(str, QObject, bool)(setRef),
        mounted=Slot(QObject)(mounted),
    )
    return type(name, (QObject,), attrs)
