"""Mediciones del reto 6: N proyectos de C columnas × T tarjetas y P personas
(por defecto 10 × 4 × 50 y 300, los de «Hecho cuando» en docs/challenges_to_test.md).

    python bench.py
    python bench.py --proyectos 20 --tarjetas 100 --personas 1000

Mide, en el hilo de la interfaz (desde la acción hasta sincronizar el fotograma:
eventos, Python, polish y disposición; sin el dibujado):

- montar la aplicación; abrir un proyecto (la 1.ª vez y las siguientes) y volver;
- cambiar de pestaña ({#hidden}) y de sección (Sections);
- escribir en la búsqueda de Personas; renombrar a una persona (se ve en todos los
  proyectos); mover una tarjeta y deshacer;
- la memoria al abrir y cerrar todos los proyectos varias veces.

Usa janelkit.inspect con la plataforma offscreen.
"""
from __future__ import annotations

import argparse
import gc
import os
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pct(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def line(label: str, values: list[float]) -> None:
    if len(values) == 1:
        print(f"  {label:<44} {values[0]:8.1f} ms")
    else:
        print(f"  {label:<44} p50 {statistics.median(values):6.2f}  p99 {pct(values, 0.99):6.2f}  máx {max(values):6.2f} ms  (n={len(values)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proyectos", type=int, default=10)
    ap.add_argument("--columnas", type=int, default=4)
    ap.add_argument("--tarjetas", type=int, default=50)
    ap.add_argument("--personas", type=int, default=300)
    ap.add_argument("--vueltas", type=int, default=5)
    args = ap.parse_args()
    os.environ["GESTOR_DEMO"] = f"{args.proyectos}x{args.columnas}x{args.tarjetas}x{args.personas}"

    import psutil
    from PySide6.QtCore import QCoreApplication, QEvent, Qt

    from janelkit.inspect import mount

    proc = psutil.Process()
    t0 = time.perf_counter()
    with mount(HERE / "src" / "App.janel") as app:
        app.window.resize(1400, 850)
        QCoreApplication.processEvents()
        montar = (time.perf_counter() - t0) * 1000
        win = app.window
        marks: dict[str, float] = {}
        win.beforeSynchronizing.connect(lambda: marks.setdefault("sync", time.perf_counter()), Qt.ConnectionType.DirectConnection)
        win.frameSwapped.connect(lambda: marks.setdefault("swap", time.perf_counter()), Qt.ConnectionType.DirectConnection)

        def frame(action, into: list) -> None:
            marks.clear()
            t = time.perf_counter()
            action()
            while "swap" not in marks and time.perf_counter() - t < 0.5:
                QCoreApplication.processEvents()
            into.append((marks.get("sync", time.perf_counter()) - t) * 1000)

        def calma(segundos: float = 0.2) -> None:
            """Que acaben las transiciones y se borre lo retirado. Fuera de exec(), processEvents()
            no entrega los deleteLater (filas y páginas retiradas): se entregan aquí, como el bucle real."""
            fin = time.perf_counter() + segundos
            while time.perf_counter() < fin:
                QCoreApplication.processEvents()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        datos, secciones = app.get("datos"), app.get("secciones")
        nav = secciones["proyectos"]
        proyectos = [p["id"] for p in datos.proyectos.peek()]
        Proyecto = nav.page.namespace["Proyecto"]
        total = sum(datos.resumen(p)["total"] for p in datos.proyectos.peek())
        print(f"{len(proyectos)} proyectos, {total} tarjetas, {len(datos.personas.peek())} personas")
        line("montar (compilar, crear, primer fotograma)", [montar])

        primera, abrir, volver = [], [], []
        for pid in proyectos:
            frame(lambda: nav.push(Proyecto, ident=pid), primera)
            calma()
            frame(nav.pop, volver)
            calma()
        for _ in range(args.vueltas):
            frame(lambda: nav.push(Proyecto, ident=proyectos[0]), abrir)
            calma()
            frame(nav.pop, volver)
            calma()
        print("Navegar")
        line("abrir un proyecto (1.ª vez de cada uno)", primera)
        line("abrir un proyecto (otra vez)", abrir)
        line("volver a Proyectos", volver)

        nav.push(Proyecto, ident=proyectos[0])
        calma()
        pestaña = nav.page.namespace["pestaña"]
        for p in ("miembros", "ajustes", "tablero"):  # la 1.ª vez crea cada pestaña
            pestaña.set(p)
            calma(0.05)
        pestañas = []
        for _ in range(args.vueltas * 2):
            for p in ("miembros", "tablero", "ajustes", "tablero"):
                frame(lambda: pestaña.set(p), pestañas)
        line("cambiar de pestaña (tablero de 200)", pestañas)
        for s in ("personas", "trabajo", "proyectos"):
            secciones.show(s)
            calma()
        cambios = []
        for _ in range(args.vueltas):
            for s in ("personas", "trabajo", "proyectos"):
                frame(lambda: secciones.show(s), cambios)
                calma(0.15)
        line("cambiar de sección", cambios)

        print("Editar")
        secciones.show("personas")
        calma()
        buscar = secciones["personas"].page.namespace["buscar"]
        escribir = []
        for valor in ("a", "an", "ana", "ana ", "", "l", "lu", "luis", ""):
            frame(lambda: buscar.set(valor), escribir)
        line("cada pulsación en la búsqueda de Personas", escribir)
        secciones.show("proyectos")
        calma()
        renombrar, mover, deshacer = [], [], []
        u = datos.personas.peek()[0]["id"]
        tablero = datos.tablero(proyectos[0])
        cols = tablero.columnas.peek()
        for i in range(args.vueltas * 2):
            frame(lambda: datos.editar_persona(u, nombre=f"Persona {i}"), renombrar)
            tid = cols[0]["tarjetas"][0]["id"]
            frame(lambda: tablero.mover(tid, cols[1]["id"], 0), mover)
            frame(datos.historial.deshacer, deshacer)
        line("renombrar a una persona", renombrar)
        line("mover una tarjeta (proyecto abierto)", mover)
        line("deshacer", deshacer)

        print("Memoria (abrir y cerrar todos los proyectos)")
        nav.pop()
        calma()
        print(f"  {'antes':<44} {proc.memory_info().rss / 2**20:8.0f} MB")
        for vuelta in range(4):
            for pid in proyectos:
                nav.push(Proyecto, ident=pid)
                calma(0.05)
                nav.pop()
                calma(0.05)
            gc.collect()
            calma(0.2)
            print(f"  {'tras la vuelta ' + str(vuelta + 1):<44} {proc.memory_info().rss / 2**20:8.0f} MB")


if __name__ == "__main__":
    main()
