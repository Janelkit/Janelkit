"""`flux new`: genera un proyecto a partir de las plantillas instaladas con el paquete.

Convenciones de las plantillas (en `fluxui/templates/<nombre>/`):
- Todo archivo termina en `.tmpl`; el sufijo se elimina al copiarlo. Así ningún
  `.py` de plantilla se importa ni se compila al instalar el wheel.
- Un nombre que empieza por `dot-` se copia con punto inicial (`dot-gitignore.tmpl` -> `.gitignore`).
- `{{project_name}}` y `{{fluxui_version}}` se sustituyen en el contenido.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # importlib.resources.abc no existe en Python 3.10
    from importlib.resources.abc import Traversable

from .. import __version__

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ScaffoldError(Exception):
    pass


@dataclass
class ScaffoldResult:
    root: Path
    files: list[Path]


def _template_root(template: str) -> Traversable:
    root = resources.files("fluxui") / "templates" / template
    if not root.is_dir():
        raise ScaffoldError(f"no existe la plantilla '{template}'")
    return root


def _output_name(name: str) -> str | None:
    if not name.endswith(".tmpl"):
        return None  # p. ej. __pycache__ u otros restos: se ignoran
    name = name[: -len(".tmpl")]
    if name.startswith("dot-"):
        name = "." + name[len("dot-"):]
    return name


def _walk(node: Traversable, rel: Path) -> list[tuple[Path, Traversable]]:
    out: list[tuple[Path, Traversable]] = []
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        if child.is_dir():
            if child.name != "__pycache__":
                out.extend(_walk(child, rel / child.name))
        else:
            name = _output_name(child.name)
            if name is not None:
                out.append((rel / name, child))
    return out


def create_project(name: str, parent: Path | None = None, template: str = "starter") -> ScaffoldResult:
    if not _NAME_RE.match(name):
        raise ScaffoldError(
            f"nombre de proyecto no válido: {name!r} (usa letras, números, '-', '_' o '.', empezando por letra o número)"
        )
    target = (parent or Path.cwd()) / name
    if target.exists():
        if not target.is_dir():
            raise ScaffoldError(f"ya existe un archivo llamado {target}")
        if any(target.iterdir()):
            raise ScaffoldError(f"el directorio {target} ya existe y no está vacío; no se sobrescribe nada")

    entries = _walk(_template_root(template), Path())
    values = {"project_name": name, "fluxui_version": __version__}
    created: list[Path] = []
    for rel, source in entries:
        content = source.read_text(encoding="utf-8")
        for key, value in values.items():
            content = content.replace("{{" + key + "}}", value)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")
        created.append(dest)
    return ScaffoldResult(target, created)
