"""El carrito: un store estricto que comparten la ventana principal y la del carrito.

Fuera de sus métodos solo se lee: las vistas llaman a `agregar`, `quitar` o `vaciar`, y
cada llamada es una acción que se anota (`subscribe`). Se guarda solo en `carrito.json`.
"""
from __future__ import annotations

from janelkit import computed
from janelkit_store import field, store

PRODUCTOS = [
    {"id": "pan", "nombre": "Pan", "precio": 1.2},
    {"id": "leche", "nombre": "Leche", "precio": 0.95},
    {"id": "cafe", "nombre": "Café", "precio": 4.5},
    {"id": "fruta", "nombre": "Fruta", "precio": 2.3},
]


@store(strict=True, persist="carrito")
class Carrito:
    lineas: list[dict] = []  # [{"id", "nombre", "precio", "cantidad"}]
    nota: str = field("", bind=True)  # la escribe un campo con bind:

    @computed
    def total(self) -> float:
        return sum(l["precio"] * l["cantidad"] for l in self.lineas)

    @computed
    def unidades(self) -> int:
        return sum(l["cantidad"] for l in self.lineas)

    def agregar(self, producto: dict) -> None:
        for linea in self.lineas:
            if linea["id"] == producto["id"]:
                linea["cantidad"] += 1
                return
        self.lineas.append({**producto, "cantidad": 1})

    def quitar(self, ident: str) -> None:
        for i, linea in enumerate(self.lineas):
            if linea["id"] == ident:
                if linea["cantidad"] > 1:
                    linea["cantidad"] -= 1
                else:
                    del self.lineas[i]
                return

    def vaciar(self) -> None:
        self.lineas = []
        self.nota = ""
