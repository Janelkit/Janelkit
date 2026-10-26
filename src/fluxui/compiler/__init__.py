"""Compilador .flux: SFC -> AST -> IR -> QML + tablas para el runtime Python."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..diagnostics import Diagnostic, SourceLocation
from .ir import IRComponent
from .lowering import lower
from .qml_generator import SourceMap, generate_qml, lookup
from .sfc_parser import parse_file, parse_sfc


@dataclass
class CompiledComponent:
    ir: IRComponent
    qml: str
    source_map: SourceMap
    # Objetos derivados que el runtime calcula una sola vez (código compilado, clase puente).
    cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def file(self) -> str:
        return self.ir.file

    @property
    def warnings(self) -> list[Diagnostic]:
        return self.ir.warnings

    def flux_location(self, qml_line: int) -> SourceLocation | None:
        return lookup(self.source_map, qml_line)


def compile_source(source: str, file: str = "<memoria>") -> CompiledComponent:
    ir = lower(parse_sfc(source, file))
    qml, source_map = generate_qml(ir)
    return CompiledComponent(ir, qml, source_map)


def compile_file(path: str | Path) -> CompiledComponent:
    sfc = parse_file(path)
    ir = lower(sfc)
    qml, source_map = generate_qml(ir)
    return CompiledComponent(ir, qml, source_map)


__all__ = ["CompiledComponent", "compile_file", "compile_source", "parse_file", "parse_sfc"]
