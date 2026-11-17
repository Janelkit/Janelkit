"""`janel dev`: ejecuta la aplicación y la recarga al guardar.

- Cambios en `.janel`: la propia aplicación (con JANELKIT_DEV=1) recompila y
  vuelve a montar la vista sin reiniciar el proceso.
- Cambios en `.py` o en `.qml` propios del proyecto: este supervisor reinicia
  `python main.py`. Los módulos Python no se pueden recargar de forma fiable, y
  Qt (antes de 6.12) no vuelve a leer en el mismo proceso un `.qml` ya cargado.
  Antes de reiniciar le pide a la aplicación que guarde su estado (los `state`
  de cada componente y la geometría de la ventana), y el proceso nuevo lo
  recupera: se conserva lo mismo que al recargar un `.janel`.

El arranque sigue siendo `main.py`: lo que funciona con `janel dev` funciona
igual con `python main.py`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..qt_backend.application import DEV_ENV, DEV_STATE_ENV, DEV_STATE_REQUEST

POLL_SECONDS = 0.4
SAVE_SECONDS = 3.0  # lo que se espera a que la aplicación guarde su estado y salga sola
IGNORED_DIRS = {".venv", "venv", "env", ".git", "__pycache__", "build", "dist", "node_modules", ".pytest_cache"}


class DevError(Exception):
    pass


def find_entry(target: Path) -> Path:
    """`main.py` del proyecto a partir de una carpeta o del propio archivo."""
    target = target.resolve()
    main = target / "main.py" if target.is_dir() else target
    if not main.is_file():
        raise DevError(f"no se encontró {main}; ejecuta janel dev dentro de un proyecto creado con janel new")
    return main


RESTART_SUFFIXES = (".py", ".qml")


def restart_files(project: Path) -> dict[str, float]:
    """Archivos cuyo cambio exige reiniciar el proceso: `.py` y `.qml` del proyecto."""
    found: dict[str, float] = {}
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith(RESTART_SUFFIXES):
                path = os.path.join(root, name)
                try:
                    found[path] = os.stat(path).st_mtime
                except OSError:
                    pass
    return found


def _changed(before: dict[str, float], after: dict[str, float]) -> list[str]:
    return sorted({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)})


def _stop(proc: subprocess.Popen, state: Path | None = None) -> None:
    """Para la aplicación. Con `state`, antes le pide que guarde ahí su estado y salga sola."""
    if state is not None and proc.poll() is None:
        request = Path(str(state) + DEV_STATE_REQUEST)
        try:
            request.touch()
            proc.wait(timeout=SAVE_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass  # no responde (o no es una aplicación JanelKit): se reinicia sin estado
        finally:
            request.unlink(missing_ok=True)
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
    state_dir = Path(tempfile.mkdtemp(prefix="janel-dev-"))  # una carpeta por sesión de janel dev
    state = state_dir / "state.pickle"
    env = {**os.environ, DEV_ENV: "1", DEV_STATE_ENV: str(state), "PYTHONUNBUFFERED": "1"}
    print(f"[janel dev] {main.relative_to(project.parent)} — Ctrl+C para salir", flush=True)
    try:
        return _supervise(main, project, env, state, python)
    finally:
        shutil.rmtree(state_dir, ignore_errors=True)


def _supervise(main: Path, project: Path, env: dict[str, str], state: Path, python: str) -> int:
    while True:
        proc = subprocess.Popen([python, str(main)], cwd=project, env=env)
        snapshot = restart_files(project)
        restart = False
        try:
            while True:
                code = proc.poll()
                if code is not None:
                    if code == 0:
                        return 0
                    print(f"[janel dev] la aplicación terminó con código {code}; esperando cambios en .py o .qml…", flush=True)
                    while not (changed := _changed(snapshot, restart_files(project))):
                        time.sleep(POLL_SECONDS)
                    restart = True
                else:
                    time.sleep(POLL_SECONDS)
                    changed = _changed(snapshot, restart_files(project))
                    restart = bool(changed)
                if restart:
                    names = ", ".join(Path(p).name for p in changed[:3]) + ("…" if len(changed) > 3 else "")
                    print(f"[janel dev] cambió {names}: reiniciando", flush=True)
                    _stop(proc, state)
                    break
        except KeyboardInterrupt:
            _stop(proc)
            return 130
