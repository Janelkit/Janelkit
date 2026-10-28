"""Medición del arranque de los ejemplos y de la respuesta de una aplicación mediana.

Uso:  python tools/bench_app.py

- Arranque: importar JanelKit y PySide6, compilar, crear Qt y montar la vista.
- Respuesta: el explorador `examples/files` sobre una carpeta de 5000 archivos.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = ["counter", "todo", "notes", "books", "files"]

STARTUP = r"""
import os, sys, time
t0 = time.perf_counter()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
app_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(app_path.parent))
from janelkit.compiler import compile_file
from janelkit.qt_backend.application import Application
t1 = time.perf_counter()
compiled = compile_file(app_path)
t2 = time.perf_counter()
app = Application([])
m = app.mount(compiled)
app.process_events()
t3 = time.perf_counter()
print(f"{1000*(t1-t0):.0f}|{1000*(t2-t1):.0f}|{1000*(t3-t2):.0f}|{1000*(t3-t0):.0f}")
"""


def startup() -> None:
    print("| Ejemplo | Importar | Compilar | Qt + montar | Total |")
    print("|---|---|---|---|---|")
    for name in EXAMPLES:
        app = REPO / "examples" / name / "src" / "App.janel"
        # Un proceso nuevo por medición: el arranque incluye la importación en frío.
        out = subprocess.run([sys.executable, "-c", STARTUP, str(app)], capture_output=True, text=True, check=True)
        imp, comp, mount, total = out.stdout.strip().splitlines()[-1].split("|")
        print(f"| {name} | {imp} ms | {comp} ms | {mount} ms | {total} ms |")


def responsiveness(files: int = 5000) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from janelkit.inspect import mount

    folder = Path(tempfile.mkdtemp(prefix="janelkit-bench-"))
    for i in range(files):
        (folder / f"archivo_{i:05d}.txt").write_text("x" * (i % 97))
    os.environ["JANEL_FILES_START"] = str(folder)

    print(f"\n| Explorador, {files} archivos | Tiempo |")
    print("|---|---|")

    def timed(label: str, fn) -> None:
        t0 = time.perf_counter()
        fn()
        print(f"| {label} | {1000 * (time.perf_counter() - t0):.0f} ms |")

    with mount(REPO / "examples" / "files" / "src" / "App.janel") as app:
        timed("Listar la carpeta (hilo aparte + lista)", lambda: app.wait(until=lambda: app.get("listing").value is not None))
        field = app.find(placeholder="Filtrar por nombre (Ctrl+F)")
        timed("Filtrar (quedan 10)", lambda: field.type("_0004"))
        timed("Quitar el filtro (vuelven todos)", lambda: field.type(""))
        timed("Ordenar por tamaño", lambda: app.find("Select").choose("Tamaño"))
        timed("Elegir un archivo", lambda: app.find("Text", text=app.get("visible")[0]["name"]).click())


if __name__ == "__main__":
    startup()
    responsiveness()
