"""El tablero: columnas con tarjetas, deshacer/rehacer y el archivo JSON.

Cada acción es un paso del historial (`janelkit.History`): mueve las tarjetas en
sitio dentro de las listas reactivas, y deshacer devuelve esas listas a como
estaban. Como los objetos son los mismos, `{#each}` mueve una fila en vez de
volver a crear la columna entera.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from janelkit import History, state, timeout

ETIQUETAS = {
    "error": "#e03131", "mejora": "#2f9e44", "diseño": "#ae3ec9",
    "urgente": "#f08c00", "docs": "#1971c2", "técnico": "#495057",
}  # fmt: skip
PERSONAS = ["Ana", "Luis", "Marta", "Pablo", "Sofía", "Iván"]


class Tablero:
    def __init__(self, archivo: Path | None = None, datos: dict[str, Any] | None = None):
        self.archivo = archivo
        if datos is None:
            datos = json.loads(archivo.read_text(encoding="utf-8")) if archivo and archivo.exists() else ejemplo(4, 6)
        self.columnas = state(datos["columnas"])
        self._siguiente = 1 + max((int(t["id"][1:]) for c in datos["columnas"] for t in c["tarjetas"]), default=0)
        self._siguiente_col = 1 + max((int(c["id"][1:]) for c in datos["columnas"]), default=0)
        self.historial = History()
        self._guardado = None

    # -- consultas -------------------------------------------------------------
    def columna(self, col_id: str) -> Any:
        return next(c for c in self.columnas.peek() if c["id"] == col_id)

    def donde(self, tarjeta_id: str) -> tuple[Any, int]:
        """Columna e índice de una tarjeta."""
        for c in self.columnas.peek():
            for i, t in enumerate(c["tarjetas"]):
                if t["id"] == tarjeta_id:
                    return c, i
        raise KeyError(tarjeta_id)

    def tarjeta(self, tarjeta_id: str) -> Any:
        c, i = self.donde(tarjeta_id)
        return c["tarjetas"][i]

    # -- deshacer ----------------------------------------------------------------
    @contextmanager
    def _paso(self, que: str) -> Iterator[None]:
        with self.historial.step(que):
            yield
        self._cambio()

    def deshacer(self) -> None:
        if self.historial.undo() is not None:
            self._cambio()

    def rehacer(self) -> None:
        if self.historial.redo() is not None:
            self._cambio()

    def _cambio(self) -> None:
        if self.archivo is not None and self._guardado is None:  # un guardado por ráfaga de cambios
            self._guardado = timeout(300)(self.guardar)

    def guardar(self) -> None:
        self._guardado = None
        if self.archivo is not None:
            datos = {"columnas": self.columnas.peek()}  # las colecciones reactivas son list y dict
            self.archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- acciones de la interfaz ------------------------------------------------------
    def mover(self, tarjeta_id: str, col_id: str, indice: int) -> None:
        origen, i = self.donde(tarjeta_id)
        if origen["id"] == col_id and i == indice:
            return
        destino = self.columna(col_id)
        with self._paso(f"mover «{self.tarjeta(tarjeta_id)['titulo']}»"):
            if origen is destino:
                lista = origen["tarjetas"]
                lista.insert(max(0, min(indice, len(lista) - 1)), lista.pop(i))
            else:
                t = origen["tarjetas"].pop(i)
                destino["tarjetas"].insert(max(0, min(indice, len(destino["tarjetas"]))), t)

    def mover_a(self, tarjeta_id: str, paso: int) -> None:
        """A la columna anterior (-1) o siguiente (+1), arriba del todo."""
        cols = self.columnas.peek()
        c, _ = self.donde(tarjeta_id)
        j = next(i for i, x in enumerate(cols) if x is c) + paso
        if 0 <= j < len(cols):
            self.mover(tarjeta_id, cols[j]["id"], 0)

    def subir(self, tarjeta_id: str, paso: int) -> None:
        c, i = self.donde(tarjeta_id)
        if 0 <= i + paso < len(c["tarjetas"]):
            self.mover(tarjeta_id, c["id"], i + paso)

    def nueva(self, col_id: str, titulo: str = "Nueva tarjeta") -> str:
        t = {"id": self._id(), "titulo": titulo, "descripcion": "", "etiquetas": [], "responsable": "", "fecha": ""}
        with self._paso("añadir tarjeta"):
            self.columna(col_id)["tarjetas"].append(t)
        return t["id"]

    def duplicar(self, tarjeta_id: str) -> str:
        c, i = self.donde(tarjeta_id)
        t = dict(self.tarjeta(tarjeta_id), id=self._id())
        t["etiquetas"] = list(t["etiquetas"])
        with self._paso(f"duplicar «{t['titulo']}»"):
            c["tarjetas"].insert(i + 1, t)
        return t["id"]

    def borrar(self, tarjeta_id: str) -> None:
        c, i = self.donde(tarjeta_id)
        with self._paso(f"borrar «{c['tarjetas'][i]['titulo']}»"):
            del c["tarjetas"][i]

    def editar(self, tarjeta_id: str, **campos: Any) -> None:
        t = self.tarjeta(tarjeta_id)
        campos = {k: v for k, v in campos.items() if t[k] != v}
        if campos:
            with self._paso(f"editar «{t['titulo']}»"):
                t.update(campos)

    def nueva_columna(self, nombre: str = "Nueva columna") -> str:
        c = {"id": f"c{self._siguiente_col}", "nombre": nombre, "tarjetas": []}
        self._siguiente_col += 1
        with self._paso("añadir columna"):
            self.columnas.peek().append(c)
        return c["id"]

    def borrar_columna(self, col_id: str) -> None:
        cols = self.columnas.peek()
        with self._paso(f"borrar columna «{self.columna(col_id)['nombre']}»"):
            cols.remove(self.columna(col_id))

    def renombrar(self, col_id: str, nombre: str) -> None:
        c = self.columna(col_id)
        if nombre and nombre != c["nombre"]:
            with self._paso("renombrar columna"):
                c["nombre"] = nombre

    def mover_columna(self, col_id: str, indice: int) -> None:
        cols = self.columnas.peek()
        i = next(i for i, c in enumerate(cols) if c["id"] == col_id)
        if i != indice:
            with self._paso(f"mover columna «{cols[i]['nombre']}»"):
                cols.insert(max(0, min(indice, len(cols) - 1)), cols.pop(i))

    def _id(self) -> str:
        self._siguiente += 1
        return f"t{self._siguiente - 1}"


def coincide(tarjeta: Any, texto: str, etiqueta: str, persona: str) -> bool:
    """La búsqueda y los filtros de la barra (las que no coinciden se atenúan)."""
    if etiqueta and etiqueta not in tarjeta["etiquetas"]:
        return False
    if persona and tarjeta["responsable"] != persona:
        return False
    texto = texto.strip().lower()
    return not texto or texto in tarjeta["titulo"].lower() or texto in tarjeta["descripcion"].lower()


def ejemplo(columnas: int, tarjetas: int, semilla: int = 7) -> dict[str, Any]:
    """Un tablero de demostración (o de medición) con datos deterministas."""
    rnd = random.Random(semilla)
    nombres = ["Pendiente", "En curso", "Revisión", "Hecho"]
    verbos = ["Revisar", "Diseñar", "Corregir", "Documentar", "Probar", "Migrar", "Medir", "Preparar"]
    cosas = ["el inicio de sesión", "la exportación", "los permisos", "la búsqueda", "el panel", "las notificaciones",
             "la API de pagos", "el instalador", "los informes", "la caché"]  # fmt: skip
    hoy = dt.date(2026, 10, 27)
    n = 0
    cols = []
    for c in range(columnas):
        lista = []
        for _ in range(tarjetas):
            n += 1
            lista.append({
                "id": f"t{n}",
                "titulo": f"{rnd.choice(verbos)} {rnd.choice(cosas)}",
                "descripcion": "",
                "etiquetas": rnd.sample(list(ETIQUETAS), rnd.randint(0, 2)),
                "responsable": rnd.choice(PERSONAS + [""]),
                "fecha": (hoy + dt.timedelta(days=rnd.randint(-5, 30))).isoformat() if rnd.random() < 0.6 else "",
            })
        cols.append({"id": f"c{c + 1}", "nombre": nombres[c] if c < len(nombres) else f"Columna {c + 1}", "tarjetas": lista})
    return {"columnas": cols}
