"""Frontera entre el núcleo y el ecosistema (docs/arquitectura.md).

- El núcleo (`packages/janelkit`) no importa ningún paquete del ecosistema.
- Los paquetes del ecosistema solo usan la API pública del núcleo: los nombres de
  `janelkit.__all__` y los módulos públicos (docs/api.md), como cualquier paquete externo.
"""
import ast
from pathlib import Path

import pytest

import janelkit

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "packages" / "janelkit" / "src" / "janelkit"
ECOSYSTEM = sorted(p for p in (REPO / "packages").glob("janelkit-*/src/*") if p.is_dir() and not p.name.endswith(".egg-info"))
PUBLIC_MODULES = {"janelkit.ext", "janelkit.inspect", "janelkit.compiler", "janelkit.diagnostics"}


def imports(path: Path) -> list[tuple[str, list[str], int]]:
    """(módulo, nombres importados, nivel relativo) de cada import del archivo."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(alias.name, [], 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append((node.module or "", [alias.name for alias in node.names], node.level))
    return out


def test_there_are_ecosystem_packages_to_check():
    assert {p.name for p in ECOSYSTEM} >= {"janelkit_i18n", "janelkit_desktop", "janelkit_router", "janelkit_store"}


def test_the_core_does_not_import_the_ecosystem():
    ecosystem = {p.name for p in ECOSYSTEM}
    offenders = [
        f"{path.relative_to(CORE)} importa {target}"
        for path in CORE.rglob("*.py")
        for target, _, level in imports(path)
        if not level and target.split(".")[0] in ecosystem
    ]
    assert offenders == []


@pytest.mark.parametrize("package", ECOSYSTEM, ids=lambda p: p.name)
def test_ecosystem_packages_only_use_the_public_api(package):
    offenders = []
    for path in package.rglob("*.py"):
        where = path.relative_to(package.parent)
        for target, names, level in imports(path):
            if level:
                continue  # dentro del propio paquete
            if target == "janelkit":
                offenders += [f"{where}: janelkit.{n} no es público" for n in names if n not in janelkit.__all__]
            elif target.startswith("janelkit.") and target not in PUBLIC_MODULES:
                offenders.append(f"{where}: {target} es interno")
    assert offenders == []


# -- solo PySide6-Essentials -----------------------------------------------------------
# JanelKit depende de PySide6-Essentials, no de PySide6 completo (que añade PySide6-Addons:
# QtMultimedia, QtCharts, QtWebEngine…, unos 436 MB). Ningún paquete puede usar un módulo
# de Addons: en una instalación limpia no estaría.
ESSENTIALS = {
    "QtConcurrent", "QtCore", "QtDBus", "QtDesigner", "QtGui", "QtHelp", "QtNetwork", "QtOpenGL",
    "QtOpenGLWidgets", "QtPrintSupport", "QtQml", "QtQuick", "QtQuickControls2", "QtQuickTest",
    "QtQuickWidgets", "QtSql", "QtSvg", "QtSvgWidgets", "QtTest", "QtUiTools", "QtWidgets", "QtXml",
}  # fmt: skip
QML_ESSENTIALS = ("QtQuick", "QtQml", "QtCore", "Qt.labs.")
SOURCES = [REPO / "packages" / "janelkit" / "src" / "janelkit", *ECOSYSTEM]


@pytest.mark.parametrize("package", SOURCES, ids=lambda p: p.name)
def test_packages_only_use_qt_modules_from_pyside6_essentials(package):
    import re

    offenders = []
    for path in package.rglob("*"):
        if path.suffix == ".py":
            for target, names, level in imports(path):
                modules = [target] + [f"{target}.{n}" for n in names]
                offenders += [
                    f"{path.relative_to(package.parent)}: {m}"
                    for m in modules
                    if not level and m.startswith("PySide6.Qt") and m.split(".")[1] not in ESSENTIALS
                ]
        if path.suffix in (".py", ".qml", ".js", ".janel"):
            for module in re.findall(r"^\s*import (Qt[\w.]*)", path.read_text(encoding="utf-8"), re.M):
                if module != "Qt" and not module.startswith(QML_ESSENTIALS):
                    offenders.append(f"{path.relative_to(package.parent)}: QML import {module}")
    assert offenders == []


def test_the_core_depends_on_pyside6_essentials():
    pyproject = (REPO / "packages" / "janelkit" / "pyproject.toml").read_text(encoding="utf-8")
    assert '"PySide6-Essentials>=' in pyproject and '"PySide6>' not in pyproject
