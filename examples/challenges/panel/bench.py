"""Carga del reto del panel: N métricas M veces por segundo durante un rato.

    python bench.py                                # 50 métricas, 10/s, 600 s, ventana visible
    python bench.py --metrics 50 --rate 10 --seconds 60 --headless

Usa la fuente simulada (valores deterministas, 300 procesos) con dos gráficas
abiertas en ventanas aparte. Cada 10 s imprime: muestras por segundo, CPU del
hilo de la interfaz y del proceso, memoria, la latencia desde cada muestra hasta
el fotograma que la muestra en pantalla (p50, p99, máximo) y el retraso del
bucle de eventos. De vez en cuando reordena y filtra la tabla, como haría un usuario.

Qt solo dibuja cuando algo cambia, así que los fotogramas por segundo no dicen
nada; lo que se nota es cuánto tarda un cambio en verse.

Al final, redimensiona la ventana sin parar durante 10 s y mide el coste de cada
fotograma con la instrumentación de Qt (QSG_RENDER_TIMING: polish en el hilo de
la interfaz; sync, render y swap en el de render). Así se separa lo que cuesta
dibujar el panel de lo que tarda el sistema en cambiar el tamaño de la ventana.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import statistics
import threading
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=int, default=50)
    parser.add_argument("--rate", type=float, default=10, help="muestras por segundo")
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--resize", type=float, default=10, help="segundos redimensionando al final")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    os.environ.update({
        "PANEL_SOURCE": "sim",
        "PANEL_METRICS": str(args.metrics),
        "PANEL_RATE_MS": str(int(1000 / args.rate)),
        "PANEL_HISTORY": str(int(60 * args.rate)),  # 60 s de historia
    })

    # Tiempos por fotograma de Qt Quick (se leen del registro de Qt).
    os.environ["QT_LOGGING_RULES"] = "qt.scenegraph.time.renderloop=true"
    from PySide6.QtCore import qInstallMessageHandler

    rendered: list[tuple[int, ...]] = []  # (total, sync, render, swap) en ms
    polished: list[int] = []
    previous = None

    def on_qt_message(kind, context, message) -> None:
        m = re.search(r"frame rendered in (\d+)ms, sync=(\d+), render=(\d+), swap=(\d+)", message)
        if m:
            rendered.append(tuple(map(int, m.groups())))
            return
        m = re.search(r"Frame prepared, polish=(\d+) ms", message)
        if m:
            polished.append(int(m.group(1)))
            return
        if "qt.scenegraph" not in (context.category or "") and previous is not None:
            previous(kind, context, message)

    previous = qInstallMessageHandler(on_qt_message)

    from fluxui import notifications
    from fluxui.inspect import mount

    notifications._tray_icon = lambda: None  # sin avisos reales del sistema durante la medición

    proc = psutil.Process()
    main_id = threading.main_thread().native_id

    def ui_thread_cpu() -> float:
        for t in proc.threads():
            if t.id == main_id:
                return t.user_time + t.system_time
        return 0.0

    lags: list[float] = []
    frames: list[float] = []  # latencias cambio -> fotograma presentado, en ms
    changed: list[float] = []  # instante del cambio que aún no se ha visto en pantalla

    async def probe() -> None:
        while True:
            t = time.perf_counter()
            await asyncio.sleep(0.05)
            lags.append((time.perf_counter() - t - 0.05) * 1000)

    with mount(HERE / "src" / "App.flux", headless=args.headless) as app:
        monitor = app.get("monitor")
        app.wait(until=lambda: len(monitor.processes.value) > 0)
        series = len(monitor.series)
        for label in ("CPU", "Red ↓"):
            app.find("Button", label=f"Abrir {label}").click()
        windows = [app.window] + [w.window for w in app.windows()]

        def on_frame() -> None:
            if changed:
                frames.append((time.perf_counter() - changed.pop()) * 1000)
                changed.clear()

        app.window.frameSwapped.connect(on_frame)
        sample = monitor.sample

        def timed_sample() -> None:
            sample()
            if not changed:
                changed.append(time.perf_counter())

        monitor.sample = timed_sample
        probe_task = asyncio.ensure_future(probe())
        print(f"{series} métricas a {args.rate:g}/s, {len(monitor.processes.value)} procesos, {len(windows)} ventanas")
        print(f"{'s':>5} {'muestras/s':>10} {'CPU UI%':>7} {'CPU%':>5} {'MB':>7} {'vistas':>6} {'latencia p50':>12} {'p99':>6} {'máx':>6} {'lag p99':>8} {'máx':>6}")

        start = time.perf_counter()
        last_t, last_ui, last_cpu, last_n = start, ui_thread_cpu(), time.process_time(), monitor.samples
        mem: list[float] = []
        ui_load: list[float] = []
        tick = 0
        sorts = ["Memoria", "PID", "Proceso", "CPU"]
        while time.perf_counter() - start < args.seconds:
            frames.clear()
            app.wait(10)
            tick += 1
            if tick % 3 == 0:  # el usuario reordena y filtra de vez en cuando
                app.find("Button", text=sorts[tick // 3 % len(sorts)]).click()
                app.find("TextField", id="query").type("" if tick % 2 else "svc")
            now, ui, cpu = time.perf_counter(), ui_thread_cpu(), time.process_time()
            dt = now - last_t
            mem.append(proc.memory_info().rss / 2**20)
            ui_load.append(100 * (ui - last_ui) / dt)
            window = sorted(lags)
            lags.clear()
            print(
                f"{now - start:5.0f} {(monitor.samples - last_n) / dt:10.1f} {ui_load[-1]:7.0f} {100 * (cpu - last_cpu) / dt:5.0f} "
                f"{mem[-1]:7.1f} {len(frames):6d} {pct(frames, 0.5):12.1f} {pct(frames, 0.99):6.1f} {max(frames, default=0):6.1f} "
                f"{pct(window, 0.99):8.1f} {max(window, default=0):6.1f}",
                flush=True,
            )
            last_t, last_ui, last_cpu, last_n = now, ui, cpu, monitor.samples

        if rendered:
            print(
                f"coste por fotograma (todas las ventanas, {len(rendered)} fotogramas): render+sync+swap p99 "
                f"{pct([r[0] for r in rendered], 0.99)} ms, máx {max(r[0] for r in rendered)} ms; "
                f"polish (disposición) p99 {pct(polished, 0.99)} ms, máx {max(polished, default=0)} ms"
            )
        if args.resize > 0 and not args.headless:
            win = app.window
            w0, h0 = win.width(), win.height()
            frames.clear()
            rendered.clear()
            polished.clear()
            t0, ui0 = time.perf_counter(), ui_thread_cpu()
            step = 0
            while time.perf_counter() - t0 < args.resize:
                step += 1
                k = (step % 40) / 40
                win.resize(int(w0 - 300 * k), int(h0 - 200 * k))
                if not changed:
                    changed.append(time.perf_counter())
                app.wait(0.016)
            win.resize(w0, h0)
            dt = time.perf_counter() - t0
            costs = [r[0] for r in rendered]
            janky = sum(f > 50 for f in frames)
            print(
                f"redimensionando {dt:.0f} s: {step} cambios de tamaño, {len(frames)} vistos; latencia p50 {pct(frames, 0.5):.1f} ms, "
                f"p99 {pct(frames, 0.99):.1f} ms, máx {max(frames, default=0):.1f} ms, {janky} por encima de 50 ms, "
                f"CPU UI {100 * (ui_thread_cpu() - ui0) / dt:.0f} %"
            )
            print(
                f"  coste por fotograma redimensionando ({len(costs)} fotogramas): render+sync+swap p99 {pct(costs, 0.99)} ms, "
                f"máx {max(costs, default=0)} ms; polish p99 {pct(polished, 0.99)} ms, máx {max(polished, default=0)} ms "
                "(el resto de la latencia es el sistema cambiando el tamaño de la ventana)"
            )
        probe_task.cancel()
        half = len(mem) // 2
        if half:
            print(
                f"memoria: primera mitad {statistics.mean(mem[:half]):.1f} MB, segunda mitad {statistics.mean(mem[half:]):.1f} MB; "
                f"CPU del hilo de la interfaz: media {statistics.mean(ui_load):.0f} %, máx {max(ui_load):.0f} %"
            )


if __name__ == "__main__":
    main()
