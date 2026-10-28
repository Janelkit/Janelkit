"""Spike del Incremento 0: puente Python <-> Qt Quick.

Valida tres cosas sin archivos .janel:
1. Un QObject Python con propiedades notificables actualiza la vista.
2. Un clic en QML modifica estado Python.
3. Un TextField sincroniza su valor con Python sin bucles.

Además prueba la técnica que usará el runtime: crear la clase puente de forma
dinámica (``type(...)``) con una propiedad por binding.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlContext, QQmlEngine


def make_bridge_class(names: list[str]) -> type[QObject]:
    attrs: dict[str, object] = {}
    for name in names:
        sig = Signal()
        attrs[f"{name}Changed"] = sig

        def getter(self, _n=name):
            return self._values.get(_n)

        attrs[name] = Property("QVariant", getter, notify=sig)

    def __init__(self, on_invoke, on_write):
        QObject.__init__(self)
        self._values = {}
        self._on_invoke = on_invoke
        self._on_write = on_write

    def set_value(self, name, value):
        if self._values.get(name, object()) == value and name in self._values:
            return False
        self._values[name] = value
        getattr(self, f"{name}Changed").emit()
        return True

    attrs["__init__"] = __init__
    attrs["set_value"] = set_value
    # Los slots deben ser funciones con nombre: Qt registra el slot con __name__.
    def invoke(self, handler):
        self._on_invoke(handler)

    def write(self, name, value):
        self._on_write(name, value)

    attrs["invoke"] = Slot(str)(invoke)
    attrs["write"] = Slot(str, "QVariant")(write)
    return type("SpikeBridge", (QObject,), attrs)


class Model:
    """Estado Python plano; el puente refleja sus cambios."""

    def __init__(self) -> None:
        self.count = 0
        self.name = ""
        self.writes = 0
        Bridge = make_bridge_class(["countText", "name"])
        self.bridge = Bridge(self.on_invoke, self.on_write)
        self.sync()

    def sync(self) -> None:
        self.bridge.set_value("countText", f"Clicks: {self.count}")
        self.bridge.set_value("name", self.name)

    def on_invoke(self, handler: str) -> None:
        if handler == "increment":
            self.count += 1
            self.sync()

    def on_write(self, name: str, value) -> None:
        self.writes += 1
        if name == "name":
            self.name = str(value)
            self.sync()


def load(engine: QQmlEngine, model: Model) -> QObject:
    ctx = QQmlContext(engine.rootContext(), engine)
    ctx.setContextProperty("jk", model.bridge)
    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(__file__).with_name("Counter.qml"))))
    obj = comp.create(ctx)
    if obj is None:
        raise RuntimeError("\n".join(e.toString() for e in comp.errors()))
    model.keepalive = (ctx, comp)  # contexto y componente deben vivir con la vista
    return obj


def main() -> int:
    app = QGuiApplication(sys.argv)
    engine = QQmlEngine()
    model = Model()
    window = load(engine, model)
    if ms := os.environ.get("SPIKE_EXIT_AFTER_MS"):
        QTimer.singleShot(int(ms), app.quit)
    code = app.exec()
    del window
    return code


if __name__ == "__main__":
    raise SystemExit(main())
