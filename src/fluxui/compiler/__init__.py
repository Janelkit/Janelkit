"""Compilador .flux: SFC -> AST -> IR -> QML + tablas para el runtime Python.

`compile_file` compila el componente raíz y, recursivamente, los componentes
`.flux` que importa. Todos comparten un registro (`registry`) indexado por
ruta, de modo que cada archivo se compila una sola vez y los componentes
recursivos funcionan.

API pública (ver docs/api.md): `compile_file`, `compile_source`,
`check_file`, `check_source`, `CompiledComponent` y `FORMAT_VERSION`. El
resto de este paquete es interno.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..diagnostics import Diagnostic, FluxError, SourceLocation
from .ast_nodes import SFC, EachBlock, Element, IfBlock, KeyBlock, Node
from .ir import IRComponent
from .lowering import ComponentInterface, lower
from .qml_generator import SourceMap, generate_qml, lookup
from .script_analysis import ScriptInfo, analyze_script
from .sfc_parser import parse_file, parse_sfc

# Versión del formato .flux que entiende este compilador. Cambia solo cuando
# un archivo válido deja de compilar o cambia de significado (ver docs/api.md).
FORMAT_VERSION = 1


@dataclass
class QmlDocument:
    """QML generado para el contenido de un slot (se muestra dentro de otro componente)."""

    file: str
    qml: str
    source_map: SourceMap
    source: str

    def flux_location(self, qml_line: int) -> SourceLocation | None:
        return lookup(self.source_map, qml_line)


@dataclass
class CompiledComponent:
    ir: IRComponent
    qml: str
    source_map: SourceMap
    # id de plantilla -> QML del contenido de slot escrito en este componente
    fragments: dict[str, QmlDocument] = field(default_factory=dict, repr=False, compare=False)
    # carpetas desde las que se resolvieron los imports (para compilar más tarde otros componentes)
    roots: list[Path] = field(default_factory=list, repr=False, compare=False)
    # ruta -> componente compilado; compartido por todos los de una misma compilación
    registry: dict[str, "CompiledComponent"] = field(default_factory=dict, repr=False, compare=False)
    # Objetos derivados que el runtime calcula una sola vez (código compilado, clases puente).
    cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def file(self) -> str:
        return self.ir.file

    @property
    def source(self) -> str:
        return self.ir.source

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
        """Archivos .flux (y .qml propios) que forman la aplicación, para observar cambios."""
        comps = [self, *self.registry.values()]
        return list(dict.fromkeys([self.file, *(c.file for c in comps), *(q for c in comps for q in c.ir.qml_files)]))

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
        fragments = {}
        for frag in ir.slot_fragments:
            frag_qml, frag_map = generate_qml(ir, frag.root)
            fragments[frag.template.id] = QmlDocument(ir.file, frag_qml, frag_map, ir.source)
        compiled = CompiledComponent(ir, qml, source_map, fragments, list(self.roots), registry=self.registry)
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
        sfc, info = self.load(path)
        roots = sfc.root_elements
        root = roots[0].tag if len(roots) == 1 and isinstance(roots[0], Element) else None
        return ComponentInterface(
            dict(info.props), dict(info.events), frozenset(_slot_names(sfc.template)),
            root_box=root in ("flex", "Column", "Row") and info.inherit_attrs, inherit_attrs=info.inherit_attrs,
        )  # fmt: skip

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
                for suffix in (".flux", ".qml"):
                    # from components import TodoItem  -> components/TodoItem.flux
                    candidate = folder / f"{name}{suffix}"
                    if candidate.is_file():
                        return candidate.resolve()
                    # from components.TodoItem import TodoItem  -> components/TodoItem.flux
                    if parts and folder.name == name:
                        candidate = folder.with_suffix(suffix)
                        if candidate.is_file():
                            return candidate.resolve()
            return None

        return resolve


def _slot_names(nodes: list[Node]) -> set[str]:
    """Nombres de los <Slot> de una plantilla ("default" para el que no tiene nombre)."""
    names: set[str] = set()
    for node in nodes:
        children: list[Node] = []
        if isinstance(node, Element):
            if node.tag == "Slot":
                attr = node.attribute("name")
                names.add(attr.value if attr is not None and isinstance(attr.value, str) else "default")
            children = node.children
        elif isinstance(node, IfBlock):
            children = [n for b in node.branches for n in b.children]
        elif isinstance(node, EachBlock):
            children = [*node.children, *(node.else_children or [])]
        elif isinstance(node, KeyBlock):
            children = node.children
        names |= _slot_names(children)
    return names


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


def check_source(source: str, file: str = "<memoria>", roots: list[Path] | None = None) -> list[Diagnostic]:
    """Errores y advertencias de un componente y de los que importa, sin ejecutar su script ni lanzar excepciones.

    Pensado para editores y herramientas: una lista vacía significa que compila sin avisos.
    """
    try:
        return compile_source(source, file, roots).all_warnings
    except FluxError as e:
        return list(e.diagnostics)


def check_file(path: str | Path, roots: list[Path] | None = None, as_window: bool = True) -> list[Diagnostic]:
    """Como `check_source`, para un archivo."""
    try:
        return compile_file(path, roots, as_window).all_warnings
    except FluxError as e:
        return list(e.diagnostics)


__all__ = [
    "FORMAT_VERSION",
    "check_file",
    "check_source",
    "CompileSession",
    "CompiledComponent",
    "ComponentInterface",
    "compile_file",
    "compile_source",
    "parse_file",
    "parse_sfc",
]
