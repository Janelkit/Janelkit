"""Los datos de la aplicación: proyectos, directorio de personas, un historial de deshacer
común y el archivo JSON.

    {"personas": [{"id", "nombre", "color", "correo", "rol"}],
     "proyectos": [{"id", "nombre", "color", "descripcion", "archivado",
                    "miembros": [{"persona", "rol"}], "etiquetas": {nombre: color},
                    "columnas": [{"id", "nombre", "tarjetas": [...]}]}]}

Las tarjetas guardan el id de su responsable: renombrar a una persona se ve al momento
en todos los proyectos. La última columna de un proyecto es la «de hecho» (su progreso).
Deshacer no está en el núcleo de JanelKit (docs/alcance.md: es de `janelkit-store`).
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Callable

from janelkit import batch, state, timeout
from services.tablero import ETIQUETAS, Tablero, columnas_ejemplo

def cuenta(n: int, nombre: str, plural: str | None = None) -> str:
    """«1 tarjeta», «3 tarjetas», «1 proyecto activo» / «2 proyectos activos» (con `plural`)."""
    return f"{n} {nombre}" if n == 1 else f"{n} {plural or nombre + 's'}"


COLORES = ["#1971c2", "#2f9e44", "#e8590c", "#ae3ec9", "#0c8599", "#e03131", "#5c940d", "#495057"]
ROLES = ["Responsable", "Colaborador", "Observador"]


class Historial:
    """Deshacer y rehacer para toda la aplicación. Cada paso es (qué, op, args); `op(*args)`
    aplica el cambio y devuelve su inversa."""

    def __init__(self, al_cambiar: Callable[[], Any]):
        self._deshacer: list[tuple[str, Callable, tuple]] = []
        self._rehacer: list[tuple[str, Callable, tuple]] = []
        self.puede_deshacer = state("")  # descripción de lo que se desharía ("" si nada)
        self.puede_rehacer = state("")
        self._al_cambiar = al_cambiar

    def hacer(self, que: str, op: Callable, *args: Any) -> None:
        self._deshacer.append((que, *op(*args)))
        self._rehacer.clear()
        self._cambio()

    def deshacer(self) -> None:
        if self._deshacer:
            que, op, args = self._deshacer.pop()
            self._rehacer.append((que, *op(*args)))
            self._cambio()

    def rehacer(self) -> None:
        if self._rehacer:
            que, op, args = self._rehacer.pop()
            self._deshacer.append((que, *op(*args)))
            self._cambio()

    def _cambio(self) -> None:
        self.puede_deshacer.value = self._deshacer[-1][0] if self._deshacer else ""
        self.puede_rehacer.value = self._rehacer[-1][0] if self._rehacer else ""
        self._al_cambiar()


class Datos:
    def __init__(self, archivo: Path | None = None, datos: dict[str, Any] | None = None):
        self.archivo = archivo
        if datos is None:
            datos = json.loads(archivo.read_text(encoding="utf-8")) if archivo and archivo.exists() else ejemplo()
        self.personas = state(datos["personas"])
        self.proyectos = state(datos["proyectos"])
        tarjetas = [t for p in datos["proyectos"] for c in p["columnas"] for t in c["tarjetas"]]
        self._contador = max((int(re.sub(r"\D", "", x["id"]) or 0) for x in [*tarjetas, *datos["personas"], *datos["proyectos"]]),
                             default=0)
        self.historial = Historial(self._programar_guardado)
        self._tableros: dict[str, Tablero] = {}
        self._guardado = None

    # -- consultas -------------------------------------------------------------
    def proyecto(self, pid: str) -> Any:
        return next(p for p in self.proyectos.value if p["id"] == pid)

    def persona(self, ident: str) -> Any | None:
        return next((p for p in self.personas.value if p["id"] == ident), None)

    def nombre(self, ident: str) -> str:
        p = self.persona(ident) if ident else None
        return p["nombre"] if p else ""

    def iniciales(self, ident: str) -> str:
        return "".join(w[0] for w in self.nombre(ident).split()[:2]).upper()

    def tablero(self, pid: str) -> Tablero:
        """El tablero de un proyecto (uno por proyecto, se reutiliza)."""
        if pid not in self._tableros:
            self._tableros[pid] = Tablero(self.proyecto(pid), self.historial, self._id_tarjeta)
        return self._tableros[pid]

    def resumen(self, p: Any) -> dict[str, Any]:
        """Nº de tarjetas y progreso (las de la última columna) de un proyecto."""
        total = sum(len(c["tarjetas"]) for c in p["columnas"])
        hechas = len(p["columnas"][-1]["tarjetas"]) if p["columnas"] else 0
        return {"total": total, "progreso": hechas / total if total else 0.0}

    def tarjetas_de(self, ident: str) -> list[tuple[Any, Any, Any]]:
        """(proyecto, columna, tarjeta) de las tarjetas de una persona, en todos los proyectos activos."""
        return [(p, c, t) for p in self.proyectos.value if not p["archivado"]
                for c in p["columnas"] for t in c["tarjetas"] if t["responsable"] == ident]

    def cuentas(self) -> dict[str, int]:
        """Nº de tarjetas de cada persona (por id), en todos los proyectos."""
        n: dict[str, int] = {}
        for p in self.proyectos.value:
            for c in p["columnas"]:
                for t in c["tarjetas"]:
                    if t["responsable"]:
                        n[t["responsable"]] = n.get(t["responsable"], 0) + 1
        return n

    def cuantas_de(self, ident: str) -> int:
        return sum(1 for p in self.proyectos.value for c in p["columnas"] for t in c["tarjetas"] if t["responsable"] == ident)

    # -- operaciones (cada una devuelve su inversa) --------------------------------
    def _poner(self, lista: str, indice: int, valor: dict) -> tuple[Callable, tuple]:
        getattr(self, lista).value.insert(indice, valor)
        return self._quitar, (lista, valor["id"])

    def _quitar(self, lista: str, ident: str) -> tuple[Callable, tuple]:
        items = getattr(self, lista).value
        i = next(i for i, x in enumerate(items) if x["id"] == ident)
        return self._poner, (lista, i, items.pop(i))

    def _editar(self, obj: Any, campos: dict) -> tuple[Callable, tuple]:
        antes = {k: obj[k] for k in campos}
        with batch():
            for k, v in campos.items():
                obj[k] = v
        return self._editar, (obj, antes)

    def _quitar_persona(self, ident: str) -> tuple[Callable, tuple]:
        """Quita a la persona del directorio, de los proyectos y de sus tarjetas."""
        with batch():
            inversa = self._quitar("personas", ident)
            miembros = []
            for p in self.proyectos.value:
                for i, m in enumerate(p["miembros"]):
                    if m["persona"] == ident:
                        miembros.append((p, i, p["miembros"].pop(i)))
                        break
            tarjetas = [t for p in self.proyectos.value for c in p["columnas"] for t in c["tarjetas"] if t["responsable"] == ident]
            for t in tarjetas:
                t["responsable"] = ""
        return self._volver_persona, (inversa, miembros, tarjetas)

    def _volver_persona(self, inversa: tuple, miembros: list, tarjetas: list) -> tuple[Callable, tuple]:
        op, args = inversa
        with batch():
            op(*args)
            for p, i, m in reversed(miembros):
                p["miembros"].insert(i, m)
            for t in tarjetas:
                t["responsable"] = args[2]["id"]
        return self._quitar_persona, (args[2]["id"],)

    def _miembro(self, p: Any, ident: str, rol: str | None, tarjetas: tuple = ()) -> tuple[Callable, tuple]:
        """Añade o cambia el rol (`rol`) o quita (None) a una persona de un proyecto. Al quitarla, sus
        tarjetas del proyecto se quedan sin responsable; `tarjetas` las devuelve al deshacer."""
        miembros = p["miembros"]
        i = next((i for i, m in enumerate(miembros) if m["persona"] == ident), None)
        antes = miembros[i]["rol"] if i is not None else None
        quitadas: tuple = ()
        with batch():
            if rol is None:
                if i is not None:
                    miembros.pop(i)
                quitadas = tuple(t for c in p["columnas"] for t in c["tarjetas"] if t["responsable"] == ident)
                for t in quitadas:
                    t["responsable"] = ""
            elif i is not None:
                miembros[i]["rol"] = rol
            else:
                miembros.append({"persona": ident, "rol": rol})
            for t in tarjetas:
                t["responsable"] = ident
        return self._miembro, (p, ident, antes, quitadas)

    # -- acciones de la interfaz ------------------------------------------------------
    def nuevo_proyecto(self, nombre: str = "Proyecto nuevo") -> str:
        pid = self._id("p")
        p = {"id": pid, "nombre": nombre, "color": COLORES[len(self.proyectos.value) % len(COLORES)], "descripcion": "",
             "archivado": False, "miembros": [], "etiquetas": dict(ETIQUETAS),
             "columnas": [{"id": f"{pid}c{i + 1}", "nombre": n, "tarjetas": []}
                          for i, n in enumerate(["Pendiente", "En curso", "Hecho"])]}
        self.historial.hacer(f"crear «{nombre}»", self._poner, "proyectos", len(self.proyectos.value), p)
        return pid

    def editar_proyecto(self, pid: str, **campos: Any) -> None:
        p = self.proyecto(pid)
        campos = {k: v for k, v in campos.items() if p[k] != v}
        if campos:
            que = "archivar" if campos.get("archivado") else "recuperar" if "archivado" in campos else "editar"
            self.historial.hacer(f"{que} «{p['nombre']}»", self._editar, p, campos)

    def borrar_proyecto(self, pid: str) -> None:
        self.historial.hacer(f"borrar «{self.proyecto(pid)['nombre']}»", self._quitar, "proyectos", pid)

    def nueva_persona(self, nombre: str = "Persona nueva") -> str:
        ident = self._id("u")
        p = {"id": ident, "nombre": nombre, "color": COLORES[len(self.personas.value) % len(COLORES)], "correo": "", "rol": ""}
        self.historial.hacer(f"añadir a «{nombre}»", self._poner, "personas", len(self.personas.value), p)
        return ident

    def editar_persona(self, ident: str, **campos: Any) -> None:
        p = self.persona(ident)
        campos = {k: v for k, v in campos.items() if p[k] != v}
        if campos:
            self.historial.hacer(f"editar a «{p['nombre']}»", self._editar, p, campos)

    def borrar_persona(self, ident: str) -> None:
        self.historial.hacer(f"quitar a «{self.nombre(ident)}»", self._quitar_persona, ident)

    def poner_miembro(self, pid: str, ident: str, rol: str | None) -> None:
        p = self.proyecto(pid)
        que = f"{'quitar' if rol is None else 'añadir'} a «{self.nombre(ident)}» en «{p['nombre']}»"
        self.historial.hacer(que, self._miembro, p, ident, rol)

    # -- archivo ------------------------------------------------------------------------
    def _programar_guardado(self) -> None:
        if self.archivo is not None and self._guardado is None:  # un guardado por ráfaga de cambios
            self._guardado = timeout(300)(self.guardar)

    def guardar(self) -> None:
        self._guardado = None
        if self.archivo is not None:
            datos = {"personas": self.personas.peek(), "proyectos": self.proyectos.peek()}
            self.archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    def _id(self, prefijo: str) -> str:
        self._contador += 1
        return f"{prefijo}{self._contador}"

    def _id_tarjeta(self) -> str:
        return self._id("t")


def importar_kanban(datos_kanban: dict[str, Any], personas: list[dict[str, Any]], pid: str = "p1",
                    nombre: str = "Tablero importado") -> dict[str, Any]:
    """Un proyecto a partir del `tablero.json` del reto 3. Los responsables (nombres) pasan a
    ser ids del directorio; los que no están se añaden a `personas`."""
    por_nombre = {p["nombre"]: p["id"] for p in personas}
    contador = len(personas)
    for c in datos_kanban["columnas"]:
        for t in c["tarjetas"]:
            nombre_persona = t["responsable"]
            if nombre_persona and nombre_persona not in por_nombre:
                contador += 1
                por_nombre[nombre_persona] = f"u-k{contador}"
                personas.append({"id": f"u-k{contador}", "nombre": nombre_persona,
                                 "color": COLORES[contador % len(COLORES)], "correo": "", "rol": ""})
            t["responsable"] = por_nombre.get(nombre_persona, "")
            t["id"] = f"k{t['id']}"  # los ids de tarjeta son únicos en toda la aplicación
        c["id"] = f"{pid}{c['id']}"
    usados = {t["responsable"] for c in datos_kanban["columnas"] for t in c["tarjetas"]} - {""}
    return {"id": pid, "nombre": nombre, "color": COLORES[0], "descripcion": "Importado del reto 3 (Kanban).",
            "archivado": False, "miembros": [{"persona": u, "rol": "Colaborador"} for u in sorted(usados)],
            "etiquetas": dict(ETIQUETAS), "columnas": datos_kanban["columnas"]}


def ejemplo(proyectos: int = 4, columnas: int = 4, tarjetas: int = 6, personas: int = 8, semilla: int = 7) -> dict[str, Any]:
    """Datos de demostración (o de medición), deterministas."""
    rnd = random.Random(semilla)
    nombres = ["Ana García", "Luis Pérez", "Marta Ruiz", "Pablo Díaz", "Sofía León", "Iván Mora", "Elena Gil",
               "Hugo Sanz", "Clara Vega", "Raúl Peña"]  # fmt: skip
    gente = [{"id": f"u{i + 1}", "nombre": nombres[i % len(nombres)] + ("" if i < len(nombres) else f" {i + 1}"),
              "color": COLORES[i % len(COLORES)], "correo": f"persona{i + 1}@ejemplo.org", "rol": rnd.choice(ROLES)}
             for i in range(personas)]
    ids = [p["id"] for p in gente]
    temas = ["Web pública", "App móvil", "Migración a la nube", "Portal de clientes", "Informes", "Facturación",
             "Intranet", "Soporte", "Datos", "Seguridad"]  # fmt: skip
    contador = [personas + proyectos]
    lista = []
    for i in range(proyectos):
        pid = f"p{i + 1}"
        equipo = rnd.sample(ids, min(len(ids), rnd.randint(2, 5)))
        lista.append({
            "id": pid, "nombre": temas[i % len(temas)] + ("" if i < len(temas) else f" {i + 1}"),
            "color": COLORES[i % len(COLORES)], "descripcion": "", "archivado": False,
            "miembros": [{"persona": u, "rol": "Responsable" if j == 0 else "Colaborador"} for j, u in enumerate(equipo)],
            "etiquetas": dict(ETIQUETAS),
            "columnas": columnas_ejemplo(pid, columnas, tarjetas, equipo, rnd, contador),
        })
    return {"personas": gente, "proyectos": lista}
