"""El tablero de un proyecto: columnas con tarjetas (viene del reto 3, el Kanban).

Todo cambio pasa por `Tablero.hacer(...)`: aplica una operación y guarda la inversa en
el historial común de la aplicación (`datos.Historial`), que dice en qué proyecto
ocurrió cada paso. Las operaciones mueven las tarjetas en sitio dentro de las listas
reactivas, así que `{#each}` mueve una fila en vez de volver a crear la columna entera.

Las tarjetas guardan el id de su responsable (una persona del directorio), no su nombre.
"""
from __future__ import annotations

import datetime as dt
import random
from typing import Any, Callable

from janelkit import batch, computed

ETIQUETAS = {
    "error": "#e03131", "mejora": "#2f9e44", "diseño": "#ae3ec9",
    "urgente": "#f08c00", "docs": "#1971c2", "técnico": "#495057",
}  # fmt: skip  (las de un proyecto nuevo)


class Tablero:
    def __init__(self, proyecto: Any, historial: Any, nuevo_id: Callable[[], str]):
        self.proyecto = proyecto
        self.historial = historial
        self._nuevo_id = nuevo_id
        self.columnas = computed(lambda: proyecto["columnas"])
        self._siguiente_col = 1 + max((int(c["id"].rsplit("c", 1)[1]) for c in proyecto["columnas"]), default=0)

    @property
    def etiquetas(self) -> dict[str, str]:
        return self.proyecto["etiquetas"]

    # -- consultas -------------------------------------------------------------
    def columna(self, col_id: str) -> Any:
        return next(c for c in self.proyecto["columnas"] if c["id"] == col_id)

    def donde(self, tarjeta_id: str) -> tuple[Any, int]:
        """Columna e índice de una tarjeta."""
        for c in self.proyecto["columnas"]:
            for i, t in enumerate(c["tarjetas"]):
                if t["id"] == tarjeta_id:
                    return c, i
        raise KeyError(tarjeta_id)

    def tarjeta(self, tarjeta_id: str) -> Any:
        c, i = self.donde(tarjeta_id)
        return c["tarjetas"][i]

    def hacer(self, que: str, op: Callable, *args: Any) -> None:
        """Aplica `op(*args)`, que devuelve su inversa como (op, args)."""
        self.historial.hacer(f"{que} en «{self.proyecto['nombre']}»", op, *args)

    # -- operaciones (cada una devuelve su inversa) --------------------------------
    def _mover(self, tarjeta_id: str, col_id: str, indice: int) -> tuple[Callable, tuple]:
        origen, i = self.donde(tarjeta_id)
        destino = self.columna(col_id)
        with batch():
            if origen is destino:
                lista = origen["tarjetas"]
                indice = max(0, min(indice, len(lista) - 1))
                lista.insert(indice, lista.pop(i))
            else:
                t = origen["tarjetas"].pop(i)
                destino["tarjetas"].insert(max(0, min(indice, len(destino["tarjetas"]))), t)
        return self._mover, (tarjeta_id, origen["id"], i)

    def _poner(self, col_id: str, indice: int, tarjeta: dict) -> tuple[Callable, tuple]:
        self.columna(col_id)["tarjetas"].insert(indice, tarjeta)
        return self._quitar, (tarjeta["id"],)

    def _quitar(self, tarjeta_id: str) -> tuple[Callable, tuple]:
        c, i = self.donde(tarjeta_id)
        t = c["tarjetas"].pop(i)
        return self._poner, (c["id"], i, dict(t))

    def _editar(self, tarjeta_id: str, campos: dict) -> tuple[Callable, tuple]:
        t = self.tarjeta(tarjeta_id)
        antes = {k: t[k] for k in campos}
        with batch():
            for k, v in campos.items():
                t[k] = v
        return self._editar, (tarjeta_id, antes)

    def _poner_columna(self, indice: int, columna: dict) -> tuple[Callable, tuple]:
        self.proyecto["columnas"].insert(indice, columna)
        return self._quitar_columna, (columna["id"],)

    def _quitar_columna(self, col_id: str) -> tuple[Callable, tuple]:
        cols = self.proyecto["columnas"]
        i = next(i for i, c in enumerate(cols) if c["id"] == col_id)
        c = cols.pop(i)
        return self._poner_columna, (i, c)

    def _mover_columna(self, col_id: str, indice: int) -> tuple[Callable, tuple]:
        cols = self.proyecto["columnas"]
        i = next(i for i, c in enumerate(cols) if c["id"] == col_id)
        cols.insert(max(0, min(indice, len(cols) - 1)), cols.pop(i))
        return self._mover_columna, (col_id, i)

    def _renombrar(self, col_id: str, nombre: str) -> tuple[Callable, tuple]:
        c = self.columna(col_id)
        antes, c["nombre"] = c["nombre"], nombre
        return self._renombrar, (col_id, antes)

    # -- acciones de la interfaz ------------------------------------------------------
    def mover(self, tarjeta_id: str, col_id: str, indice: int) -> None:
        origen, i = self.donde(tarjeta_id)
        if origen["id"] == col_id and i == indice:
            return
        self.hacer(f"mover «{self.tarjeta(tarjeta_id)['titulo']}»", self._mover, tarjeta_id, col_id, indice)

    def mover_a(self, tarjeta_id: str, paso: int) -> None:
        """A la columna anterior (-1) o siguiente (+1), arriba del todo."""
        cols = self.proyecto["columnas"]
        c, _ = self.donde(tarjeta_id)
        j = next(i for i, x in enumerate(cols) if x is c) + paso
        if 0 <= j < len(cols):
            self.mover(tarjeta_id, cols[j]["id"], 0)

    def subir(self, tarjeta_id: str, paso: int) -> None:
        c, i = self.donde(tarjeta_id)
        if 0 <= i + paso < len(c["tarjetas"]):
            self.mover(tarjeta_id, c["id"], i + paso)

    def nueva(self, col_id: str, titulo: str = "Nueva tarjeta") -> str:
        t = {"id": self._nuevo_id(), "titulo": titulo, "descripcion": "", "etiquetas": [], "responsable": "", "fecha": ""}
        self.hacer("añadir tarjeta", self._poner, col_id, len(self.columna(col_id)["tarjetas"]), t)
        return t["id"]

    def duplicar(self, tarjeta_id: str) -> str:
        c, i = self.donde(tarjeta_id)
        t = dict(self.tarjeta(tarjeta_id), id=self._nuevo_id())
        t["etiquetas"] = list(t["etiquetas"])
        self.hacer(f"duplicar «{t['titulo']}»", self._poner, c["id"], i + 1, t)
        return t["id"]

    def borrar(self, tarjeta_id: str) -> None:
        self.hacer(f"borrar «{self.tarjeta(tarjeta_id)['titulo']}»", self._quitar, tarjeta_id)

    def editar(self, tarjeta_id: str, **campos: Any) -> None:
        t = self.tarjeta(tarjeta_id)
        campos = {k: v for k, v in campos.items() if t[k] != v}
        if campos:
            self.hacer(f"editar «{t['titulo']}»", self._editar, tarjeta_id, campos)

    def nueva_columna(self, nombre: str = "Nueva columna") -> str:
        c = {"id": f"{self.proyecto['id']}c{self._siguiente_col}", "nombre": nombre, "tarjetas": []}
        self._siguiente_col += 1
        self.hacer("añadir columna", self._poner_columna, len(self.proyecto["columnas"]), c)
        return c["id"]

    def borrar_columna(self, col_id: str) -> None:
        self.hacer(f"borrar columna «{self.columna(col_id)['nombre']}»", self._quitar_columna, col_id)

    def renombrar(self, col_id: str, nombre: str) -> None:
        if nombre and nombre != self.columna(col_id)["nombre"]:
            self.hacer("renombrar columna", self._renombrar, col_id, nombre)

    def mover_columna(self, col_id: str, indice: int) -> None:
        cols = self.proyecto["columnas"]
        if next(i for i, c in enumerate(cols) if c["id"] == col_id) != indice:
            self.hacer(f"mover columna «{self.columna(col_id)['nombre']}»", self._mover_columna, col_id, indice)


def coincide(tarjeta: Any, texto: str, etiqueta: str, persona: str) -> bool:
    """La búsqueda y los filtros de la barra (las que no coinciden se atenúan). `persona` es un id."""
    if etiqueta and etiqueta not in tarjeta["etiquetas"]:
        return False
    if persona and tarjeta["responsable"] != persona:
        return False
    texto = texto.strip().lower()
    return not texto or texto in tarjeta["titulo"].lower() or texto in tarjeta["descripcion"].lower()


def columnas_ejemplo(pid: str, columnas: int, tarjetas: int, personas: list[str], rnd: random.Random,
                     contador: list[int]) -> list[dict[str, Any]]:
    """Columnas de demostración (o de medición) con datos deterministas. `contador` da ids únicos."""
    nombres = ["Pendiente", "En curso", "Revisión", "Hecho"]
    verbos = ["Revisar", "Diseñar", "Corregir", "Documentar", "Probar", "Migrar", "Medir", "Preparar"]
    cosas = ["el inicio de sesión", "la exportación", "los permisos", "la búsqueda", "el panel", "las notificaciones",
             "la API de pagos", "el instalador", "los informes", "la caché"]  # fmt: skip
    hoy = dt.date(2026, 10, 27)
    cols = []
    for c in range(columnas):
        lista = []
        for _ in range(tarjetas):
            contador[0] += 1
            lista.append({
                "id": f"t{contador[0]}",
                "titulo": f"{rnd.choice(verbos)} {rnd.choice(cosas)}",
                "descripcion": "",
                "etiquetas": rnd.sample(list(ETIQUETAS), rnd.randint(0, 2)),
                "responsable": rnd.choice(personas + [""]),
                "fecha": (hoy + dt.timedelta(days=rnd.randint(-5, 30))).isoformat() if rnd.random() < 0.6 else "",
            })
        nombre = nombres[c] if c < len(nombres) else f"Columna {c + 1}"
        cols.append({"id": f"{pid}c{c + 1}", "nombre": nombre, "tarjetas": lista})
    return cols
