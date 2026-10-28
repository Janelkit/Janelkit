"""La hoja: lo escrito en cada celda, sus valores calculados, deshacer/rehacer y CSV.

Lo escrito vive en un diccionario normal (`(fila, col) -> texto`): abrir un CSV de
10 000 × 26 no crea 260 000 estados. Una celda reactiva (`Celda`: un `state` con lo
escrito y un `computed` con su valor) se crea la primera vez que alguien la lee: la vista
al mostrarla o una fórmula que la usa. Como los `computed` son perezosos, cambiar una
celda de la que dependen mil fórmulas solo recalcula las que están a la vista.

Todo cambio pasa por `escribir()`, que anota en el historial (`janelkit.History`) lo
que había y lo que hay. Como el diccionario de lo escrito no es reactivo, el historial
no lo ve: el paso se anota con `add()` y dos funciones que aplican cada versión.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from janelkit import Computed, History, State, batch, computed, state, untracked

from services.formulas import Error, FalloFormula, evaluar, mostrar, nombre

FILAS = 10_000
COLUMNAS = 26
LIMITE_DESHACER = 500

Pos = tuple[int, int]


class Celda:
    __slots__ = ("raw", "valor", "texto")

    def __init__(self, raw: State[str], valor: Computed[Any], texto: Computed[str]):
        self.raw, self.valor, self.texto = raw, valor, texto


class Hoja:
    def __init__(self, datos: dict[Pos, str] | None = None, filas: int = FILAS, columnas: int = COLUMNAS):
        self.filas, self.columnas = filas, columnas
        self._raw: dict[Pos, str] = {k: v for k, v in (datos or {}).items() if v}
        self._celdas: dict[Pos, Celda] = {}
        self._evaluando: set[Pos] = set()
        self.historial = History(limit=LIMITE_DESHACER)
        self.separador = ","  # el del último CSV abierto; se usa al guardar

    # -- lectura ------------------------------------------------------------------
    def celda(self, r: int, c: int) -> Celda:
        pos = (r, c)
        celda = self._celdas.get(pos)
        if celda is None:
            raw = state(self._raw.get(pos, ""))
            valor = computed(lambda: self._calcular(pos, raw.value))
            texto = computed(lambda: mostrar(valor.value))
            celda = self._celdas[pos] = Celda(raw, valor, texto)
        return celda

    def texto(self, r: int, c: int) -> str:
        """Lo que se muestra (reactivo)."""
        return self.celda(r, c).texto.value

    def escrito(self, r: int, c: int) -> str:
        """Lo que hay escrito (reactivo): la fórmula, no su resultado."""
        return self.celda(r, c).raw.value

    def valor(self, r: int, c: int) -> Any:
        return self.celda(r, c).valor.value

    def _leer(self, r: int, c: int) -> Any:
        if not (0 <= r < self.filas and 0 <= c < self.columnas):
            raise FalloFormula("#REF!")
        if (r, c) in self._evaluando:
            self.celda(r, c).raw.value  # dependencia de lo escrito: si se rompe el ciclo, se recalcula
            raise FalloFormula("#CICLO!")
        return self.celda(r, c).valor.value  # también si está vacía: así la fórmula se entera si se escribe

    def _calcular(self, pos: Pos, texto: str) -> Any:
        if not texto.startswith("="):
            return evaluar(texto, self._leer)
        self._evaluando.add(pos)
        try:
            return evaluar(texto, self._leer)
        finally:
            self._evaluando.discard(pos)

    def usadas(self) -> tuple[int, int]:
        """(filas, columnas) hasta la última celda con algo escrito."""
        if not self._raw:
            return 0, 0
        return max(r for r, _ in self._raw) + 1, max(c for _, c in self._raw) + 1

    # -- cambios ------------------------------------------------------------------
    def escribir(self, cambios: dict[Pos, str], que: str) -> None:
        """Aplica `cambios` como un solo paso que se puede deshacer."""
        antes = {pos: self._raw.get(pos, "") for pos in cambios}
        cambios = {pos: v for pos, v in cambios.items() if antes[pos] != v}
        if not cambios:
            return
        antes = {pos: antes[pos] for pos in cambios}
        self._aplicar(cambios)
        self.historial.add(que, undo=lambda: self._aplicar(antes), redo=lambda: self._aplicar(cambios))

    def deshacer(self) -> None:
        self.historial.undo()

    def rehacer(self) -> None:
        self.historial.redo()

    def _aplicar(self, cambios: dict[Pos, str]) -> None:
        with batch():
            for pos, texto in cambios.items():
                if texto:
                    self._raw[pos] = texto
                else:
                    self._raw.pop(pos, None)
                celda = self._celdas.get(pos)
                if celda is not None:  # si no existe, nadie la lee todavía: se creará con el texto nuevo
                    celda.raw.value = texto

    def borrar(self, r0: int, c0: int, r1: int, c1: int) -> None:
        cambios = {(r, c): "" for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if (r, c) in self._raw}
        self.escribir(cambios, f"Borrar {_rango(r0, c0, r1, c1)}")

    # -- portapapeles (texto separado por tabuladores, como Excel) ---------------------
    def copiar(self, r0: int, c0: int, r1: int, c1: int) -> str:
        out = io.StringIO()
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
        for r in range(r0, r1 + 1):
            w.writerow([self._raw.get((r, c), "") for c in range(c0, c1 + 1)])
        return out.getvalue()

    def pegar(self, r: int, c: int, texto: str) -> tuple[int, int, int, int] | None:
        """Pega en (r, c) un bloque separado por tabuladores; devuelve el rango pegado."""
        filas = list(csv.reader(io.StringIO(texto.replace("\r\n", "\n")), delimiter="\t"))
        while filas and filas[-1] in ([], [""]):
            filas.pop()
        if not filas:
            return None
        cambios = {
            (r + i, c + j): v
            for i, fila in enumerate(filas)
            for j, v in enumerate(fila)
            if r + i < self.filas and c + j < self.columnas
        }
        r1 = min(self.filas, r + len(filas)) - 1
        c1 = min(self.columnas, c + max(map(len, filas))) - 1
        self.escribir(cambios, f"Pegar en {_rango(r, c, r1, c1)}")
        return r, c, r1, c1

    # -- ordenar ------------------------------------------------------------------
    def ordenar(self, col: int, descendente: bool = False, desde: int = 0) -> None:
        """Ordena las filas usadas (desde `desde`) por el valor de la columna `col`.

        Las vacías van al final. Las fórmulas se mueven tal cual: sus referencias no se
        ajustan (ver HALLAZGOS.md)."""
        filas_usadas, cols = self.usadas()
        if filas_usadas <= desde + 1:
            return
        with untracked():
            valores = {r: self.valor(r, col) for r in range(desde, filas_usadas)}

        def clave(r: int) -> tuple[int, Any]:
            v = valores[r]
            if isinstance(v, float):
                return (0, v)
            if isinstance(v, Error):
                return (2, str(v))
            return (1, v.casefold()) if v is not None else (3, "")

        llenas = [r for r in valores if valores[r] is not None]
        vacias = [r for r in valores if valores[r] is None]
        grupos: dict[int, list[int]] = {}
        for r in sorted(llenas, key=clave):
            grupos.setdefault(clave(r)[0], []).append(r)
        orden = [r for g in sorted(grupos) for r in (reversed(grupos[g]) if descendente else grupos[g])] + vacias
        cambios = {
            (desde + i, c): self._raw.get((origen, c), "")
            for i, origen in enumerate(orden)
            for c in range(cols)
        }
        sentido = "descendente" if descendente else "ascendente"
        self.escribir(cambios, f"Ordenar por {nombre(0, col)[0]} ({sentido})")

    # -- archivo ------------------------------------------------------------------
    def abrir(self, archivo: Path) -> None:
        """Sustituye todo por el contenido de un CSV (no se puede deshacer)."""
        texto = archivo.read_text(encoding="utf-8-sig")
        self.separador = _separador(texto)
        datos: dict[Pos, str] = {}
        for r, fila in enumerate(csv.reader(io.StringIO(texto), delimiter=self.separador)):
            if r >= self.filas:
                break
            for c, v in enumerate(fila[: self.columnas]):
                if v:
                    datos[(r, c)] = v
        self.reemplazar(datos)

    def reemplazar(self, datos: dict[Pos, str]) -> None:
        self._raw = dict(datos)
        with batch():
            for pos, celda in self._celdas.items():
                celda.raw.value = self._raw.get(pos, "")
        self.historial.clear()
        self.historial.mark_saved()

    def guardar(self, archivo: Path) -> None:
        filas, cols = self.usadas()
        out = io.StringIO()
        w = csv.writer(out, delimiter=self.separador, lineterminator="\n")
        for r in range(filas):
            w.writerow([self._raw.get((r, c), "") for c in range(cols)])
        archivo.write_text(out.getvalue(), encoding="utf-8")
        self.historial.mark_saved()


def _separador(texto: str) -> str:
    muestra = texto[:4096]
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def _rango(r0: int, c0: int, r1: int, c1: int) -> str:
    return nombre(r0, c0) if (r0, c0) == (r1, c1) else f"{nombre(r0, c0)}:{nombre(r1, c1)}"


def ejemplo(filas: int = FILAS, columnas: int = COLUMNAS) -> dict[Pos, str]:
    """Datos de demostración: números en A..Y y en Z la suma de cada fila; abajo, totales."""
    datos: dict[Pos, str] = {(0, c): f"Col {nombre(0, c)[0]}" for c in range(columnas)}
    for r in range(1, filas):
        for c in range(columnas - 1):
            datos[(r, c)] = str((r * 7 + c * 13) % 100)
        datos[(r, columnas - 1)] = f"=SUMA(A{r + 1}:{nombre(0, columnas - 2)[0]}{r + 1})"
    return datos
