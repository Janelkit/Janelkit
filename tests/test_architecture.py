"""Capas del núcleo: cada módulo solo importa capas iguales o inferiores, sin ciclos entre áreas.

Capas (de abajo arriba), según la ubicación del módulo:

    L0  reactividad   reactivity · diagnostics · events                         (sin Qt)
    L1  lenguaje      compiler (también el catálogo de elementos y el CSS)       (sin Qt)
    L2  runtime       runtime · lifecycle · pages · windows · tasks · timers · storage · locale · themes · displays
    L3  backend Qt    qt_backend · video
    L4  herramientas  cli · inspect · testing · ext · el paquete raíz (fachada pública)

Se cuentan también los imports diferidos (dentro de funciones): esconder un import no
quita la dependencia.

`DEUDAS` lista las violaciones que existían al escribir esta prueba. Solo puede encoger:
- una violación nueva que no está en la lista hace fallar la prueba;
- una deuda que ya no existe también, para que se borre de la lista al resolverla.
"""
from __future__ import annotations

import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "packages" / "janelkit" / "src" / "janelkit"

# Prefijo de módulo (sin "janelkit.") → capa. Gana el prefijo más largo.
LAYERS = {
    "reactivity": 0, "diagnostics": 0, "events": 0,
    "compiler": 1,
    "runtime": 2, "lifecycle": 2, "pages": 2, "windows": 2, "tasks": 2, "timers": 2,
    "storage": 2, "locale": 2, "themes": 2, "displays": 2,
    "qt_backend": 3, "video": 3,
    "cli": 4, "inspect": 4, "testing": 4, "ext": 4, "": 4,
}
WITHOUT_QT = 1  # L0 y L1 no importan PySide6 ni shiboken6

# Deudas conocidas (2026-11-04, auditoría de planeacion-0.2.0/arquitectura.md).
# Cada entrada: "módulo -> módulo importado". Ver los hallazgos H1-H4 del plan.
DEUDAS: set[str] = set()  # H1 resuelta: el catálogo vive en compiler/elements.py

# Ciclos conocidos entre áreas («área» = primer nivel del paquete).
CICLOS: set[frozenset[str]] = set()  # H1, H2 y H3 resueltos en F3


def _modules() -> dict[str, Path]:
    found = {}
    for path in CORE.rglob("*.py"):
        parts = path.relative_to(CORE).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        found[".".join(parts)] = path
    return found


MODULES = _modules()


def layer(module: str) -> int:
    best = max((p for p in LAYERS if p == "" or module == p or module.startswith(p + ".")), key=len)
    return LAYERS[best]


def area(module: str) -> str:
    return module.split(".")[0]


def _targets(module: str, node: ast.ImportFrom | ast.Import) -> list[str]:
    """Módulos internos (relativos a `janelkit`) o externos (`ext:nombre`) que importa `node`."""
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
        return [n[len("janelkit."):] if n.startswith("janelkit.") else "" if n == "janelkit" else f"ext:{n}" for n in names]
    if node.level == 0:
        name = node.module or ""
        if name != "janelkit" and not name.startswith("janelkit."):
            return [f"ext:{name}"]
        base = name[len("janelkit."):] if name.startswith("janelkit.") else ""
    else:
        package = module.split(".") if MODULES[module].name == "__init__.py" else module.split(".")[:-1]
        if module == "":
            package = []
        package = package[: len(package) - (node.level - 1)]
        base = ".".join([*package, *([node.module] if node.module else [])])
    out = []
    for alias in node.names:  # `from . import storage` importa el módulo janelkit.storage
        sub = f"{base}.{alias.name}" if base else alias.name
        out.append(sub if sub in MODULES else base)
    return out


def _imports() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for module, path in MODULES.items():
        targets: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                targets.update(_targets(module, node))
        graph[module] = targets
    return graph


GRAPH = _imports()


def upward_imports() -> set[str]:
    return {
        f"{src or 'janelkit'} -> {dst or 'janelkit'}"
        for src, targets in GRAPH.items()
        for dst in targets
        if not dst.startswith("ext:") and dst in MODULES and layer(dst) > layer(src)
    }


def area_cycles() -> set[frozenset[str]]:
    edges = {
        (area(src), area(dst))
        for src, targets in GRAPH.items()
        for dst in targets
        if not dst.startswith("ext:") and dst in MODULES and src and dst and area(src) != area(dst)
    }
    return {frozenset((a, b)) for a, b in edges if (b, a) in edges}


def test_the_layer_map_covers_every_module():
    # Un módulo nuevo en un sitio no previsto cae en la capa del paquete raíz (L4): avisar.
    unmapped = [m for m in MODULES if m and layer(m) == 4 and area(m) not in {"cli", "inspect", "testing", "ext"}]
    assert unmapped == [], f"módulos sin capa en LAYERS: {unmapped}"


def test_no_new_upward_imports():
    new = sorted(upward_imports() - DEUDAS)
    assert new == [], "imports hacia una capa superior (ver la cabecera de este archivo):\n  " + "\n  ".join(new)


def test_resolved_debts_are_removed_from_the_list():
    stale = sorted(DEUDAS - upward_imports())
    assert stale == [], "deudas ya resueltas: bórralas de DEUDAS:\n  " + "\n  ".join(stale)


def test_no_new_cycles_between_areas():
    cycles = area_cycles()
    new = sorted(" <-> ".join(sorted(c)) for c in cycles - CICLOS)
    stale = sorted(" <-> ".join(sorted(c)) for c in CICLOS - cycles)
    assert new == [], "ciclos nuevos entre áreas:\n  " + "\n  ".join(new)
    assert stale == [], "ciclos ya resueltos: bórralos de CICLOS:\n  " + "\n  ".join(stale)


def test_language_and_reactivity_do_not_import_qt():
    offenders = sorted(
        f"{src} -> {dst[4:]}"
        for src, targets in GRAPH.items()
        if src and layer(src) <= WITHOUT_QT
        for dst in targets
        if dst.startswith(("ext:PySide6", "ext:shiboken6"))
    )
    assert offenders == [], "L0 y L1 no pueden usar Qt:\n  " + "\n  ".join(offenders)
