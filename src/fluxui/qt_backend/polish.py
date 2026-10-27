"""Enganche del motor de disposición de `<flex>` (flex.js) con Qt Quick.

Cada ventana de FluxUI tiene un `FxPolisher`: cuando el motor tiene contenedores
pendientes le pide `polish()`, y Qt llama a `updatePolish()` justo antes de
sincronizar el fotograma. Ahí se vacía la cola de flex.js: la disposición está
siempre al día en el fotograma que se dibuja, y varios cambios seguidos cuestan
una sola pasada. Si en esa pasada cambia algo que vuelve a pedir `polish()`
(un layout de Qt dentro de un `<flex>`), Qt repite la fase antes de dibujar.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuick import QQuickItem

URI = "FluxEngine"
_registered = False


class FxPolisher(QQuickItem):
    polishing = Signal()

    @Slot()
    def request(self) -> None:
        self.polish()

    def updatePolish(self) -> None:
        self.polishing.emit()


def register_types() -> None:
    global _registered
    if not _registered:
        qmlRegisterType(FxPolisher, URI, 1, 0, "FxPolisher")
        _registered = True
