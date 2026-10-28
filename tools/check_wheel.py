"""Verificación de distribución (PR-010 / sección 14.5 del plan).

1. Construye wheel y sdist.
2. Comprueba que ambos incluyen runtime, compilador y plantillas.
3. Instala el wheel en un entorno virtual nuevo, fuera del repositorio.
4. Ejecuta `janel --help`, `janel new demo` y `python main.py` (Qt offscreen)
   y confirma que `janelkit` se importa desde el entorno, no desde el checkout.
5. Construye e instala junto a él los wheels de las extensiones (janelkit-i18n,
   janelkit-desktop) y comprueba que se importan y que pip acepta su rango del núcleo.

Uso:  python tools/check_wheel.py [--keep]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXTENSIONS = {"janelkit-i18n": "janelkit_i18n", "janelkit-desktop": "janelkit_desktop"}
REQUIRED = [
    "janelkit/__init__.py",
    "janelkit/compiler/qml_generator.py",
    "janelkit/runtime/component.py",
    "janelkit/cli/main.py",
    "janelkit/templates/starter/main.py.tmpl",
    "janelkit/templates/starter/src/App.janel.tmpl",
    "janelkit/templates/starter/dot-gitignore.tmpl",
    "janelkit/qml/Janel/qmldir",
    "janelkit/qml/Janel/jk.js",
    "janelkit/qml/Janel/JkWindow.qml",
    "janelkit/qml/Janel/JkButton.qml",
]


def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("   $", " ".join(str(c) for c in cmd), flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"falló: {' '.join(str(c) for c in cmd)}")
    return proc


def check_contents(names: list[str], label: str, prefix: str = "") -> None:
    missing = [r for r in REQUIRED if prefix + r not in names]
    if missing:
        raise SystemExit(f"{label} incompleto, faltan: {missing}")
    print(f"   {label}: {len(names)} archivos, plantillas incluidas")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep", action="store_true", help="no borrar el directorio temporal")
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="janelkit-check-"))
    try:
        step("Construyendo wheel y sdist")
        dist = work / "dist"
        run([sys.executable, "-m", "build", "--outdir", str(dist), str(REPO / "packages" / "janelkit")])
        wheel = next(dist.glob("*.whl"))
        sdist = next(dist.glob("*.tar.gz"))

        step("Revisando contenido")
        with zipfile.ZipFile(wheel) as zf:
            check_contents(zf.namelist(), wheel.name)
        with tarfile.open(sdist) as tf:
            root = tf.getnames()[0].split("/")[0]
            check_contents(tf.getnames(), sdist.name, prefix=f"{root}/src/")

        step("Instalando en un entorno virtual limpio")
        venv = work / "venv"
        run([sys.executable, "-m", "venv", str(venv)])
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        py = bindir / ("python.exe" if os.name == "nt" else "python")
        janel = bindir / ("janel.exe" if os.name == "nt" else "janel")
        run([str(py), "-m", "pip", "install", "--quiet", str(wheel)])

        outside = work / "proyectos"
        outside.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        env.update(QT_QPA_PLATFORM="offscreen", JANELKIT_EXIT_AFTER_MS="500")

        step("Comprobando que janelkit se importa desde el entorno instalado")
        origin = run([str(py), "-c", "import janelkit; print(janelkit.__file__)"], cwd=outside, env=env).stdout.strip()
        print(f"   {origin}")
        if Path(origin).resolve().is_relative_to(REPO):
            raise SystemExit("janelkit se está importando desde el repositorio, no desde el wheel")

        step("janel --help / --version")
        run([str(janel), "--help"], cwd=outside, env=env)
        print("   " + run([str(janel), "--version"], cwd=outside, env=env).stdout.strip())

        step("janel new demo")
        run([str(janel), "new", "demo"], cwd=outside, env=env)
        demo = outside / "demo"
        for rel in ("main.py", "src/App.janel", "pyproject.toml", ".gitignore"):
            if not (demo / rel).is_file():
                raise SystemExit(f"janel new no creó {rel}")
        print("   main.py y src/App.janel creados")

        step("python main.py")
        proc = run([str(py), "main.py"], cwd=demo, env=env)
        noise = [ln for ln in proc.stderr.splitlines() if ln.strip() and not ln.startswith("qt.qpa")]
        if noise:
            raise SystemExit("la aplicación emitió avisos o errores:\n" + "\n".join(noise))
        print("   la ventana se abrió (controles del módulo Janel incluidos) y terminó con código 0, sin avisos")

        step("janel build")
        run([str(janel), "build"], cwd=demo, env=env)
        if not (demo / "build" / "qml" / "App.qml").is_file():
            raise SystemExit("janel build no generó build/qml/App.qml")
        print("   todos los componentes compilan; QML en build/qml")

        step("Extensiones: " + ", ".join(EXTENSIONS))
        for name in EXTENSIONS:
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist), str(REPO / "packages" / name)])
        wheels = [next(dist.glob(f"{module}-*.whl")) for module in EXTENSIONS.values()]
        run([str(py), "-m", "pip", "install", "--quiet", *map(str, wheels)])
        run([str(py), "-m", "pip", "check"], cwd=outside, env=env)
        code = "import janelkit_desktop as d, janelkit_i18n as i; print(d.__file__); print(i.__file__)"
        origins = [Path(o) for o in run([str(py), "-c", code], cwd=outside, env=env).stdout.splitlines()]
        if any(o.resolve().is_relative_to(REPO) for o in origins):
            raise SystemExit("las extensiones se importan desde el repositorio, no desde los wheels")
        if not (origins[0].parent / "icon.png").is_file():
            raise SystemExit("el wheel de janelkit-desktop no incluye icon.png")
        print("   instaladas sobre el núcleo del wheel; pip check sin conflictos")

        print("\nOK: el recorrido pip install -> janel new -> python main.py funciona fuera del repositorio, también con las extensiones.")
        return 0
    finally:
        if args.keep:
            print(f"\n(directorio conservado: {work})")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
