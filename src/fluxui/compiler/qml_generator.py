"""IR -> texto QML, con un mapa de origen línea QML -> ubicación .flux."""
from __future__ import annotations

from pathlib import Path

from ..diagnostics import SourceLocation
from .ir import Bound, IRComponent, IRElement, Literal

BRIDGE_NAME = "fx"  # propiedad de contexto con el puente de cada instancia

SourceMap = list[tuple[int, SourceLocation]]


def generate_qml(component: IRComponent) -> tuple[str, SourceMap]:
    lines: list[str] = [
        f"// Generado por FluxUI desde {Path(component.file).name}. No editar: se regenera al compilar.",
        *(f"import {module}" for module in component.imports),
        "",
    ]
    source_map: SourceMap = []
    _emit(component.root, 0, lines, source_map)
    return "\n".join(lines) + "\n", source_map


def _emit(el: IRElement, depth: int, lines: list[str], source_map: SourceMap) -> None:
    pad = "    " * depth
    inner = "    " * (depth + 1)
    source_map.append((len(lines) + 1, el.loc))
    lines.append(f"{pad}{el.qml_type} {{")
    for prop, value in el.props.items():
        lines.append(f"{inner}{prop}: {_value(value)}")
    for handler, statements in el.handlers.items():
        body = statements[0] if len(statements) == 1 else "{ " + "; ".join(statements) + " }"
        lines.append(f"{inner}{handler}: {body}")
    for child in el.children:
        _emit(child, depth + 1, lines, source_map)
    lines.append(f"{pad}}}")


def _value(value: Literal | Bound) -> str:
    if isinstance(value, Bound):
        return f"{BRIDGE_NAME}.{value.binding_id}"
    return value.qml


def lookup(source_map: SourceMap, qml_line: int) -> SourceLocation | None:
    """Ubicación .flux del elemento que contiene la línea QML indicada."""
    best: SourceLocation | None = None
    for line, loc in source_map:
        if line > qml_line:
            break
        best = loc
    return best
