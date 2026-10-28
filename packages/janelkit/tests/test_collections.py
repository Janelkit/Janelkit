"""Colecciones reactivas: mutar en el sitio una lista, diccionario o conjunto de un state notifica."""
import copy
import json
import pickle

from janelkit import computed, state
from janelkit.reactivity import Effect
from janelkit.reactivity.collections import ReactiveDict, ReactiveList, ReactiveSet, to_plain


def runs(fn):
    """Cuenta cuántas veces se ejecuta un efecto que llama a `fn`."""
    seen = []
    Effect(lambda: seen.append(fn()))
    return seen


def test_state_converts_collections_deeply():
    s = state([{"id": 1, "tags": ["a"], "seen": {1}}])
    assert type(s.value) is ReactiveList
    assert type(s.value[0]) is ReactiveDict
    assert type(s.value[0]["tags"]) is ReactiveList
    assert type(s.value[0]["seen"]) is ReactiveSet
    assert s.value == [{"id": 1, "tags": ["a"], "seen": {1}}]
    assert isinstance(s.value, list) and isinstance(s.value[0], dict)


def test_list_mutations_notify():
    s = state([1, 2])
    seen = runs(lambda: list(s.value))
    s.value.append(3)
    s.value.extend([4])
    s.value.insert(0, 0)
    s.value.remove(4)
    s.value.pop()
    s.value[0] = 10
    del s.value[0]
    s.value += [5]
    s.value.reverse()
    s.value.sort()
    s.value.clear()
    assert seen == [
        [1, 2], [1, 2, 3], [1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3], [0, 1, 2],
        [10, 1, 2], [1, 2], [1, 2, 5], [5, 2, 1], [1, 2, 5], [],
    ]  # fmt: skip


def test_setting_an_equal_item_does_not_notify():
    s = state([1, 2])
    seen = runs(lambda: list(s.value))
    s.value[0] = 1
    assert len(seen) == 1


def test_dict_mutations_notify():
    s = state({"a": 1})
    seen = runs(lambda: dict(s.value.items()))
    s.value["b"] = 2
    s.value["b"] = 2  # igual: sin aviso
    s.value.update(c=3)
    s.value.setdefault("d", 4)
    s.value.pop("a")
    del s.value["b"]
    s.value |= {"e": 5}
    s.value.clear()
    assert seen == [
        {"a": 1}, {"a": 1, "b": 2}, {"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2, "c": 3, "d": 4},
        {"b": 2, "c": 3, "d": 4}, {"c": 3, "d": 4}, {"c": 3, "d": 4, "e": 5}, {},
    ]  # fmt: skip


def test_set_mutations_notify():
    s = state({1})
    seen = runs(lambda: sorted(s.value))
    s.value.add(2)
    s.value.discard(1)
    s.value |= {3}
    s.value -= {2}
    assert seen == [[1], [1, 2], [2], [2, 3], [3]]


def test_nested_mutation_only_notifies_readers_of_that_item():
    todos = state([{"id": 1, "done": False}, {"id": 2, "done": False}])
    first = runs(lambda: todos.value[0]["done"])
    second_reader = todos.value[1]
    second = runs(lambda: second_reader["done"])
    todos.value[0]["done"] = True
    assert first == [False, True]
    assert second == [False]


def test_computed_sees_nested_changes():
    todos = state([{"done": False}, {"done": False}])

    @computed
    def pending():
        return sum(not t["done"] for t in todos.value)

    assert pending.value == 2
    todos.value[1]["done"] = True
    assert pending.value == 1
    todos.value.append({"done": False})
    assert pending.value == 2


def test_inserted_values_become_reactive():
    s = state([])
    s.value.append({"x": [1]})
    item = s.value[0]
    assert type(item) is ReactiveDict and type(item["x"]) is ReactiveList
    seen = runs(lambda: len(item["x"]))
    item["x"].append(2)
    assert seen == [1, 2]


def test_reassigning_keeps_existing_reactive_items():
    s = state([{"id": 1}])
    original = s.value[0]
    s.value = [*s.value, {"id": 2}]
    assert s.value[0] is original


def test_mutation_in_a_batch_notifies_once():
    from janelkit import batch

    s = state([])
    seen = runs(lambda: len(s.value))
    with batch():
        s.value.append(1)
        s.value.append(2)
    assert seen == [0, 2]


def test_notify_for_objects_mutated_in_place():
    class Box:
        n = 0

    s = state(Box())
    seen = runs(lambda: s.value.n)
    s.value.n = 5
    assert seen == [0]
    s.notify()
    assert seen == [0, 5]


def test_reactive_collections_interoperate():
    s = state({"items": [1, {"a": {2}}]})
    plain = to_plain(s.value)
    assert type(plain) is dict and type(plain["items"]) is list and type(plain["items"][1]["a"]) is set
    assert json.dumps(state([{"a": 1}]).value) == '[{"a": 1}]'
    clone = copy.deepcopy(s.value)
    assert clone == s.value and clone is not s.value and type(clone) is ReactiveDict
    assert pickle.loads(pickle.dumps(s.value)) == s.value
    seen = runs(lambda: len(clone["items"]))
    clone["items"].append(3)
    assert seen == [2, 3]


def test_tuples_and_custom_types_are_left_alone():
    class MyList(list):
        pass

    s = state((1, [2]))
    assert type(s.value) is tuple and type(s.value[1]) is list
    assert type(state(MyList([1])).value) is MyList
