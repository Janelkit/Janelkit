"""IR -> texto QML, con un mapa de origen línea QML -> ubicación .flux."""
from __future__ import annotations

from pathlib import Path

from ..diagnostics import SourceLocation
from .ir import Bound, IRComponent, IRElement, IRNode, IRRepeater, Literal

BRIDGE_NAME = "fx"  # puente de la instancia (propiedad de contexto o rol del modelo)

SourceMap = list[tuple[int, SourceLocation]]


def generate_qml(component: IRComponent, root: IRElement | None = None) -> tuple[str, SourceMap]:
    """QML del componente, o de `root` (contenido de un slot) como documento independiente."""
    what = "" if root is None else " (contenido de un slot)"
    lines: list[str] = [
        f"// Generado por FluxUI desde {Path(component.file).name}{what}. No editar: se regenera al compilar.",
        *(f"import {module}" for module in component.imports),
        "",
    ]
    source_map: SourceMap = []
    _emit(component.root if root is None else root, 0, lines, source_map)
    return "\n".join(lines) + "\n", source_map


def _emit(node: IRNode, depth: int, lines: list[str], source_map: SourceMap, prefix: str = "") -> None:
    pad = "    " * depth
    inner = "    " * (depth + 1)
    source_map.append((len(lines) + 1, node.loc))
    if isinstance(node, IRRepeater):
        lines.append(f"{pad}{prefix}Repeater {{")
        lines.append(f"{inner}model: {BRIDGE_NAME}.{node.model_id}")
        if node.delegate is None:
            lines.append(f"{inner}delegate: {BRIDGE_NAME}.{node.model_id}.delegate")
        else:
            # Dentro del delegado, `fx` es el rol del modelo: el puente de esa fila.
            _emit(node.delegate, depth + 1, lines, source_map, prefix="delegate: ")
        lines.append(f"{pad}}}")
        return
    el: IRElement = node
    lines.append(f"{pad}{prefix}{el.qml_type} {{")
    for prop, value in el.props.items():
        lines.append(f"{inner}{prop}: {_value(value)}")
    for prop, animation in el.behaviors.items():
        lines.append(f"{inner}Behavior on {prop} {{ {animation} }}")
    for prop, value, when in el.conditional:
        lines.append(f"{inner}Binding on {prop} {{ when: {when}; value: {value} }}")
    for handler, statements in el.handlers.items():
        body = statements[0] if len(statements) == 1 else "{ " + "; ".join(statements) + " }"
        lines.append(f"{inner}{handler}: {body}")
    if el.delegate is not None:
        _emit(el.delegate, depth + 1, lines, source_map, prefix="delegate: ")
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
