"""Carga del reto del chat: N mensajes por segundo durante un rato, midiendo memoria y respuesta.

    python bench.py                       # 20 mensajes/s durante 300 s, con ventana visible
    python bench.py --rate 50 --seconds 60 --headless

El servidor corre en otro proceso (no comparte CPU ni GIL con la interfaz).
Cada 10 s imprime: mensajes recibidos, mensajes guardados por sala, memoria del
proceso, CPU del proceso y el retraso del bucle de eventos (cuánto tarda en
atenderse una tarea que debería ejecutarse cada 50 ms).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rss_mb() -> float:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t)
                for n in ("Peak", "WorkingSet", "QPPeak", "QP", "QNPPeak", "QNP", "Pagefile", "PeakPagefile")
            ]

        c = Counters()
        c.cb = ctypes.sizeof(c)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSet / 2**20
    with open("/proc/self/statm") as f:  # Linux
        return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=20)
    parser.add_argument("--seconds", type=float, default=300)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    port = free_port()
    server = subprocess.Popen([sys.executable, str(HERE / "server.py"), "--port", str(port), "--rate", str(args.rate)])
    os.environ["CHAT_URL"] = f"ws://127.0.0.1:{port}"
    time.sleep(1)

    from janelkit import notifications
    from janelkit.inspect import mount

    notifications._tray_icon = lambda: None  # sin avisos reales del sistema durante la medición

    lags: list[float] = []

    async def probe() -> None:
        while True:
            t = time.perf_counter()
            await asyncio.sleep(0.05)
            lags.append((time.perf_counter() - t - 0.05) * 1000)

    try:
        with mount(HERE / "src" / "App.janel", headless=args.headless) as app:
            client = app.get("client")
            app.wait(until=lambda: client.status.value == "online" and len(client.room_list.value) == 4)
            probe_task = asyncio.ensure_future(probe())
            rooms = ["general", "python", "random", "arabic"]
            start, cpu0 = time.perf_counter(), time.process_time()
            last_t, last_cpu, last_n = start, cpu0, client.received
            print(f"{'s':>5} {'recibidos':>9} {'msg/s':>6} {'guardados':>18} {'MB':>7} {'CPU%':>5} {'lag p50':>8} {'p99':>6} {'máx':>6}")
            mem = []
            tick = 0
            while time.perf_counter() - start < args.seconds:
                app.wait(10)
                tick += 1
                if tick % 3 == 0:  # el usuario cambia de sala de vez en cuando
                    app.find("Row", label=client.rooms[rooms[tick // 3 % 4]].name).click()
                now, cpu = time.perf_counter(), time.process_time()
                kept = "/".join(str(len(client.rooms[r].messages.value)) for r in rooms)
                window = sorted(lags)
                lags.clear()
                mem.append(rss_mb())
                print(
                    f"{now - start:5.0f} {client.received:9d} {(client.received - last_n) / (now - last_t):6.1f} {kept:>18} "
                    f"{mem[-1]:7.1f} {100 * (cpu - last_cpu) / (now - last_t):5.0f} "
                    f"{statistics.median(window):8.1f} {window[int(len(window) * 0.99) - 1]:6.1f} {window[-1]:6.1f}",
                    flush=True,
                )
                last_t, last_cpu, last_n = now, cpu, client.received
            probe_task.cancel()
            half = len(mem) // 2
            print(f"memoria: primera mitad {statistics.mean(mem[:half]):.1f} MB, segunda mitad {statistics.mean(mem[half:]):.1f} MB")
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
