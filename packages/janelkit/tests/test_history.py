"""Deshacer y rehacer: `History`."""
from __future__ import annotations

from janelkit import History, batch, computed, effect, state


def test_a_step_undoes_and_redoes_states_and_collections():
    h = History()
    titulo = state("a")
    origen, destino = state([1, 2, 3]), state([])
    with h.step("mover"):
        titulo.value = "b"
        destino.value.insert(0, origen.value.pop(0))
        titulo.value = "c"  # solo cuentan el valor de antes y el de después
    assert (titulo.value, origen.value, destino.value) == ("c", [2, 3], [1])
    assert h.undo() == "mover"
    assert (titulo.value, origen.value, destino.value) == ("a", [1, 2, 3], [])
    assert h.redo() == "mover"
    assert (titulo.value, origen.value, destino.value) == ("c", [2, 3], [1])


def test_undo_keeps_the_same_objects():
    """Las filas de `{#each}` con clave dependen de que los objetos sean los mismos."""
    h = History()
    tarjeta = {"titulo": "x"}
    cols = state({"a": [tarjeta], "b": []})
    t = cols.value["a"][0]
    with h.step("mover"):
        cols.value["b"].append(cols.value["a"].pop())
    with h.step("editar"):
        t["titulo"] = "y"
    h.undo()
    h.undo()
    assert cols.value["a"][0] is t and t["titulo"] == "x"


def test_dicts_and_sets_and_nested_collections():
    h = History()
    d = state({"x": 1, "lista": [1]})
    s = state({1, 2})
    with h.step("todo"):
        d.value["x"] = 2
        del d.value["lista"][0]
        d.value["nuevo"] = True
        s.value.discard(1)
        s.value.add(3)
    h.undo()
    assert d.value == {"x": 1, "lista": [1]} and s.value == {1, 2}
    h.redo()
    assert d.value == {"x": 2, "lista": [], "nuevo": True} and s.value == {2, 3}


def test_steps_without_changes_are_not_recorded_and_nested_steps_join():
    h = History()
    n = state(1)
    with h.step("nada"):
        n.value = 2
        n.value = 1
    assert not h.can_undo
    with h.step("fuera"):
        n.value = 5
        with h.step("dentro"):
            n.value = 6
    assert h.undo_label == "fuera"
    h.undo()
    assert n.value == 1 and not h.can_undo


def test_changes_outside_a_step_are_not_recorded():
    h = History()
    n = state(0)
    n.value = 1
    assert not h.can_undo
    with h.step("x"):
        n.value = 2
    h.undo()
    assert n.value == 1


def test_a_new_step_clears_redo_and_the_limit_drops_the_oldest():
    h = History(limit=2)
    n = state(0)
    for i in range(1, 4):
        with h.step(f"poner {i}"):
            n.value = i
    h.undo()
    assert h.redo_label == "poner 3"
    with h.step("otro"):
        n.value = 9
    assert not h.can_redo
    assert h.undo() == "otro" and h.undo() == "poner 2" and h.undo() is None
    assert n.value == 1


def test_custom_steps_for_what_is_not_reactive():
    h = History()
    datos = {}  # un dict normal: el historial no lo ve
    version = state(0)

    def poner(v):
        datos["k"] = v
        version.value += 1

    poner(1)
    h.add("poner 1", undo=lambda: datos.pop("k"), redo=lambda: poner(1))
    h.undo()
    assert datos == {}
    h.redo()
    assert datos == {"k": 1}
    with h.step("mixto"):
        version.value = 100
        h.add("ignorado", undo=lambda: datos.clear(), redo=lambda: datos.update(k=2))
    h.undo()
    assert datos == {} and version.value == 2


def test_undo_inside_a_replay_does_not_record():
    """Lo que hacen las funciones de deshacer, aunque abran pasos, no se anota."""
    h = History()
    n = state(0)

    def poner(v):
        with h.step("poner"):
            n.value = v

    poner(1)
    h.add("propio", undo=lambda: poner(0), redo=lambda: poner(1))
    assert h.undo() == "propio" and n.value == 0
    assert h.undo() == "poner" and n.value == 0
    assert h.redo() == "poner" and h.redo() == "propio" and not h.can_redo


def test_undo_runs_effects_once():
    h = History()
    a, b = state(1), state([1])
    veces = []
    effect(lambda: veces.append((a.value, len(b.value))))
    with h.step("x"):
        a.value = 2
        b.value.append(2)
    assert veces == [(1, 1), (2, 2)]
    h.undo()
    assert veces[-1] == (1, 1) and len(veces) == 3


def test_reactive_queries_and_modified():
    h = History()
    n = state(0)
    vistas = []

    @computed
    def boton():
        return (h.can_undo, h.undo_label, h.can_redo, h.modified)

    effect(lambda: vistas.append(boton.value))
    assert vistas[-1] == (False, "", False, False)
    with h.step("subir"):
        n.value = 1
    assert vistas[-1] == (True, "subir", False, True)
    h.mark_saved()
    assert vistas[-1] == (True, "subir", False, False)
    h.undo()
    assert vistas[-1] == (False, "", True, True)
    h.redo()
    assert h.modified is False
    with batch():
        h.clear()
    assert not h.can_undo and h.modified is False
    with h.step("otra"):
        n.value = 2
    assert h.modified is True
    h.undo()
    assert h.modified is False  # vuelve a lo guardado, aunque el paso que lo dejó así ya no esté


def test_an_exception_inside_a_step_records_what_changed():
    h = History()
    n = state(0)
    try:
        with h.step("a medias"):
            n.value = 1
            raise ValueError
    except ValueError:
        pass
    assert h.undo() == "a medias" and n.value == 0
