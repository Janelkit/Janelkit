"""Los paquetes de packages/ son coherentes entre sí (docs/api.md, política de versiones).

- La versión del pyproject.toml es la `__version__` del módulo.
- Cada extensión declara un rango del núcleo que incluye la versión del núcleo de este repositorio.
"""
import importlib
import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parents[1]
PYTHON_PACKAGES = sorted(p for p in (REPO / "packages").iterdir() if (p / "pyproject.toml").exists())
EXTENSIONS = [p for p in PYTHON_PACKAGES if p.name != "janelkit"]


def project(package: Path) -> dict:
    """name, version y dependencies de [project] (sin tomllib, que falta en Python 3.10)."""
    text = (package / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[project\]\n(.*?)(?=^\[)", text, re.M | re.S)[1]
    deps = re.search(r"^dependencies = \[(.*?)\]", section, re.M | re.S)
    return {
        "name": re.search(r'^name = "([^"]+)"', section, re.M)[1],
        "version": re.search(r'^version = "([^"]+)"', section, re.M)[1],
        "dependencies": re.findall(r'"([^"]+)"', deps[1]) if deps else [],
    }


def test_the_repository_has_the_expected_packages():
    assert [project(p)["name"] for p in PYTHON_PACKAGES] == ["janelkit", "janelkit-desktop", "janelkit-i18n"]


@pytest.mark.parametrize("package", PYTHON_PACKAGES, ids=lambda p: p.name)
def test_pyproject_version_is_the_module_version(package):
    meta = project(package)
    module = importlib.import_module(meta["name"].replace("-", "_"))
    assert module.__version__ == meta["version"]


@pytest.mark.parametrize("package", EXTENSIONS, ids=lambda p: p.name)
def test_extensions_accept_the_core_of_this_repository(package):
    core_version = project(REPO / "packages" / "janelkit")["version"]
    (core,) = [Requirement(d) for d in project(package)["dependencies"] if Requirement(d).name == "janelkit"]
    assert core.specifier.contains(core_version, prereleases=True), f"{core} no admite janelkit {core_version}"
    assert not core.specifier.contains("99"), f"{core} debe tener límite superior (política de versiones)"
