"""Frontera entre el núcleo y el ecosistema (docs/alcance.md).

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
    assert {p.name for p in ECOSYSTEM} >= {"janelkit_i18n", "janelkit_desktop"}


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
