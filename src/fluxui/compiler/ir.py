"""Representación intermedia: árbol de elementos Qt más tablas para el runtime.

El IR no contiene sintaxis .flux ni objetos PySide6: el generador QML lo
convierte en texto y el runtime Python usa sus tablas para evaluar expresiones.

Una *plantilla* (`IRTemplate`) agrupa los bindings, manejadores y regiones
dinámicas que pertenecen a un mismo ámbito: el componente completo o un
*fragmento* (el cuerpo de un `{#each}` o de una rama de `{#if}`). Cada
instancia de una plantilla tiene su propio puente `fx` en QML.

Las regiones dinámicas (`Slot`) se generan como un `Repeater` cuyo modelo es
una lista de puentes que el runtime Python inserta, mueve y elimina.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Union

from ..diagnostics import Diagnostic, SourceLocation
from .ast_nodes import Expression, ScriptBlock


@dataclass
class Literal:
    """Valor QML ya formateado (`"hola"`, `640`, `true`, `fxtheme.primary`)."""

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


Binding = Union[ExprBinding, TextBinding]


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
    children: list["IRNode"] = field(default_factory=list)
    # class:nombre={cond}: (propiedad QML, valor, condición QML) -> `Binding on ... { when }`
    conditional: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class IRRepeater:
    """Región dinámica en el árbol QML: `Repeater { model: fx.<model_id> }`.

    `delegate` es el elemento que se repite; None significa que el delegado es
    un componente hijo compilado aparte (`fx.<model_id>.delegate`).
    """

    model_id: str
    loc: SourceLocation
    delegate: IRElement | None = None


IRNode = Union[IRElement, IRRepeater]


@dataclass
class ConstArg:
    """Valor constante de una prop (`titulo="Hola"`, `max={10}`)."""

    value: Any


PropArg = Union[Expression, ConstArg]


@dataclass
class ComponentUse:
    """Uso de un componente hijo: `<TodoItem todo={t} on:removed={borrar} />`."""

    tag: str
    path: str  # clave del componente compilado en el registro
    props: dict[str, PropArg]
    events: dict[str, Handler]  # evento del hijo -> manejador en la plantilla actual
    loc: SourceLocation


@dataclass
class Fragment:
    """Contenido de un `{#each}` o de una rama `{#if}`."""

    template: "IRTemplate"
    root: IRElement | None = None  # delegado en línea
    component: ComponentUse | None = None  # o un único componente hijo

    @property
    def empty(self) -> bool:
        return self.root is None and self.component is None


@dataclass
class EachSlot:
    model_id: str
    iterable: Expression
    item: str
    index: str | None
    key: Expression | None
    fragment: Fragment
    loc: SourceLocation
    empty_model_id: str | None = None  # rama {:else} (lista vacía)
    empty_fragment: Fragment | None = None


@dataclass
class IfBranchSlot:
    model_id: str | None  # None si la rama está vacía
    condition: Expression | None  # None = {:else}
    fragment: Fragment


@dataclass
class IfSlot:
    branches: list[IfBranchSlot]
    loc: SourceLocation


@dataclass
class KeySlot:
    """`{#key expr}`: vuelve a crear el fragmento cuando cambia el valor de `expr`."""

    model_id: str
    expression: Expression
    fragment: Fragment
    loc: SourceLocation


@dataclass
class ComponentSlot:
    model_id: str
    use: ComponentUse
    loc: SourceLocation


Slot = Union[EachSlot, IfSlot, KeySlot, ComponentSlot]


@dataclass
class IRTemplate:
    id: str
    bindings: list[Binding] = field(default_factory=list)
    handlers: list[Handler] = field(default_factory=list)
    writes: list[Write] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)

    @property
    def model_ids(self) -> list[str]:
        ids: list[str] = []
        for slot in self.slots:
            if isinstance(slot, EachSlot):
                ids.append(slot.model_id)
                if slot.empty_model_id:
                    ids.append(slot.empty_model_id)
            elif isinstance(slot, IfSlot):
                ids.extend(b.model_id for b in slot.branches if b.model_id)
            else:  # KeySlot, ComponentSlot
                ids.append(slot.model_id)
        return ids


@dataclass
class TokenUse:
    """Referencia a un token de tema desde `<style>` (`var(--primary)`)."""

    name: str
    loc: SourceLocation


@dataclass
class IRComponent:
    file: str
    source: str
    root: IRElement
    template: IRTemplate
    script: ScriptBlock | None
    script_info: Any = None  # compiler.script_analysis.ScriptInfo
    is_window: bool = True
    imports: tuple[str, ...] = ()
    warnings: list[Diagnostic] = field(default_factory=list)
    tokens: list[TokenUse] = field(default_factory=list)
    component_paths: list[str] = field(default_factory=list)


def qml_string(text: str) -> str:
    """Literal de cadena QML (compatible con JSON), conservando caracteres no ASCII."""
    return json.dumps(text, ensure_ascii=False)
