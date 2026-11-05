"""Registro de escrituras (janelkit.ext.on_write) y dueño de los datos (janelkit.ext.own)."""
import pytest

from janelkit import state
from janelkit.ext import on_write, own


class Dueno:
    pass


@pytest.fixture
def writes():
    seen = []
    remove = on_write(lambda target, owner, before: seen.append((target, owner, before)))
    yield seen
    remove()


def test_state_assignments_and_in_place_changes_are_reported_before_they_happen(writes):
    n, items = state(1), state([1])
    snapshots = []
    remove = on_write(lambda target, owner, before: snapshots.append(list(target)) if target is items.peek() else None)
    n.value = 2
    items.value.append(2)
    remove()
    assert writes[0] == (n, None, 1)
    assert writes[1][0] is items.peek() and writes[1][1] is None
    assert snapshots == [[1]]  # se avisa antes: la lista aún no tiene el 2
    n.value = 2
    assert len(writes) == 2  # un valor igual no es una escritura


def test_the_owner_is_inherited_by_nested_inserted_and_assigned_values(writes):
    dueno = Dueno()
    tablero = state([{"tarjetas": [{"titulo": "a"}]}])
    own(tablero, dueno)
    tarjeta = tablero.value[0]["tarjetas"][0]
    tarjeta["titulo"] = "b"  # anidada desde antes
    tablero.value[0]["tarjetas"].append({"titulo": "c", "etiquetas": []})
    nueva = tablero.value[0]["tarjetas"][-1]
    nueva["etiquetas"].append("x")  # insertada después: también es suya
    tablero.value = [{"otra": []}]
    tablero.value[0]["otra"].append(1)  # asignada después: también
    assert [owner for _, owner, _ in writes] == [dueno] * 5
    suelto = state([])
    suelto.value.append(1)
    assert writes[-1][1] is None


def test_raising_in_the_callback_stops_the_write():
    items = state([1])

    def forbid(target, owner, before):
        raise PermissionError("no")

    remove = on_write(forbid)
    try:
        with pytest.raises(PermissionError):
            items.value.append(2)
        with pytest.raises(PermissionError):
            items.value = []
    finally:
        remove()
    assert items.value == [1]


def test_nothing_is_called_once_removed():
    seen = []
    remove = on_write(lambda *a: seen.append(a))
    remove()
    state(0).value = 1
    assert seen == []
