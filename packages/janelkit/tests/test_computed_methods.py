"""@computed en un método de una clase: un computed por instancia, que vive lo que la instancia."""
import pytest

from janelkit import Computed, computed, effect, state
from janelkit.reactivity import Scope


class Carrito:
    calculos = 0

    def __init__(self, precios):
        self.items = state(list(precios))

    @computed
    def total(self):
        Carrito.calculos += 1
        return sum(self.items.value)


def test_each_instance_has_its_own_cached_computed():
    a, b = Carrito([1, 2]), Carrito([10])
    assert isinstance(a.total, Computed) and a.total is a.total and a.total is not b.total
    Carrito.calculos = 0
    assert (a.total.value, b.total.value, a.total.value) == (3, 10, 3)
    assert Carrito.calculos == 2  # en caché
    a.items.value.append(4)
    assert a.total.value == 7 and b.total.value == 10
    assert isinstance(Carrito.total, Computed)  # en la clase, el descriptor


def test_it_is_reactive_and_outlives_the_scope_that_read_it_first():
    c = Carrito([1])
    seen = []
    scope = Scope()
    with scope.active():
        effect(lambda: seen.append(c.total.value))  # se crea aquí, dentro de un ámbito
    scope.dispose()
    c.items.value.append(1)
    assert c.total.value == 2  # el computed sigue siguiendo sus fuentes
    other = []
    effect(lambda: other.append(c.total.value))
    c.items.value.append(1)
    assert other == [2, 3] and seen == [1]


def test_a_zero_argument_computed_in_a_class_stays_shared():
    n = state(1)

    class Servicio:
        doble = computed(lambda: n.value * 2)

    assert Servicio().doble is Servicio.doble and Servicio().doble.value == 2


def test_slots_classes_get_a_clear_error():
    class Fijo:
        __slots__ = ("x",)

        @computed
        def total(self):
            return 1

    with pytest.raises(TypeError, match="sin __slots__"):
        Fijo().total
