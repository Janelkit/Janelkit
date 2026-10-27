"""Elementos propios escritos en QML: `from widgets.Gauge import Gauge` importa `widgets/Gauge.qml`.

Es la salida para lo que FluxUI no ofrece todavía. El compilador lee la
interfaz del objeto raíz del archivo (sin ejecutarlo) para validar su uso:

    // widgets/Gauge.qml
    import QtQuick
    Item {
        property real value: 0          // prop: value={...}  y  bind:value={...}
        readonly property bool full: …  // solo lectura: no se puede pasar ni enlazar
        signal picked(real v)           // evento: on:picked={...} (recibe v)
    }

Además se admiten las props comunes (`width`, `height`, `flex`, `visible`,
`enabled`, `opacity`), `id`, `class` y `ref`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..diagnostics import Diagnostic, FluxError
from ..qt_backend.controls import ControlSpec, EventSpec, PropSpec, TwoWaySpec

_TYPES = {
    "string": "string", "url": "string", "int": "number", "real": "number", "double": "number",
    "number": "number", "bool": "bool", "color": "color",
}  # fmt: skip
_PROPERTY = re.compile(
    r"^\s*(?P<mods>(?:(?:default|required|readonly|final|virtual|override)\s+)*)property\s+"
    r"(?P<type>list\s*<\s*[\w.]+\s*>|[\w.]+)\s+(?P<name>[A-Za-z_]\w*)"
)
_SIGNAL = re.compile(r"^\s*signal\s+(?P<name>[A-Za-z_]\w*)\s*(?:\((?P<params>[^)]*)\))?")


@dataclass(frozen=True)
class QmlImport:
    """Un archivo .qml importado: alias de su carpeta en el QML generado y nombre del tipo."""

    alias: str
    directory: Path
    type_name: str

    @property
    def import_line(self) -> str:
        return f'"{self.directory.as_uri()}" as {self.alias}'


def _strip(text: str) -> str:
    """Quita comentarios y el contenido de las cadenas (conservando los saltos de línea)."""

    def blank(m: re.Match) -> str:
        s = m.group(0)
        if s.startswith("/"):
            return "\n" * s.count("\n")
        return s[0] + "\n" * s.count("\n") + s[0]

    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`', blank, text, flags=re.S)


def _params(text: str | None) -> tuple[str, ...]:
    if not text or not text.strip():
        return ()
    names = []
    for part in text.split(","):
        part = part.strip()
        if ":" in part:  # sintaxis moderna: signal x(valor: real)
            names.append(part.split(":", 1)[0].strip())
        else:  # signal x(real valor)
            names.append(part.split()[-1])
    return tuple(names)


def _root_members(text: str) -> list[str]:
    """Sentencias escritas directamente dentro del objeto raíz (separadas por saltos de línea o `;`)."""
    members: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "{":
            depth += 1
            if depth == 2:  # empieza un objeto o bloque hijo: lo anterior era una sentencia
                members.append("".join(current))
                current = []
            continue
        if ch == "}":
            depth -= 1
            continue
        if depth != 1:
            continue
        if ch in "\n;":
            members.append("".join(current))
            current = []
        else:
            current.append(ch)
    members.append("".join(current))
    return [m for m in members if m.strip()]


def read_interface(path: Path, tag: str, alias: str) -> ControlSpec:
    """Interfaz (props, eventos, enlaces) del objeto raíz de un archivo QML."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FluxError(Diagnostic(f"no se pudo leer {path}: {exc}")) from None
    props: dict[str, PropSpec] = {}
    events: dict[str, EventSpec] = {}
    two_way: dict[str, TwoWaySpec] = {}
    for statement in _root_members(_strip(text)):
        m = _PROPERTY.match(statement)
        if m:
            name = m.group("name")
            type_ = re.sub(r"\s+", "", m.group("type"))
            cap = name[0].upper() + name[1:]
            if "readonly" not in m.group("mods").split():
                props[name] = PropSpec(name, _TYPES.get(type_, "any"))
                two_way[name] = TwoWaySpec(name, f"on{cap}Changed")
        m = _SIGNAL.match(statement)
        if m:
            name = m.group("name")
            events[name] = EventSpec(f"on{name[0].upper()}{name[1:]}", _params(m.group("params")))
    return ControlSpec(f"{alias}.{tag}", props=props, events=events, two_way=two_way, tag=tag)

