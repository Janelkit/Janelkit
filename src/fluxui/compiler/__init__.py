"""Compilador .flux: SFC -> AST -> IR -> QML + tablas para el runtime Python.

`compile_file` compila el componente raíz y, recursivamente, los componentes
`.flux` que importa. Todos comparten un registro (`registry`) indexado por
ruta, de modo que cada archivo se compila una sola vez y los componentes
recursivos funcionan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..diagnostics import Diagnostic, FluxError, SourceLocation
from .ast_nodes import SFC
from .ir import IRComponent
from .lowering import ComponentInterface, lower
from .qml_generator import SourceMap, generate_qml, lookup
from .script_analysis import ScriptInfo, analyze_script
from .sfc_parser import parse_file, parse_sfc


@dataclass
class CompiledComponent:
    ir: IRComponent
    qml: str
    source_map: SourceMap
    # ruta -> componente compilado; compartido por todos los de una misma compilación
    registry: dict[str, "CompiledComponent"] = field(default_factory=dict, repr=False, compare=False)
    # Objetos derivados que el runtime calcula una sola vez (código compilado, clases puente).
    cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def file(self) -> str:
        return self.ir.file

    @property
    def warnings(self) -> list[Diagnostic]:
        return self.ir.warnings

    @property
    def all_warnings(self) -> list[Diagnostic]:
        """Advertencias de este componente y de todos los que usa."""
        seen = [self] + [c for c in self.registry.values() if c is not self]
        return [w for c in seen for w in c.warnings]

    @property
    def files(self) -> list[str]:
        """Archivos .flux que forman la aplicación (para observar cambios)."""
        return list(dict.fromkeys([self.file, *(c.file for c in self.registry.values())]))

    def component(self, path: str) -> "CompiledComponent":
        return self.registry[path]

    def flux_location(self, qml_line: int) -> SourceLocation | None:
        return lookup(self.source_map, qml_line)


class CompileSession:
    """Compila un árbol de componentes resolviendo imports respecto a `roots`."""

    def __init__(self, roots: list[Path]):
        self.roots = [Path(r).resolve() for r in roots]
        self.registry: dict[str, CompiledComponent] = {}
        self._loaded: dict[str, tuple[SFC, ScriptInfo]] = {}

    def compile(self, path: Path, as_window: bool) -> CompiledComponent:
        key = _key(path)
        if key in self.registry:
            return self.registry[key]
        sfc, info = self.load(path)
        return self._compile_loaded(key, sfc, info, as_window)

    def compile_source(self, source: str, file: str, as_window: bool = True) -> CompiledComponent:
        sfc = parse_sfc(source, file)
        info = analyze_script(sfc.script, file, sfc.source, self._resolver(Path(file)))
        return self._compile_loaded(file, sfc, info, as_window)

    def _compile_loaded(self, key: str, sfc: SFC, info: ScriptInfo, as_window: bool) -> CompiledComponent:
        ir = lower(sfc, info, as_window=as_window, interface=self.interface)
        qml, source_map = generate_qml(ir)
        compiled = CompiledComponent(ir, qml, source_map, registry=self.registry)
        self.registry[key] = compiled
        for child in ir.component_paths:
            self.compile(Path(child), as_window=False)
        return compiled

    def load(self, path: Path) -> tuple[SFC, ScriptInfo]:
        key = _key(path)
        if key not in self._loaded:
            sfc = parse_file(path)
            info = analyze_script(sfc.script, sfc.file, sfc.source, self._resolver(Path(path)))
            self._loaded[key] = (sfc, info)
        return self._loaded[key]

    def interface(self, path: Path) -> ComponentInterface:
        _, info = self.load(path)
        return ComponentInterface(dict(info.props), dict(info.events))

    def _resolver(self, file: Path):
        here = file.resolve().parent  # en memoria: el directorio actual

        def resolve(module: str | None, name: str, level: int) -> Path | None:
            if level:
                base = here
                for _ in range(level - 1):
                    base = base.parent
                bases = [base]
            else:
                bases = self.roots
            parts = module.split(".") if module else []
            for base in bases:
                folder = base.joinpath(*parts)
                # from components import TodoItem  -> components/TodoItem.flux
                candidate = folder / f"{name}.flux"
                if candidate.is_file():
                    return candidate.resolve()
                # from components.TodoItem import TodoItem  -> components/TodoItem.flux
                if parts and folder.name == name:
                    candidate = folder.with_suffix(".flux")
                    if candidate.is_file():
                        return candidate.resolve()
            return None

        return resolve


def _key(path: Path | str) -> str:
    return str(Path(path).resolve())


def compile_source(source: str, file: str = "<memoria>", roots: list[Path] | None = None) -> CompiledComponent:
    """Compila un componente raíz desde texto. Los imports se resuelven respecto a la carpeta de `file`."""
    base = Path(file).resolve().parent if file != "<memoria>" else Path.cwd()
    session = CompileSession(roots or [base])
    return session.compile_source(source, file)


def compile_file(path: str | Path, roots: list[Path] | None = None, as_window: bool = True) -> CompiledComponent:
    """Compila el componente `path` y los componentes que importa.

    `roots` son las carpetas desde las que se resuelven los imports absolutos
    (`from components.X import X`); por defecto, la carpeta de `path`.
    """
    path = Path(path)
    if not path.is_file():
        raise FluxError(Diagnostic(f"no se encontró el archivo {path}"))
    session = CompileSession(roots or [path.resolve().parent])
    return session.compile(path, as_window=as_window)


__all__ = [
    "CompileSession",
    "CompiledComponent",
    "ComponentInterface",
    "compile_file",
    "compile_source",
    "parse_file",
    "parse_sfc",
]
