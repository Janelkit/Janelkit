"""Mediciones del motor de <flex> (docs/flex.md, criterios de rendimiento).

    python bench.py               # rejilla de 200 tarjetas
    python bench.py --cards 500

Mide el tiempo de montar la vista y, al cambiar el ancho de la ventana, la fase de
polish de cada fotograma (instrumentación de Qt), que es donde se calcula la
disposición de <flex>: recolocar y volver a cortar los textos. El resto del tiempo
de un cambio de tamaño es el sistema redimensionando la ventana.
"""
import argparse
import os
import re
import statistics
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=int, default=200)
    parser.add_argument("--steps", type=int, default=200)
    args = parser.parse_args()
    os.environ["FLEX_CARDS"] = str(args.cards)
    os.environ["QT_LOGGING_RULES"] = "qt.scenegraph.time.renderloop=true"

    from PySide6.QtCore import QCoreApplication, qInstallMessageHandler

    polished: list[int] = []

    def on_qt_message(kind, context, message) -> None:
        m = re.search(r"Frame prepared, polish=(\d+) ms", message)
        if m:
            polished.append(int(m.group(1)))

    qInstallMessageHandler(on_qt_message)

    from janelkit.inspect import mount

    t = time.perf_counter()
    with mount(Path(__file__).parent / "src" / "App.janel", headless=False) as app:
        app.wait(0.2)
        print(f"{args.cards} tarjetas: montar {(time.perf_counter() - t) * 1000:.0f} ms (con 0,2 s de espera)")
        win = app.window
        polished.clear()
        steps = []
        for i in range(args.steps):
            start = time.perf_counter()
            win.setWidth(500 + (i * 37) % 900)
            QCoreApplication.processEvents()
            steps.append((time.perf_counter() - start) * 1000)
        steps.sort()
        p99 = steps[max(0, int(len(steps) * 0.99) - 1)]
        print(f"cambiar el ancho (total, con el sistema): mediana {statistics.median(steps):.1f} ms, p99 {p99:.1f} ms")
        # Solo los fotogramas en que hubo que recolocar (los demás dan 0 ms).
        work = sorted(p for p in polished if p > 0)
        if work:
            pp = work[max(0, int(len(work) * 0.99) - 1)]
            print(f"polish de los fotogramas que recolocan ({len(work)}): mediana {statistics.median(work):.0f} ms, "
                  f"p99 {pp} ms, máx {work[-1]} ms")


if __name__ == "__main__":
    main()
