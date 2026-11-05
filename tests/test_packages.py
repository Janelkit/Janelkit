"""Los paquetes de packages/ son coherentes entre sí (docs/api.md, política de versiones).

- La versión del pyproject.toml es la `__version__` del módulo, con cuatro números (E.S.M.m).
- Todos los paquetes están en la misma serie (E.S), y cada extensión pide exactamente esa
  serie del núcleo: janelkit>=E.S,<E.(S+1).
"""
import importlib
import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

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
    assert [project(p)["name"] for p in PYTHON_PACKAGES] == ["janelkit", "janelkit-desktop", "janelkit-i18n", "janelkit-router", "janelkit-store"]


@pytest.mark.parametrize("package", PYTHON_PACKAGES, ids=lambda p: p.name)
def test_pyproject_version_is_the_module_version(package):
    meta = project(package)
    module = importlib.import_module(meta["name"].replace("-", "_"))
    assert module.__version__ == meta["version"]


def series() -> tuple[int, int]:
    major, minor, *_ = (int(n) for n in project(REPO / "packages" / "janelkit")["version"].split("."))
    return major, minor


@pytest.mark.parametrize("package", PYTHON_PACKAGES, ids=lambda p: p.name)
def test_versions_have_four_numbers_and_share_the_series(package):
    version = project(package)["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version), f"{version}: se esperan cuatro números (E.S.M.m)"
    assert version.startswith("%d.%d." % series()), (
        f"{version} no está en la serie del núcleo ({'%d.%d' % series()}): python tools/versioning.py series E.S")


@pytest.mark.parametrize("package", EXTENSIONS, ids=lambda p: p.name)
def test_extensions_ask_for_the_series_of_this_repository(package):
    major, minor = series()
    expected = f">={major}.{minor},<{major}.{minor + 1}"
    (core,) = [Requirement(d) for d in project(package)["dependencies"] if Requirement(d).name == "janelkit"]
    assert core.specifier == SpecifierSet(expected), f"{core}: en la serie {major}.{minor} se pide janelkit{expected}"
