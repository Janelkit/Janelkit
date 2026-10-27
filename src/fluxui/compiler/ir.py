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
    classes: bool = False  # class={expr}: el runtime lo convierte en " a b " (nombres de clase)


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
    inline: bool = False  # llamada o sentencias que se ejecutan al ocurrir el evento


@dataclass
class RefUse:
    """`ref={nombre}`: el elemento se asigna al `Ref` del script cuando existe."""

    id: str
    name: str
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
    handler_params: dict[str, tuple[str, ...]] = field(default_factory=dict)  # parámetros de la señal
    children: list["IRNode"] = field(default_factory=list)
    # class:nombre={cond}: (propiedad QML, valor, condición QML) -> `Binding on ... { when }`
    conditional: list[tuple[str, str, str]] = field(default_factory=list)
    delegate: "IRElement | None" = None  # <List>: la fila que repite su ListView
    behaviors: dict[str, str] = field(default_factory=dict)  # propiedad QML -> animación (transition en CSS)
    # transition:/in:/out: -> {"in": (tipo, ms), "out": (tipo, ms)}
    transitions: dict[str, tuple[str, int]] = field(default_factory=dict)
    component: str | None = None  # FxRemote: ruta del componente cuya raíz recibe los atributos


@dataclass
class IRRepeater:
    """Región dinámica en el árbol QML: `Repeater { model: fx.<model_id> }`.

    `delegate` es el elemento que se repite; None significa que el delegado es
    un componente hijo compilado aparte (`fx.<model_id>.delegate`).
    """

    model_id: str
    loc: SourceLocation
    delegate: IRElement | None = None
    # Para elegir el layout de la caja que lo contiene (layout_choice.py):
    component: str | None = None  # el delegado es la raíz de este componente
    many: bool = False  # {#each}: puede repetir el delegado
    opaque: bool = False  # contenido de un <Slot />: no se sabe qué es


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
    slots: dict[str, "Fragment"] = field(default_factory=dict)  # contenido entre etiquetas, por nombre de slot
    ordinal: int = 0  # cuántos usos de esta etiqueta hay antes en la plantilla (identidad estable para flux dev)


@dataclass
class Fragment:
    """Contenido de un `{#each}` o de una rama `{#if}`."""

    template: "IRTemplate"
    root: IRElement | None = None  # delegado en línea
    component: ComponentUse | None = None  # o un único componente hijo
    leave_ms: int = 0  # out:/transition: en la raíz: Python retira la fila al terminar la animación

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
    lazy: bool = False  # dentro de <List>: cada fila se crea cuando Qt la pide (al hacerse visible)
    animated: bool = False  # <List animate>: al quitar una fila, su vista se anima antes de liberarla


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


@dataclass
class SlotOutlet:
    """`<Slot name="x">reserva</Slot>` en un componente hijo: aquí va el contenido que pasa el padre."""

    name: str  # "default" para <Slot />
    model_id: str  # contenido del padre (delegado definido por el padre)
    fallback: Fragment | None  # contenido de reserva si el padre no pasa nada
    loc: SourceLocation
    fallback_model_id: str | None = None


Slot = Union[EachSlot, IfSlot, KeySlot, ComponentSlot, SlotOutlet]


@dataclass
class IRTemplate:
    id: str
    bindings: list[Binding] = field(default_factory=list)
    handlers: list[Handler] = field(default_factory=list)
    writes: list[Write] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)
    refs: list[RefUse] = field(default_factory=list)

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
            elif isinstance(slot, SlotOutlet):
                ids.append(slot.model_id)
                if slot.fallback_model_id:
                    ids.append(slot.fallback_model_id)
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
    # Componentes hijos que van dentro de una caja con el motor de <flex> (layout_choice.py).
    engine_children: list[str] = field(default_factory=list)
    # Contenido de slots escrito aquí con elementos propios: cada uno se genera
    # como un documento QML aparte, porque se muestra dentro de otro componente.
    slot_fragments: list[Fragment] = field(default_factory=list)
    qml_files: list[str] = field(default_factory=list)  # elementos propios importados de archivos .qml
    class_names: list[str] = field(default_factory=list)  # clases con reglas en <style> (para class={expr})


def qml_string(text: str) -> str:
    """Literal de cadena QML (compatible con JSON), conservando caracteres no ASCII."""
    return json.dumps(text, ensure_ascii=False)
