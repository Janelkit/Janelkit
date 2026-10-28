"""Lo que se ve de la hoja: celda activa, selección, columnas visibles, celdas congeladas
y edición. Es Python normal (sin interfaz) para poder probarlo y medirlo aparte.

Las filas las virtualiza `<List>`. Las columnas no (las filas ocupan el ancho de la
lista), así que se virtualizan aquí: solo se muestran las `caben` columnas a partir de
`inicio`, y el desplazamiento horizontal va de columna en columna, como en las hojas
de cálculo. Ver HALLAZGOS.md.
"""
from __future__ import annotations

from typing import Any

from janelkit import computed, effect, state, untracked

from services.formulas import nombre
from services.hoja import Hoja

ANCHO_COL = 96
ANCHO_NUM = 56
ALTO_FILA = 25


class Vista:
    def __init__(self, hoja: Hoja):
        self.hoja = hoja
        self.cursor = state((0, 0))
        self.ancla = state((0, 0))  # el otro extremo de la selección
        self.inicio = state(0)  # primera columna desplazable que se ve
        self.caben = state(10)  # columnas que caben a lo ancho
        self.congelar_fila = state(False)
        self.congelar_col = state(False)
        self.editando = state(None)  # (fila, col) de la celda que se edita
        self.borrador = state("")
        self.visibles = computed(self._visibles)
        self.rango = computed(self._rango)
        effect(self._seguir_columna)

    def _seguir_columna(self) -> None:
        # Congelar la columna A o cambiar el ancho deja menos sitio: que la activa se siga viendo.
        self.congelar_col.value, self.caben.value
        with untracked():
            self.mostrar_col(self.cursor.value[1])

    # -- consultas ------------------------------------------------------------------
    def _visibles(self) -> list[int]:
        fijas = [0] if self.congelar_col.value else []
        desde = max(self.inicio.value, len(fijas))
        hasta = min(self.hoja.columnas, desde + max(1, self.caben.value - len(fijas)))
        return fijas + list(range(desde, hasta))

    def _rango(self) -> tuple[int, int, int, int]:
        (r0, c0), (r1, c1) = self.cursor.value, self.ancla.value
        return min(r0, r1), min(c0, c1), max(r0, r1), max(c0, c1)

    def en_rango(self, r: int, c: int) -> bool:
        r0, c0, r1, c1 = self.rango.value
        return r0 <= r <= r1 and c0 <= c <= c1

    def nombre_activa(self) -> str:
        r0, c0, r1, c1 = self.rango.value
        activa = nombre(*self.cursor.value)
        return activa if (r0, c0) == (r1, c1) else f"{activa} ({nombre(r0, c0)}:{nombre(r1, c1)})"

    def x_de(self, c: int) -> int:
        """Posición horizontal de la columna `c` dentro de una fila (para el editor)."""
        return ANCHO_NUM + self.visibles.peek().index(c) * ANCHO_COL

    # -- moverse --------------------------------------------------------------------
    def ir(self, r: int, c: int, extender: bool = False) -> None:
        r = max(0, min(self.hoja.filas - 1, r))
        c = max(0, min(self.hoja.columnas - 1, c))
        self.cursor.value = (r, c)
        if not extender:
            self.ancla.value = (r, c)
        self.mostrar_col(c)

    def mover(self, dr: int, dc: int, extender: bool = False) -> None:
        r, c = self.cursor.peek()
        self.ir(r + dr, c + dc, extender)

    def mostrar_col(self, c: int) -> None:
        fijas = 1 if self.congelar_col.peek() else 0
        if c < fijas:  # la congelada siempre se ve; se vuelve al principio de las demás
            self.inicio.value = fijas
            return
        n = max(1, self.caben.peek() - fijas)
        inicio = max(self.inicio.peek(), fijas)
        if c < inicio:
            self.inicio.value = c
        elif c >= inicio + n:
            self.inicio.value = c - n + 1

    def desplazar_cols(self, d: int) -> None:
        fijas = 1 if self.congelar_col.peek() else 0
        n = max(1, self.caben.peek() - fijas)
        self.inicio.value = max(fijas, min(self.hoja.columnas - n, self.inicio.peek() + d))

    def medir(self, ancho: float) -> None:
        self.caben.value = max(1, int((ancho - ANCHO_NUM) // ANCHO_COL))

    def seleccionar_todo(self) -> None:
        filas, cols = self.hoja.usadas()
        self.ancla.value = (0, 0)
        self.cursor.value = (max(0, filas - 1), max(0, cols - 1))

    def seleccionar_columna(self, c: int, extender: bool = False) -> None:
        filas, _ = self.hoja.usadas()
        if not extender:
            self.ancla.value = (0, c)
        self.cursor.value = (max(0, filas - 1), c)

    # -- editar ---------------------------------------------------------------------
    def empezar(self, texto: str | None = None) -> None:
        r, c = self.cursor.peek()
        self.borrador.value = self.hoja.escrito(r, c) if texto is None else texto
        self.editando.value = (r, c)

    def confirmar(self, dr: int = 1, dc: int = 0, mover: bool = True) -> None:
        """Guarda lo editado y pasa a la celda de al lado (con `mover=False`, p. ej. al
        perder el foco por un clic en otra celda, la celda activa ya la decidió el clic)."""
        pos = self.editando.peek()
        if pos is None:
            return
        self.editando.value = None
        self.hoja.escribir({pos: self.borrador.peek()}, f"Editar {nombre(*pos)}")
        if mover:
            self.ir(pos[0] + dr, pos[1] + dc)

    def cancelar(self) -> None:
        self.editando.value = None

    # -- teclado (con la rejilla enfocada y sin editar) ----------------------------------
    def tecla(self, event: Any, pagina: int = 20) -> bool:
        """Navegar, seleccionar, empezar a editar y borrar. Devuelve si la usó."""
        k, shift, ctrl = event.key, event.shift, event.ctrl
        r, c = self.cursor.peek()
        filas, cols = self.hoja.usadas()
        flechas = {"ArrowUp": (-1, 0), "ArrowDown": (1, 0), "ArrowLeft": (0, -1), "ArrowRight": (0, 1)}
        if k in flechas:
            dr, dc = flechas[k]
            if ctrl:  # al borde de los datos (o de la hoja)
                destino = (0 if dr < 0 else max(filas - 1, 0), c) if dr else (r, 0 if dc < 0 else max(cols - 1, 0))
                self.ir(*destino, extender=shift)
            else:
                self.mover(dr, dc, extender=shift)
        elif k == "Tab":
            self.mover(0, -1 if shift else 1)
        elif k == "Enter":
            self.mover(-1 if shift else 1, 0)
        elif k in ("PageDown", "PageUp"):
            self.mover(pagina if k == "PageDown" else -pagina, 0, extender=shift)
        elif k == "Home":
            self.ir(0 if ctrl else r, 0, extender=shift)
        elif k == "End":
            self.ir(max(filas - 1, 0) if ctrl else r, max(cols - 1, 0), extender=shift)
        elif k == "F2":
            self.empezar()
        elif k in ("Delete", "Backspace"):
            self.hoja.borrar(*self.rango.peek())
        elif k == "Escape":
            self.ancla.value = self.cursor.peek()
        elif k.lower() == "a" and ctrl:
            self.seleccionar_todo()
        elif event.text and event.text.isprintable() and not (ctrl or event.alt or event.meta):
            self.empezar(event.text)
        else:
            return False
        return True
