"""Métricas del sistema: series con historia y la lista de procesos.

Dos fuentes con la misma forma:

- `SystemSource` lee el ordenador con `psutil` (CPU por núcleo, memoria, red, disco).
- `SimulatedSource` genera valores deterministas: para pruebas y mediciones, con
  tantas métricas como se pida.

`Monitor.sample()` lee la fuente y actualiza todas las series en un solo `batch`
(un único recálculo de la interfaz por muestra). La lista de procesos se lee en
otro hilo (`background`), porque recorrer ~300 procesos tarda decenas de ms.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any

from janelkit import batch, state


class Series:
    """Una métrica: valor actual, historia de los últimos `capacity` valores y umbral de aviso."""

    def __init__(self, id: str, label: str, unit: str = "%", max: float = 100.0, warn: float | None = None, capacity: int = 240):
        self.id = id
        self.label = label
        self.unit = unit
        self.max = max  # 0: escala automática
        self.warn = warn  # por encima: la tarjeta cambia de color y hay aviso
        self.capacity = capacity
        self.value = state(0.0)
        self.history = state([])  # crece hasta `capacity`; la gráfica la alinea a la derecha
        self.alert = state(False)

    def push(self, value: float) -> None:
        self.value.value = value
        h = self.history.peek()
        if len(h) >= self.capacity:
            del h[0]  # dentro del batch de sample(): una sola notificación para los dos cambios
        h.append(value)
        if self.warn is not None:
            self.alert.value = value >= self.warn

    def text(self, value: float | None = None) -> str:
        v = self.value.value if value is None else value
        return format_value(v, self.unit)

    def __repr__(self) -> str:
        return f"Series({self.id}={self.value.peek():.1f}{self.unit})"


def format_value(v: float, unit: str) -> str:
    if unit == "B/s":
        for suffix, size in (("GB/s", 1 << 30), ("MB/s", 1 << 20), ("KB/s", 1 << 10)):
            if v >= size:
                return f"{v / size:.1f} {suffix}"
        return f"{v:.0f} B/s"
    if unit == "GB":
        return f"{v:.1f} GB"
    return f"{v:.0f} %"


# -- fuentes ------------------------------------------------------------------
class SystemSource:
    """El ordenador real, con psutil."""

    def __init__(self) -> None:
        import psutil

        self.psutil = psutil
        self.cores = psutil.cpu_count() or 1
        self.total_memory = psutil.virtual_memory().total / (1 << 30)
        self._net = psutil.net_io_counters()
        self._disk = psutil.disk_io_counters()
        self._at = time.monotonic()
        self._procs: dict[int, Any] = {}
        psutil.cpu_percent(percpu=True)  # la primera lectura siempre es 0

    def describe(self) -> list[dict]:
        out = [
            {"id": "cpu", "label": "CPU", "warn": 90},
            {"id": "mem", "label": "Memoria", "warn": 90},
            {"id": "net_down", "label": "Red ↓", "unit": "B/s", "max": 0},
            {"id": "net_up", "label": "Red ↑", "unit": "B/s", "max": 0},
            {"id": "disk_read", "label": "Disco (lectura)", "unit": "B/s", "max": 0},
            {"id": "disk_write", "label": "Disco (escritura)", "unit": "B/s", "max": 0},
        ]
        out += [{"id": f"core{i}", "label": f"Núcleo {i}", "core": True} for i in range(self.cores)]
        return out

    def read(self) -> dict[str, float]:
        ps = self.psutil
        now = time.monotonic()
        dt = max(now - self._at, 1e-3)
        self._at = now
        cores = ps.cpu_percent(percpu=True)
        net, disk = ps.net_io_counters(), ps.disk_io_counters()
        values = {
            "cpu": sum(cores) / len(cores),
            "mem": ps.virtual_memory().percent,
            "net_down": (net.bytes_recv - self._net.bytes_recv) / dt,
            "net_up": (net.bytes_sent - self._net.bytes_sent) / dt,
            "disk_read": (disk.read_bytes - self._disk.read_bytes) / dt if disk else 0.0,
            "disk_write": (disk.write_bytes - self._disk.write_bytes) / dt if disk else 0.0,
        }
        self._net, self._disk = net, disk
        values.update({f"core{i}": v for i, v in enumerate(cores)})
        return values

    def processes(self) -> list[dict]:
        """Lista de procesos (se ejecuta en otro hilo: no toca estado)."""
        ps = self.psutil
        seen: dict[int, Any] = {}
        out = []
        for p in ps.process_iter(["name", "memory_info", "num_threads", "username"]):
            if p.pid == 0:  # "System Idle Process": no es un proceso de verdad
                continue
            proc = self._procs.get(p.pid, p)
            seen[p.pid] = proc
            try:
                cpu = proc.cpu_percent(None) / self.cores  # como el administrador de tareas: % del total
            except (ps.NoSuchProcess, ps.AccessDenied):
                cpu = 0.0
            info = p.info
            mem = info["memory_info"].rss if info.get("memory_info") else 0
            out.append({
                "pid": p.pid,
                "name": info.get("name") or "?",
                "cpu": cpu,
                "mem": mem,
                "threads": info.get("num_threads") or 0,
                "user": (info.get("username") or "").split("\\")[-1],
            })
        self._procs = seen
        return out


class SimulatedSource:
    """Valores sintéticos y deterministas: `metrics` series y `procs` procesos."""

    def __init__(self, metrics: int = 30, procs: int = 300, seed: int = 1):
        self.cores = max(1, metrics - 6)
        self.total_memory = 16.0
        self.rng = random.Random(seed)
        self.prng = random.Random(seed + 1)  # processes() corre en otro hilo: generador propio
        self.t = 0
        self.procs = [
            {"pid": 1000 + i, "name": f"{self.rng.choice(['svc', 'app', 'worker', 'node', 'python', 'chrome'])}-{i}.exe",
             "threads": self.rng.randint(1, 60), "user": self.rng.choice(["yo", "SYSTEM", "red"])}
            for i in range(procs)
        ]
        self.forced: dict[str, float] = {}  # para pruebas: fijar el valor de una métrica

    def describe(self) -> list[dict]:
        return SystemSource.describe(self)  # type: ignore[arg-type]

    def read(self) -> dict[str, float]:
        self.t += 1
        t = self.t
        values = {
            "cpu": 40 + 30 * math.sin(t / 15),
            "mem": 55 + 10 * math.sin(t / 40),
            "net_down": 2e6 * (1 + math.sin(t / 7)),
            "net_up": 3e5 * (1 + math.cos(t / 9)),
            "disk_read": 1e6 * (1 + math.sin(t / 5)) if t % 20 < 10 else 0.0,
            "disk_write": 5e5 * (1 + math.cos(t / 11)),
        }
        for i in range(self.cores):
            values[f"core{i}"] = max(0.0, min(100.0, 50 + 45 * math.sin(t / 10 + i) + self.rng.uniform(-5, 5)))
        values.update(self.forced)
        return values

    def processes(self) -> list[dict]:
        rng = self.prng
        return [{**p, "cpu": rng.uniform(0, 8) if rng.random() < 0.3 else 0.0, "mem": rng.randint(5, 900) << 20} for p in self.procs]


# -- monitor ------------------------------------------------------------------
class Monitor:
    def __init__(self, source: Any, capacity: int = 240):
        self.source = source
        self.series: dict[str, Series] = {}
        for d in source.describe():
            self.series[d["id"]] = Series(d["id"], d["label"], d.get("unit", "%"), d.get("max", 100.0), d.get("warn"), capacity)
        self.main = [s for s in self.series.values() if not s.id.startswith("core")]
        self.cores = [s for s in self.series.values() if s.id.startswith("core")]
        self.processes = state([])
        self.samples = 0  # para mediciones
        self.process_reads = 0

    def sample(self) -> None:
        values = self.source.read()
        with batch():
            for id, v in values.items():
                s = self.series.get(id)
                if s is not None:
                    s.push(v)
        self.samples += 1

    async def refresh_processes(self) -> None:
        from janelkit import background

        procs = await background(self.source.processes)
        self.processes.value = procs
        self.process_reads += 1

    def alerts(self) -> list[Series]:
        return [s for s in self.series.values() if s.alert.value]
