"""Mediciones de <Video> y Frames (docs/vision.md).

    python bench.py              # 640×480, 1280×720 y 1920×1080 a 60 fps, sin ventana
    python bench.py --ventana    # con la ventana a la vista (incluye subir la imagen a la GPU)

Para cada resolución, un hilo empuja fotogramas a 60 fps durante unos segundos y se mide:
fotogramas entregados por segundo, lo que cuesta `push` en el hilo que lo llama, la
latencia de `push` a la entrega en el hilo de la interfaz, y la CPU del hilo de la
interfaz (porcentaje de un núcleo).
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ventana", action="store_true")
    ap.add_argument("--segundos", type=float, default=3.0)
    ap.add_argument("--fps", type=float, default=60.0)
    args = ap.parse_args()
    if not args.ventana:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(HERE / "src"))

    import numpy as np
    import psutil

    from janelkit.inspect import mount

    principal = threading.main_thread().native_id
    proceso = psutil.Process()

    def cpu_principal() -> float:
        return next(t.user_time + t.system_time for t in proceso.threads() if t.id == principal)

    print(f"{'resolución':>11}  {'entregados':>10}  {'push':>8}  {'latencia p50/p95':>17}  {'CPU interfaz':>12}")
    for ancho, alto in ((640, 480), (1280, 720), (1920, 1080)):
        with mount(HERE / "src" / "App.janel") as app:
            if args.ventana:
                app.window.show()
            app.window.resize(960, 640)
            frames = app.namespace["frames"]
            app.namespace["parar"].set()  # sin la escena del ejemplo ni su modelo
            app.wait(0.2)
            app.namespace["objetos"].value = []

            empujado: dict[int, float] = {}
            latencias: list[float] = []
            original = frames._deliver

            def entregar() -> None:
                with frames._lock:
                    pendiente = frames._pending
                original()
                if pendiente is not None:
                    t = empujado.pop(id(pendiente[0]), None)
                    if t is not None:
                        latencias.append((time.perf_counter() - t) * 1000)

            frames._deliver = entregar
            base = np.random.default_rng(1).integers(0, 255, (alto, ancho, 3), dtype=np.uint8)
            imagenes = [np.roll(base, i * 8, axis=1) for i in range(8)]
            costes: list[float] = []
            parar = threading.Event()

            def empujar() -> None:
                siguiente = time.perf_counter()
                i = 0
                while not parar.is_set():
                    img = imagenes[i % len(imagenes)].copy()
                    t = time.perf_counter()
                    empujado[id(img)] = t
                    frames.push(img)
                    costes.append((time.perf_counter() - t) * 1000)
                    i += 1
                    siguiente += 1 / args.fps
                    parar.wait(max(0.0, siguiente - time.perf_counter()))

            hilo = threading.Thread(target=empujar)
            app.wait(0.3)
            cpu0, t0, n0 = cpu_principal(), time.perf_counter(), frames._seq
            hilo.start()
            app.wait(args.segundos)
            parar.set()
            hilo.join()
            dt = time.perf_counter() - t0
            cpu = (cpu_principal() - cpu0) / dt * 100
            fps = (frames._seq - n0) / dt
            lat = sorted(latencias)
            p95 = lat[int(len(lat) * 0.95)] if lat else float("nan")
            print(f"{ancho:>5}×{alto:<5}  {fps:>7.1f} fps  {statistics.median(costes):>5.2f} ms"
                  f"  {statistics.median(lat):>7.2f} / {p95:>5.2f} ms  {cpu:>10.1f} %")


if __name__ == "__main__":
    main()
