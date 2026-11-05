"""janelkit.ext.Gate (0.2): la compuerta de visibilidad que usan los anfitriones de los paquetes.

`visible` es reactivo y tiene en cuenta las compuertas de fuera (`parent`). Que lo que muestra
un componente espere con la compuerta cerrada se prueba en test_hidden_gate.py y en
test_ext_hosts_qt.py (la `.visibility` de cada hijo montado).
"""
from janelkit import computed, effect
from janelkit.ext import Gate


def test_visible_is_reactive_and_follows_the_outer_gates():
    outer, inner = Gate(), Gate()
    inner.parent = outer
    visible = computed(lambda: inner.visible)
    seen = []
    effect(lambda: seen.append(visible.value))
    assert seen == [True]
    outer.set_open(False)
    assert seen == [True, False] and not inner.closed  # cerrada por fuera
    inner.set_open(False)
    outer.set_open(True)
    assert seen == [True, False]  # sigue cerrada ella
    inner.set_open(True)
    assert seen == [True, False, True]


def test_a_gate_can_start_inside_another():
    outer = Gate()
    outer.set_open(False)
    assert Gate(parent=outer).visible is False


def test_changing_the_parent_updates_visible():
    closed = Gate()
    closed.set_open(False)
    gate = Gate()
    visible = computed(lambda: gate.visible)
    assert visible.value is True
    gate.parent = closed
    assert visible.value is False
    gate.parent = None
    assert visible.value is True


def test_opening_or_closing_twice_changes_nothing():
    gate = Gate()
    changes = []
    effect(lambda: changes.append(gate.visible))
    gate.set_open(True)
    gate.set_open(False)
    gate.set_open(False)
    gate.set_open(True)
    gate.set_open(True)
    assert changes == [True, False, True]
