"""Nodos del AST de un archivo .flux. Todos conservan su ubicación de origen."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from ..diagnostics import SourceLocation


@dataclass
class Expression:
    """Expresión Python tal como aparece entre llaves."""

    code: str
    loc: SourceLocation


@dataclass
class Attribute:
    name: str
    # str = literal entre comillas, Expression = {expr}, True = atributo booleano sin valor
    value: Union[str, Expression, bool]
    loc: SourceLocation

    @property
    def directive(self) -> str | None:
        """Prefijo de directiva (`on`, `bind`) o None para atributos normales."""
        return self.name.split(":", 1)[0] if ":" in self.name else None

    @property
    def argument(self) -> str:
        return self.name.split(":", 1)[1] if ":" in self.name else self.name


@dataclass
class Element:
    tag: str
    attributes: list[Attribute]
    children: list["Node"]
    loc: SourceLocation

    def attribute(self, name: str) -> Attribute | None:
        return next((a for a in self.attributes if a.name == name), None)


@dataclass
class Text:
    value: str
    loc: SourceLocation


@dataclass
class Interpolation:
    expression: Expression
    loc: SourceLocation


@dataclass
class IfBranch:
    condition: Expression | None  # None = {:else}
    children: list["Node"]
    loc: SourceLocation


@dataclass
class IfBlock:
    branches: list[IfBranch]
    loc: SourceLocation


@dataclass
class EachBlock:
    iterable: Expression
    item: str
    index: str | None
    key: Expression | None
    children: list["Node"]
    loc: SourceLocation
    else_children: list["Node"] | None = None  # {:else}: se muestra si la lista está vacía


@dataclass
class KeyBlock:
    """`{#key expr}...{/key}`: recrea el contenido cuando cambia `expr`."""

    expression: Expression
    children: list["Node"]
    loc: SourceLocation


Node = Union[Element, Text, Interpolation, IfBlock, EachBlock, KeyBlock]


@dataclass
class ScriptBlock:
    content: str
    lang: str
    loc: SourceLocation  # ubicación del primer carácter del contenido


@dataclass
class StyleBlock:
    content: str
    loc: SourceLocation


@dataclass
class SFC:
    file: str
    source: str
    script: ScriptBlock | None
    style: StyleBlock | None
    template: list[Node] = field(default_factory=list)

    @property
    def root_elements(self) -> list[Element]:
        return [n for n in self.template if not (isinstance(n, Text) and not n.value.strip())]


def dump(sfc: SFC) -> str:
    """Representación legible del AST (usada por `flux parse`)."""
    out: list[str] = [f"SFC {sfc.file}"]
    if sfc.script:
        n = len(sfc.script.content.strip().splitlines())
        out.append(f"  Script lang={sfc.script.lang} @{_lc(sfc.script.loc)} ({n} líneas)")
    if sfc.style:
        n = len(sfc.style.content.strip().splitlines())
        out.append(f"  Style @{_lc(sfc.style.loc)} ({n} líneas)")
    out.append("  Template")
    for node in sfc.template:
        _dump_node(node, 2, out)
    return "\n".join(out)


def _lc(loc: SourceLocation) -> str:
    return f"{loc.line}:{loc.column}"


def _dump_node(node: Node, depth: int, out: list[str]) -> None:
    pad = "  " * depth
    if isinstance(node, Element):
        attrs = " ".join(_fmt_attr(a) for a in node.attributes)
        out.append(f"{pad}<{node.tag}{' ' + attrs if attrs else ''}> @{_lc(node.loc)}")
        for child in node.children:
            _dump_node(child, depth + 1, out)
    elif isinstance(node, Text):
        if node.value.strip():
            out.append(f"{pad}Text {node.value.strip()!r} @{_lc(node.loc)}")
    elif isinstance(node, Interpolation):
        out.append(f"{pad}{{{node.expression.code.strip()}}} @{_lc(node.loc)}")
    elif isinstance(node, IfBlock):
        for i, branch in enumerate(node.branches):
            if i == 0:
                label = f"#if {branch.condition.code.strip()}"
            elif branch.condition:
                label = f":else if {branch.condition.code.strip()}"
            else:
                label = ":else"
            out.append(f"{pad}{{{label}}} @{_lc(branch.loc)}")
            for child in branch.children:
                _dump_node(child, depth + 1, out)
    elif isinstance(node, KeyBlock):
        out.append(f"{pad}{{#key {node.expression.code.strip()}}} @{_lc(node.loc)}")
        for child in node.children:
            _dump_node(child, depth + 1, out)
    elif isinstance(node, EachBlock):
        key = f" ({node.key.code.strip()})" if node.key else ""
        idx = f", {node.index}" if node.index else ""
        out.append(f"{pad}{{#each {node.iterable.code.strip()} as {node.item}{idx}{key}}} @{_lc(node.loc)}")
        for child in node.children:
            _dump_node(child, depth + 1, out)
        if node.else_children is not None:
            out.append(f"{pad}{{:else}}")
            for child in node.else_children:
                _dump_node(child, depth + 1, out)


def _fmt_attr(attr: Attribute) -> str:
    if attr.value is True:
        return attr.name
    if isinstance(attr.value, Expression):
        return f"{attr.name}={{{attr.value.code.strip()}}}"
    return f'{attr.name}="{attr.value}"'
