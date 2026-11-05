"""El script de un .janel se ejecuta en un módulo registrado en `sys.modules`.

Así funcionan `dataclass` (con anotaciones en texto), `typing.get_type_hints` y `pickle`,
que buscan el módulo de una clase por su nombre.
"""
import pickle
import sys

from janelkit.testing import texts

DATACLASS_APP = """<script>
from __future__ import annotations
from dataclasses import dataclass
import typing

@dataclass
class Point:
    x: int = 0
    y: int = 0

hints = typing.get_type_hints(Point)
</script>
<column><text>{Point(3).x}</text></column>
"""


def test_dataclass_with_string_annotations_works(mount):
    m = mount(DATACLASS_APP)
    ns = m.instance.namespace
    assert "3" in texts(m)
    assert ns["hints"] == {"x": int, "y": int}
    point = ns["Point"](1, 2)
    assert pickle.loads(pickle.dumps(point)) == point


def test_each_instance_has_its_own_module_released_on_unmount(mount, janel_app):
    first = mount(DATACLASS_APP)
    second = mount(DATACLASS_APP)
    a, b = first.instance.namespace["__name__"], second.instance.namespace["__name__"]
    assert a != b and a.startswith("janelkit.components.App")
    assert sys.modules[a].__dict__ is first.instance.namespace
    janel_app.unmount(first)
    assert a not in sys.modules and b in sys.modules
