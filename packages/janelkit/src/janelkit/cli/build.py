"""`janel build`: compila todos los componentes del proyecto y guarda el QML generado.

Sirve para validar el proyecto completo (también componentes que todavía no se
usan) y para inspeccionar el QML. **No genera un ejecutable**: empaquetar
aplicaciones para distribuirlas es un paso distinto, previsto para más adelante.

Con `--pyinstaller` da además lo que el análisis de PyInstaller no ve: los módulos que
solo importan los `.janel` y los recursos (`<image src>`, `<button icon>`) fuera de `src/`.
"""
from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..compiler import CompileSession, CompiledComponent
from ..compiler.ast_nodes import EachBlock, Element, IfBlock, KeyBlock
from ..diagnostics import Diagnostic, JanelError


@dataclass
class BuildResult:
    out_dir: Path
    written: list[Path] = field(default_factory=list)
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)
    modules: set[str] = field(default_factory=set)  # importados desde los .janel (sin la biblioteca estándar)
    resources: list[Path] = field(default_factory=list)  # rutas fijas de src/icon fuera de src/
    project: Path | None = None

    def pyinstaller_options(self) -> list[str]:
        """Opciones para PyInstaller, una por elemento: `--hidden-import=m` y `--add-data=ruta{sep}destino`.
        Las rutas son relativas a la carpeta del proyecto, desde donde se ejecuta pyinstaller."""
        options = [f"--hidden-import={m}" for m in sorted(self.modules)]
        for path in self.resources:
            rel = path.relative_to(self.project) if self.project else path
            options.append(f"--add-data={rel.as_posix()}{os.pathsep}{rel.parent.as_posix()}")
        return options

    @property
    def ok(self) -> bool:
        return not self.errors


def find_source_dir(target: Path) -> Path:
    target = target.resolve()
    if target.is_file():
        return target.parent
    src = target / "src"
    return src if (src / "App.janel").is_file() else target


def build_project(target: Path, out_dir: Path | None = None) -> BuildResult:
    src = find_source_dir(target)
    project = src.parent if src.name == "src" else src
    out = (out_dir or project / "build" / "qml").resolve()
    result = BuildResult(out)

    entry = src / "App.janel"
    files = sorted(src.rglob("*.janel"))
    if not files:
        result.errors.append(Diagnostic(f"no hay archivos .janel en {src}"))
        return result

    session = CompileSession([src])
    compiled: dict[str, CompiledComponent] = {}

    def attempt(path: Path, as_window: bool) -> None:
        try:
            session.compile(path, as_window=as_window)
        except JanelError as exc:
            result.errors.extend(exc.diagnostics)

    if entry.is_file():
        attempt(entry, as_window=True)
    for path in files:
        if str(path.resolve()) not in session.registry and path != entry:
            # Sin usar en ninguna plantilla: un componente, o una ventana para open_window.
            attempt(path, as_window=_is_window(session, path))
    compiled.update(session.registry)
    # Un archivo con errores puede intentarse dos veces (como hijo y por sí mismo).
    result.errors = list({(d.message, d.location): d for d in result.errors}.values())

    for key, comp in compiled.items():
        result.warnings.extend(comp.warnings)
        rel = _relative(Path(key), src)
        target_file = out / rel.with_suffix(".qml")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(comp.qml, encoding="utf-8")
        result.written.append(target_file)
        result.modules |= _imported_modules(comp, Path(key), src)
        try:
            sfc, _ = session.load(Path(key))
        except JanelError:
            continue
        inside, mine = src.resolve(), project.resolve()
        for path in _resources(sfc.template, Path(key).parent):
            if not path.is_relative_to(inside) and path.is_relative_to(mine) and path not in result.resources:
                result.resources.append(path)
    result.project = project.resolve()
    return result


_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")


def _imported_modules(comp: CompiledComponent, path: Path, src: Path) -> set[str]:
    """Módulos que importa el script (también dentro de funciones), salvo la biblioteca estándar
    y janelkit. Los imports de componentes ya no están en el árbol: los inyecta el runtime."""
    tree = getattr(comp.ir.script_info, "tree", None)
    if tree is None:
        return set()
    package = list(path.parent.relative_to(src).parts) if path.is_relative_to(src) else None
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if package is None or node.level - 1 > len(package):
                    continue
                base = package[: len(package) - (node.level - 1)]
                module = ".".join([*base, *([node.module] if node.module else [])])
            else:
                module = node.module or ""
            if module:
                found.add(module)
            for alias in node.names:  # `from paquete import modulo`: el submódulo también
                if alias.name != "*" and module and _is_module(f"{module}.{alias.name}", src):
                    found.add(f"{module}.{alias.name}")
    skip = set(sys.stdlib_module_names) | {"janelkit", "__future__"}
    return {m for m in found if m.split(".")[0] not in skip}


def _is_module(name: str, src: Path) -> bool:
    """Si `name` es un módulo (en src/ o instalado), buscándolo en disco: sin importar nada."""
    first, *rest = name.split(".")
    try:
        spec = importlib.util.find_spec(first)  # solo el primer nivel: no importa el paquete
    except (ImportError, ValueError):
        spec = None
    folders = [src / first] + ([Path(p) for p in spec.submodule_search_locations] if spec and spec.submodule_search_locations else [])
    for i, part in enumerate(rest):
        last = i == len(rest) - 1
        nxt = []
        for folder in folders:
            files = [folder / f"{part}{suffix}" for suffix in (".py", *importlib.machinery.EXTENSION_SUFFIXES)]
            if last and (any(f.is_file() for f in files) or (folder / part / "__init__.py").is_file()):
                return True
            if (folder / part).is_dir():
                nxt.append(folder / part)
        folders = nxt
    return False


def _resources(nodes: list, folder: Path) -> list[Path]:
    """Rutas relativas fijas de `<image src="...">` y `<button icon="...">` (las de una expresión no se saben)."""
    out: list[Path] = []
    for node in nodes:
        if isinstance(node, Element):
            for attr in node.attributes:
                value = attr.value
                if attr.name in ("src", "icon") and isinstance(value, str) and value:
                    if not _URL.match(value) and not Path(value).is_absolute():
                        out.append((folder / value).resolve())
            out += _resources(node.children, folder)
        elif isinstance(node, IfBlock):
            for branch in node.branches:
                out += _resources(branch.children, folder)
        elif isinstance(node, (EachBlock, KeyBlock)):
            out += _resources(node.children, folder) + _resources(node.else_children or [], folder)
    return out


def _relative(path: Path, src: Path) -> Path:
    """Dónde va el QML de `path`: su ruta en `src`, o la de su paquete instalado en `_paquetes/`."""
    if path.is_relative_to(src):
        return path.relative_to(src)
    entries = [Path(e).resolve() for e in sys.path if e and Path(e).is_dir()]
    inside = [e for e in entries if path.is_relative_to(e)]
    if inside:
        return Path("_paquetes") / path.relative_to(max(inside, key=lambda e: len(e.parts)))
    return Path("_paquetes") / path.name


def _is_window(session: CompileSession, path: Path) -> bool:
    """El archivo tiene <window> como raíz (se abrirá con open_window)."""
    try:
        sfc, _ = session.load(path)
    except JanelError:
        return False
    roots = sfc.root_elements
    return bool(roots) and getattr(roots[0], "tag", None) == "window"
