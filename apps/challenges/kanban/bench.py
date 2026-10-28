"""Mediciones del reto Kanban: un tablero de N columnas × M tarjetas (por defecto 20 × 200).

    python bench.py                 # 20 × 200, sin ventana
    python bench.py --cols 4 --cards 200

Mide, en el hilo de la interfaz (procesando eventos hasta que no queda nada):

- montar el tablero (compilar, crear y primer fotograma);
- cada movimiento del puntero mientras se arrastra una tarjeta entre columnas
  (encontrar la zona bajo el puntero, mover la copia, :drag-over, on:dragover);
- soltar en otra columna (mover la fila entre dos <List>) y dentro de la misma;
- deshacer, filtrar (escribir en la búsqueda) y la memoria del proceso.

Usa janelkit.inspect con la plataforma offscreen: los tiempos incluyen el trabajo de
Python y de Qt Quick (polish, disposición) y no el dibujado en pantalla.
"""
from __future__ import annotations

import argparse
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
        print(f"  {label:<42} {values[0]:8.1f} ms")
    else:
        print(f"  {label:<42} p50 {statistics.median(values):6.2f}  p99 {pct(values, 0.99):6.2f}  máx {max(values):6.2f} ms  (n={len(values)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cols", type=int, default=20)
    ap.add_argument("--cards", type=int, default=200)
    ap.add_argument("--repeat", type=int, default=10)
    args = ap.parse_args()
    os.environ["KANBAN_DEMO"] = f"{args.cols}x{args.cards}"

    import psutil
    from PySide6.QtCore import QCoreApplication, QPoint, Qt
    from PySide6.QtTest import QTest

    from janelkit.inspect import mount

    proc = psutil.Process()
    rss0 = proc.memory_info().rss
    t0 = time.perf_counter()
    with mount(HERE / "src" / "App.janel") as app:
        app.window.resize(1600, 900)
        QCoreApplication.processEvents()
        montar = (time.perf_counter() - t0) * 1000
        tab = app.get("tablero")
        cols = tab.columnas.peek()
        print(f"Tablero de {len(cols)} columnas × {args.cards} tarjetas ({sum(len(c['tarjetas']) for c in cols)} en total)")
        line("montar (compilar, crear, primer fotograma)", [montar])
        print(f"  {'tarjetas creadas (las visibles)':<42} {len(app.find_all('Tarjeta')):8d}")
        print(f"  {'memoria del proceso':<42} {(proc.memory_info().rss - rss0) / 2**20:8.0f} MB más")

        win = app.window
        marks: dict[str, float] = {}
        win.beforeSynchronizing.connect(lambda: marks.setdefault("sync", time.perf_counter()), Qt.ConnectionType.DirectConnection)
        win.frameSwapped.connect(lambda: marks.setdefault("swap", time.perf_counter()), Qt.ConnectionType.DirectConnection)

        def frame(action, into: list, render: list | None = None) -> None:
            """Hace `action` y espera a su fotograma: guarda el trabajo del hilo de la
            interfaz hasta sincronizar (eventos, Python, polish) y, aparte, con el dibujado."""
            marks.clear()
            t = time.perf_counter()
            action()
            while "swap" not in marks and time.perf_counter() - t < 0.5:
                QCoreApplication.processEvents()
            into.append((marks.get("sync", time.perf_counter()) - t) * 1000)
            if render is not None:
                render.append((marks.get("swap", time.perf_counter()) - t) * 1000)

        def card(titulo: str):
            return next(c for c in app.find_all("Tarjeta") if c.label == titulo)

        L, NONE = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        moves, moves_r, between, within, undos = [], [], [], [], []
        for _ in range(args.repeat):
            # Entre columnas: la primera tarjeta de la columna 0 recorre las columnas 1 y 2 y cae en la 3.
            src = card(cols[0]["tarjetas"][0]["titulo"])
            start, end = src._center(), app.find("Columna", label=cols[3]["nombre"])._center()
            QTest.mousePress(win, L, NONE, start)
            QCoreApplication.processEvents()
            for i in range(1, 41):
                to = start + QPoint((end.x() - start.x()) * i // 40, (end.y() - start.y()) * i // 40 + (i % 7) * 9)
                frame(lambda: QTest.mouseMove(win, to), moves, moves_r)
            frame(lambda: QTest.mouseRelease(win, L, NONE, end), between)
            app.wait(0.3)
            # Dentro de una columna: la segunda tarjeta de la columna 1 sobre la primera.
            a, b = card(cols[1]["tarjetas"][1]["titulo"]), card(cols[1]["tarjetas"][0]["titulo"])
            QTest.mousePress(win, L, NONE, a._center())
            for i in range(1, 6):
                QTest.mouseMove(win, a._center() + QPoint(0, (b._center().y() - a._center().y()) * i // 5))
                QCoreApplication.processEvents()
            frame(lambda: QTest.mouseRelease(win, L, NONE, b._center()), within)
            app.wait(0.3)
            frame(tab.deshacer, undos)
            app.wait(0.3)

        base, base_r = [], []
        for _ in range(40):
            frame(win.update, base, base_r)
        print("Referencia: un fotograma sin cambios")
        line("hasta sincronizar", base)
        line("  … con el dibujado por software", base_r)
        print("Arrastrar (hilo de la interfaz, hasta sincronizar el fotograma)")
        line("cada movimiento del puntero", moves)
        line("  … con el dibujado por software", moves_r)
        line("soltar en otra columna", between)
        line("soltar dentro de la columna", within)
        line("deshacer un movimiento", undos)

        print("Filtrar")
        texto = app.namespace["texto"]
        escribir = []
        for valor in ("r", "re", "rev", "revi", "", "do", "doc", ""):
            frame(lambda: texto.set(valor), escribir)
            app.wait(0.2)
        line("cada cambio en la búsqueda", escribir)


if __name__ == "__main__":
    main()
