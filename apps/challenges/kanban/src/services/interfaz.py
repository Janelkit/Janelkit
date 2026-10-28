"""Estado de la ventana que comparten las columnas y las tarjetas (`provide("ui", ...)`):
la tarjeta abierta en el detalle, el menú contextual, la tarjeta nueva que enfocar y el filtro."""
from __future__ import annotations

from typing import Any

from janelkit import batch, computed, state


class Interfaz:
    def __init__(self, texto: Any, etiqueta: Any, persona: Any):
        self.detalle = state(None)  # id de la tarjeta abierta en el panel de detalle
        self.menu = state(None)  # {"id", "x", "y"} del menú contextual abierto
        self.enfocar = state(None)  # id de una tarjeta nueva (duplicada) que debe tomar el foco al aparecer
        self._origen = None  # ref de la tarjeta que abrió el menú: recupera el foco al cerrarlo
        # Lo que la barra filtra, o None: las tarjetas solo lo leen si hay filtro.
        self.filtro = computed(lambda: (texto.value, etiqueta.value, persona.value)
                               if texto.value.strip() or etiqueta.value or persona.value else None)

    def abrir(self, ident: str) -> None:
        with batch():
            self.menu.value = None
            self.detalle.value = ident

    def menu_en(self, ident: str, x: float | None, y: float | None, origen: Any = None) -> None:
        self._origen = origen
        self.menu.value = {"id": ident, "x": x, "y": y}

    def cerrar_menu(self) -> None:
        self.menu.value = None
        if self._origen is not None:
            self._origen.focus()
            self._origen = None
