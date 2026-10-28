"""Mediciones del reto Hoja de cálculo (los criterios de «Hecho cuando»).

    python bench.py                  # CSV de 10 000 × 26, ventana de 1280 × 800, sin mostrarla
    python bench.py --filas 2000

Mide, en el hilo de la interfaz (procesando eventos hasta que no queda nada):

- abrir un CSV de 10 000 × 26 (leerlo y mostrar la hoja) y montar la aplicación;
- moverse: flecha (sin filas nuevas), AvPág (filas nuevas), la rueda, columna a la derecha
  (columna nueva en cada fila visible) y el salto al final de los datos;
- editar una celda de la que dependen 1 000 fórmulas (algunas a la vista, todas
  sumadas en un total a la vista, o ninguna a la vista);
- seleccionar un rango grande, deshacer, ordenar y la memoria del proceso.

Usa janelkit.inspect con la plataforma offscreen: los tiempos incluyen Python y Qt
Quick (polish, disposición), no el dibujado en pantalla.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pct(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def line(label: str, values: list[float]) -> None:
    if len(values) == 1:
        print(f"  {label:<46} {values[0]:8.1f} ms")
    else:
        print(f"  {label:<46} p50 {statistics.median(values):7.2f}  máx {max(values):7.2f} ms  (n={len(values)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filas", type=int, default=10_000)
    ap.add_argument("--repeat", type=int, default=10)
    args = ap.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(HERE / "src"))

    import psutil
    from PySide6.QtCore import QCoreApplication, QObject

    from janelkit.inspect import mount
    from services.hoja import COLUMNAS, ejemplo

    carpeta = Path(tempfile.mkdtemp())
    archivo = carpeta / "datos.csv"
    datos = ejemplo(args.filas, COLUMNAS)
    with archivo.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for r in range(args.filas):
            w.writerow([datos.get((r, c), "") for c in range(COLUMNAS)])
    os.environ["HOJA_FILE"] = str(archivo)
    os.environ.pop("HOJA_DEMO", None)

    proc = psutil.Process()
    rss0 = proc.memory_info().rss

    def medir(fn, n: int = 1) -> list[float]:
        out = []
        for _ in range(n):
            t = time.perf_counter()
            fn()
            QCoreApplication.processEvents()
            out.append((time.perf_counter() - t) * 1000)
        return out

    t0 = time.perf_counter()
    with mount(HERE / "src" / "App.janel") as app:
        app.window.resize(1280, 800)
        QCoreApplication.processEvents()
        montar = (time.perf_counter() - t0) * 1000
        hoja, vista = app.get("hoja"), app.get("vista")
        rejilla = app.find(label="Hoja")
        print(f"Hoja de {args.filas} × {COLUMNAS}; {vista.caben.value} columnas y "
              f"{len(app.find_all('Fila'))} filas a la vista\n")
        line("abrir el CSV y montar (primer fotograma)", [montar])
        t = time.perf_counter()
        hoja.abrir(archivo)
        QCoreApplication.processEvents()
        line("volver a abrir el CSV con la hoja a la vista", [(time.perf_counter() - t) * 1000])

        print("\nMoverse")
        line("flecha abajo (sin filas nuevas)", medir(lambda: rejilla.key("Down"), args.repeat))
        line("AvPág (una página de filas nuevas)", medir(lambda: rejilla.key("PgDown"), args.repeat))
        lista = next(i for i in app.get("lista").value.findChildren(QObject) if i.inherits("QQuickListView"))

        def rueda() -> None:  # un paso de rueda: 3 filas
            lista.setProperty("contentY", lista.property("contentY") + 3 * 25)

        line("rueda, 3 filas por paso (60 pasos)", medir(rueda, 60))
        line("columna a la derecha (una celda nueva por fila)", medir(lambda: vista.desplazar_cols(1), args.repeat))
        line("columna a la izquierda", medir(lambda: vista.desplazar_cols(-1), args.repeat))
        line("Ctrl+Fin (al final de los datos)", medir(lambda: rejilla.key("Ctrl+End")))
        line("Ctrl+Inicio", medir(lambda: rejilla.key("Ctrl+Home")))

        print("\nEditar una celda de la que dependen 1 000 fórmulas")
        cambios = {(r, 1): f"=A1*{r}" for r in range(1, 1001)}
        hoja.escribir(cambios, "dependientes")
        QCoreApplication.processEvents()
        valores = iter(range(100, 10_000))
        line("  con ~30 de ellas a la vista", medir(lambda: hoja.escribir({(0, 0): str(next(valores))}, "x"), args.repeat))
        hoja.escribir({(0, 2): "=SUMA(B2:B1001)"}, "total")  # a la vista: necesita las 1 000
        QCoreApplication.processEvents()
        line("  y un total a la vista que las suma todas", medir(lambda: hoja.escribir({(0, 0): str(next(valores))}, "x"), args.repeat))
        rejilla.key("Ctrl+End")
        QCoreApplication.processEvents()
        line("  con ninguna a la vista", medir(lambda: hoja.escribir({(0, 0): str(next(valores))}, "x"), args.repeat))
        rejilla.key("Ctrl+Home")

        print("\nOtras acciones")
        line("seleccionar 30 × 10 (Mayús+clic)", medir(lambda: vista.ir(29, 9, extender=True)))
        line("seleccionar toda la hoja (Ctrl+A, con resumen)", medir(lambda: rejilla.key("Ctrl+A")))
        line("deshacer", medir(hoja.deshacer))
        line("ordenar 10 000 filas por la columna B", medir(lambda: hoja.ordenar(1, desde=1)))
        line("deshacer la ordenación", medir(hoja.deshacer))
        print(f"\nMemoria del proceso: {(proc.memory_info().rss - rss0) / 2**20:.0f} MB más que al empezar "
              f"({len(hoja._celdas)} celdas reactivas creadas)")


if __name__ == "__main__":
    main()
