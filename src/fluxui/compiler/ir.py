"""Representación intermedia: árbol de elementos Qt más tablas de bindings y manejadores.

El IR no contiene sintaxis .flux ni objetos PySide6: el generador QML lo
convierte en texto y el runtime Python usa sus tablas para evaluar expresiones.
"""
from __future__ import annotations

import json

from dataclasses import dataclass, field
from typing import Union

from ..diagnostics import Diagnostic, SourceLocation
from .ast_nodes import Expression, ScriptBlock


@dataclass
class Literal:
    """Valor QML ya formateado (`"hola"`, `640`, `true`)."""

    qml: str


@dataclass
class Bound:
    """Valor que proviene de la propiedad `binding_id` del puente."""

    binding_id: str


PropValue = Union[Literal, Bound]


@dataclass
class ExprBinding:
    """El valor es el resultado de una expresión."""

    id: str
    expression: Expression
    loc: SourceLocation


@dataclass
class TextBinding:
    """Texto con interpolaciones: `Clicks: {count}`."""

    id: str
    parts: list[Union[str, Expression]]
    loc: SourceLocation


@dataclass
class Guard:
    """Rama de un `{#if}`: activa si `conditions[index]` es verdadera y las anteriores falsas.

    `index == len(conditions)` representa la rama `{:else}`.
    """

    conditions: list[Expression]
    index: int


@dataclass
class VisibilityBinding:
    """Visibilidad de un elemento dentro de uno o más `{#if}` anidados."""

    id: str
    guards: list[Guard]
    extra: Expression | None  # atributo `visible={...}` del propio elemento
    loc: SourceLocation


Binding = Union[ExprBinding, TextBinding, VisibilityBinding]


@dataclass
class Handler:
    id: str
    expression: Expression
    event: str
    loc: SourceLocation


@dataclass
class Write:
    """Escritura de `bind:` desde Qt hacia un `state` del script."""

    binding_id: str
    target: Expression  # nombre simple
    loc: SourceLocation


@dataclass
class IRElement:
    qml_type: str
    loc: SourceLocation
    props: dict[str, PropValue] = field(default_factory=dict)
    # manejador QML ("onClicked") -> sentencias JS que llaman al puente
    handlers: dict[str, list[str]] = field(default_factory=dict)
    children: list["IRElement"] = field(default_factory=list)


@dataclass
class IRComponent:
    file: str
    source: str
    root: IRElement
    script: ScriptBlock | None
    bindings: list[Binding] = field(default_factory=list)
    handlers: list[Handler] = field(default_factory=list)
    writes: list[Write] = field(default_factory=list)
    imports: tuple[str, ...] = ()
    warnings: list[Diagnostic] = field(default_factory=list)


def qml_string(text: str) -> str:
    """Literal de cadena QML (compatible con JSON), conservando caracteres no ASCII."""
    return json.dumps(text, ensure_ascii=False)
