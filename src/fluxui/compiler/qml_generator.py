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
        lines.append(f"{inner}readonly property bool fxSkip: true")  # no ocupa sitio en <flex>
        # Al reordenar filas, Qt solo cambia el orden de apilado (sin señal para <flex>): el
        # modelo avisa una vez por movimiento. Antes lo hacía el índice de cada fila, y
        # mover una fila recalculaba el de todas las de detrás (invertir 1000: ~380 ms).
        lines.append(f"{inner}readonly property bool fxTouchOrder: Fx.resized(parent, model ? model.order : 0)")
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
    # Un solo Binding por propiedad: con varios, al cambiar dos a la vez, el valor que
    # se restaura depende del orden en que Qt los procese. Gana la última condición activa.
    styled: dict[str, list[tuple[str, str]]] = {}
    for prop, value, when in el.conditional:
        if when == "true":  # bind: (se reafirma tras cada edición del usuario)
            lines.append(f"{inner}Binding on {prop} {{ when: true; value: {value} }}")
        else:
            styled.setdefault(prop, []).append((value, when))
    for prop, entries in styled.items():
        value = entries[0][0]
        for v, w in entries[1:]:
            value = f"{_paren(w)} ? {v} : {_paren(value)}"
        when = " || ".join(_paren(w) for _, w in entries) if len(entries) > 1 else entries[0][1]
        lines.append(f"{inner}Binding on {prop} {{ when: {when}; value: {value} }}")
    for handler, statements in el.handlers.items():
        params = el.handler_params.get(handler)
        if params is not None:  # parámetros declarados: Qt ya no los inyecta en el manejador
            lines.append(f"{inner}{handler}: function({', '.join(params)}) {{ {'; '.join(statements)} }}")
            continue
        body = statements[0] if len(statements) == 1 else "{ " + "; ".join(statements) + " }"
        lines.append(f"{inner}{handler}: {body}")
    if el.delegate is not None:
        _emit(el.delegate, depth + 1, lines, source_map, prefix="delegate: ")
    for child in el.children:
        _emit(child, depth + 1, lines, source_map)
    lines.append(f"{pad}}}")


def _paren(expr: str) -> str:
    return f"({expr})" if " " in expr else expr


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
