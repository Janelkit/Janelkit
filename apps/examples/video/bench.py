"""Mediciones de <video> y Frames (docs/arquitectura.md, «Rendimiento»).

    python bench.py                                   # sin ventana (offscreen), a 60 fps
    python bench.py --ventana                         # con una ventana real
    python bench.py --ventana --fps 47 --rondas 5     # las cifras de docs/arquitectura.md

Para cada resolución (640×480, 1280×720 y 1920×1080), un hilo empuja fotogramas durante unos
segundos y se mide:
- los fotogramas entregados por segundo;
- lo que cuesta `push` en el hilo que lo llama;
- la latencia de `push` a la entrega en el hilo de la interfaz;
- con --ventana, la latencia de `push` a la pantalla;
- la CPU del hilo de la interfaz (porcentaje de un núcleo).

Con --rondas N se repite cada medición N veces y se da la mediana de cada cifra.

- Sin ventana (plataforma offscreen) Qt Quick dibuja por software en el hilo de la interfaz: la
  CPU sale mucho más alta que con una ventana real, y no hay latencia hasta la pantalla.
- Hasta la pantalla: de `push` al frameSwapped del fotograma en el que esa imagen se sincronizó
  con el hilo de render. Solo cuenta la imagen que se dibujó (la última entregada antes de
  sincronizar). No incluye el barrido del monitor ni el compositor del sistema.
- A 60 fps, el hilo y el refresco del monitor (60 Hz) van casi en fase: la espera hasta el
  refresco queda casi fija en una ejecución y cambia de una a otra. Con --fps 47, cada ronda
  recorre todas las fases.
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


def percentil(valores: list[float], q: float) -> float:
    s = sorted(valores)
    return s[min(len(s) - 1, int(len(s) * q))] if s else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ventana", action="store_true", help="con una ventana real (si no, offscreen)")
    ap.add_argument("--segundos", type=float, default=3.0)
    ap.add_argument("--fps", type=float, default=60.0)
    ap.add_argument("--rondas", type=int, default=1)
    args = ap.parse_args()
    if not args.ventana:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(HERE / "src"))

    import numpy as np
    import psutil
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    from janelkit.inspect import mount

    principal = threading.main_thread().native_id
    proceso = psutil.Process()

    def cpu_principal() -> float:
        return next(t.user_time + t.system_time for t in proceso.threads() if t.id == principal)

    cabecera = True
    for ancho, alto in ((640, 480), (1280, 720), (1920, 1080)):
        # headless=False: sin él, mount() usa la plataforma offscreen aunque se muestre la ventana.
        with mount(HERE / "src" / "App.janel", headless=not args.ventana) as app:
            if args.ventana:
                app.window.show()
            app.window.resize(960, 640)
            frames = app.namespace["frames"]
            app.namespace["parar"].set()  # sin la escena del ejemplo ni su modelo
            app.wait(0.2)
            app.namespace["objetos"].value = []
            if cabecera:
                api = app.window.rendererInterface().graphicsApi().name  # offscreen: Software
                print(f"plataforma {QGuiApplication.platformName()} ({api}), {args.fps:g} fps, "
                      f"{args.rondas} ronda(s) de {args.segundos:g} s")
                print(f"{'resolución':>11}  {'entregados':>10}  {'push':>8}  {'entrega p50/p95':>16}"
                      f"  {'pantalla p50/p95':>17}  {'CPU interfaz':>12}")
                cabecera = False

            # Hasta la pantalla (solo con ventana): en el hilo de render, con el de la interfaz parado
            # mientras se sincroniza.
            cerrojo = threading.Lock()
            entregados: list[float] = []  # instantes de push de lo entregado aún sin sincronizar
            sincronizado: list[float] = []
            pantalla: list[float] = []

            def tras_sincronizar() -> None:
                with cerrojo:
                    if entregados:
                        sincronizado.append(max(entregados))  # solo la última se dibuja
                        entregados.clear()

            def intercambiado() -> None:
                ahora = time.perf_counter()
                with cerrojo:
                    pantalla.extend((ahora - t) * 1000 for t in sincronizado)
                    sincronizado.clear()

            if args.ventana:
                app.window.afterSynchronizing.connect(tras_sincronizar, Qt.ConnectionType.DirectConnection)
                app.window.frameSwapped.connect(intercambiado, Qt.ConnectionType.DirectConnection)

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
                        with cerrojo:
                            entregados.append(t)

            frames._deliver = entregar
            base = np.random.default_rng(1).integers(0, 255, (alto, ancho, 3), dtype=np.uint8)
            imagenes = [np.roll(base, i * 8, axis=1) for i in range(8)]

            rondas: list[dict[str, float]] = []
            for _ in range(args.rondas):
                costes: list[float] = []
                parar = threading.Event()

                def empujar(costes=costes, parar=parar) -> None:
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
                latencias.clear()
                with cerrojo:
                    entregados.clear()
                    sincronizado.clear()
                    pantalla.clear()
                cpu0, t0, n0 = cpu_principal(), time.perf_counter(), frames._seq
                hilo.start()
                app.wait(args.segundos)
                parar.set()
                hilo.join()
                dt = time.perf_counter() - t0
                with cerrojo:
                    vistos = list(pantalla)
                rondas.append({
                    "fps": (frames._seq - n0) / dt,
                    "push": statistics.median(costes),
                    "entrega50": statistics.median(latencias),
                    "entrega95": percentil(latencias, 0.95),
                    "pantalla50": statistics.median(vistos) if vistos else float("nan"),
                    "pantalla95": percentil(vistos, 0.95),
                    "cpu": (cpu_principal() - cpu0) / dt * 100,
                })
            m = {k: statistics.median(r[k] for r in rondas) for k in rondas[0]}
            hasta = f"{m['pantalla50']:>7.2f} / {m['pantalla95']:>5.2f} ms" if args.ventana else f"{'—':>17}"
            print(f"{ancho:>5}×{alto:<5}  {m['fps']:>7.1f} fps  {m['push']:>5.2f} ms"
                  f"  {m['entrega50']:>6.2f} / {m['entrega95']:>5.2f} ms  {hasta}  {m['cpu']:>10.1f} %")


if __name__ == "__main__":
    main()
