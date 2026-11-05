"""Stores sin Qt: instancias sueltas (Carrito()), como se prueban en una aplicación."""
import asyncio

import pytest

from janelkit import computed, effect
from janelkit_store import Mutation, StoreError, field, reset, snapshot, store, subscribe, use


@store
class Libre:
    items: list = []
    n: int = 0

    def poner(self, x):
        self.items.append(x)
        self.n += 1


@store(strict=True)
class Carrito:
    items: list[dict] = []
    nota: str = field("", bind=True)
    _cache: dict = {}

    @computed
    def total(self) -> float:
        return sum(i["precio"] for i in self.items)

    def setup(self):
        self._cache["listo"] = True

    def agregar(self, item):
        self.items.append(item)

    def editar(self, i, **campos):
        self.items[i].update(campos)

    def dos(self, a, b):
        self.agregar(a)  # una acción dentro de otra se suma a ella
        self.agregar(b)

    async def cargar(self, items):
        await asyncio.sleep(0)
        self.items = items  # tras el await sigue siendo «cargar»
        await asyncio.sleep(0)
        self.agregar({"precio": 1})


def test_fields_are_reactive_attributes_without_value_and_each_instance_has_its_own():
    a, b = Libre(), Libre(n=5)
    assert (a.items, a.n, b.n) == ([], 0, 5) and a.items is not b.items
    seen = []
    effect(lambda: seen.append(a.n))
    a.poner("x")
    a.n = 10  # no estricto: se puede escribir desde fuera
    assert seen == [0, 1, 10] and a.items == ["x"]
    with pytest.raises(TypeError, match="no tiene los campos"):
        Libre(otro=1)


def test_an_action_is_one_batch_and_one_mutation():
    c = Carrito()
    seen, log = [], []
    effect(lambda: seen.append((len(c.items), c.total)))
    subscribe(c, log.append)
    c.dos({"precio": 2}, {"precio": 3})
    assert seen == [(0, 0), (2, 5)]  # un solo recálculo
    assert len(log) == 1 and isinstance(log[0], Mutation)
    m = log[0]
    assert (m.store, m.key, m.action) == ("Carrito", None, "dos") and m.instance is c
    assert [(ch.field, ch.kind, ch.old, ch.new) for ch in m.changes] == [
        ("items", "mutate", [], [{"precio": 2}, {"precio": 3}])
    ]
    assert str(m) == "Carrito.dos: items"


def test_nested_data_belongs_to_its_field():
    c = Carrito()
    c.agregar({"precio": 2, "etiquetas": []})
    log = []
    subscribe(c, log.append)
    c.editar(0, precio=4)
    assert c.total == 4 and log[-1].action == "editar" and log[-1].changes[0].field == "items"


def test_strict_stores_only_write_inside_their_methods():
    c = Carrito()
    c.agregar({"precio": 1})
    with pytest.raises(StoreError, match="solo se escribe dentro de sus métodos"):
        c.items.append({"precio": 9})
    with pytest.raises(StoreError, match="solo se escribe dentro de sus métodos"):
        c.items[0]["precio"] = 9  # también lo anidado
    with pytest.raises(StoreError):
        c.nota = "hola"
    assert c.items == [{"precio": 1}]
    with pytest.raises(AttributeError, match="es un valor derivado"):
        c.total = 3


def test_bind_respects_the_bind_option_in_strict_stores():
    c = Carrito()
    log = []
    subscribe(c, log.append)
    type(c).nota.__jk_bind__(c, "sin prisa")  # lo que hace bind:value={carrito.nota}
    assert c.nota == "sin prisa" and log[-1].action == "bind:nota"
    with pytest.raises(StoreError, match="no admite bind:"):
        type(c).items.__jk_bind__(c, [])


def test_private_fields_setup_snapshot_and_reset():
    c = Carrito()
    assert c._cache == {"listo": True}  # setup() se ejecuta al crearse
    c.agregar({"precio": 1})
    assert snapshot(c) == {"items": [{"precio": 1}], "nota": ""}  # sin lo interno
    reset(c)
    assert snapshot(c) == {"items": [], "nota": ""}


def test_async_actions_keep_their_name_after_await():
    c = Carrito()
    log = []
    subscribe(c, log.append)
    loop = asyncio.new_event_loop()  # no asyncio.run: dejaría el hilo sin bucle para las demás pruebas
    try:
        loop.run_until_complete(c.cargar([{"precio": 2}]))
    finally:
        loop.close()
    assert c.total == 3
    assert [m.action for m in log] == ["cargar"] and log[0].changes[0].kind == "set"


def test_use_needs_a_running_application():
    with pytest.raises(StoreError, match="necesita una aplicación en marcha"):
        use(Carrito)


def test_declaration_errors_are_explained():
    with pytest.raises(StoreError, match="no define __init__"):
        @store
        class Mal:
            def __init__(self):
                pass

    with pytest.raises(TypeError, match="no es un store"):
        use(dict)
