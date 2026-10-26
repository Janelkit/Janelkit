"""`flux dev`: ejecuta la aplicación y la recarga al guardar.

- Cambios en `.flux`: la propia aplicación (con FLUXUI_DEV=1) recompila y
  vuelve a montar la vista sin reiniciar el proceso.
- Cambios en `.py` del proyecto: este supervisor reinicia `python main.py`,
  porque los módulos Python no se pueden recargar de forma fiable.

El arranque sigue siendo `main.py`: lo que funciona con `flux dev` funciona
igual con `python main.py`.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ..qt_backend.application import DEV_ENV

POLL_SECONDS = 0.4
IGNORED_DIRS = {".venv", "venv", "env", ".git", "__pycache__", "build", "dist", "node_modules", ".pytest_cache"}


class DevError(Exception):
    pass


def find_entry(target: Path) -> Path:
    """`main.py` del proyecto a partir de una carpeta o del propio archivo."""
    target = target.resolve()
    main = target / "main.py" if target.is_dir() else target
    if not main.is_file():
        raise DevError(f"no se encontró {main}; ejecuta flux dev dentro de un proyecto creado con flux new")
    return main


def python_files(project: Path) -> dict[str, float]:
    found: dict[str, float] = {}
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(root, name)
                try:
                    found[path] = os.stat(path).st_mtime
                except OSError:
                    pass
    return found


def _changed(before: dict[str, float], after: dict[str, float]) -> list[str]:
    return sorted({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)})


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def run_dev(target: Path, python: str = sys.executable) -> int:
    main = find_entry(target)
    project = main.parent
    env = {**os.environ, DEV_ENV: "1", "PYTHONUNBUFFERED": "1"}
    print(f"[flux dev] {main.relative_to(project.parent)} — Ctrl+C para salir", flush=True)
    while True:
        proc = subprocess.Popen([python, str(main)], cwd=project, env=env)
        snapshot = python_files(project)
        restart = False
        try:
            while True:
                code = proc.poll()
                if code is not None:
                    if code == 0:
                        return 0
                    print(f"[flux dev] la aplicación terminó con código {code}; esperando cambios en .py…", flush=True)
                    while not (changed := _changed(snapshot, python_files(project))):
                        time.sleep(POLL_SECONDS)
                    restart = True
                else:
                    time.sleep(POLL_SECONDS)
                    changed = _changed(snapshot, python_files(project))
                    restart = bool(changed)
                if restart:
                    names = ", ".join(Path(p).name for p in changed[:3]) + ("…" if len(changed) > 3 else "")
                    print(f"[flux dev] cambió {names}: reiniciando", flush=True)
                    _stop(proc)
                    break
        except KeyboardInterrupt:
            _stop(proc)
            return 130
