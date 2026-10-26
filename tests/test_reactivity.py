import pytest

from fluxui import batch, computed, state
from fluxui.reactivity import Effect, ReactiveCycleError, Scope, untracked


def test_state_value_and_helpers():
    s = state(1)
    s.value = 2
    s.set(3)
    s.update(lambda v: v * 10)
    assert s.value == 30
    assert s.peek() == 30
    assert repr(s) == "state(30)"


def test_effect_reruns_on_change_only():
    s = state(0)
    seen = []
    Effect(lambda: seen.append(s.value))
    s.value = 1
    s.value = 1  # mismo valor: sin notificación
    s.value = 2
    assert seen == [0, 1, 2]


def test_equal_but_different_type_counts_as_change():
    s = state(1)
    seen = []
    Effect(lambda: seen.append(s.value))
    s.value = True
    assert seen == [1, True]


def test_dependencies_are_dynamic():
    flag, a, b = state(True), state("a"), state("b")
    seen = []
    Effect(lambda: seen.append(a.value if flag.value else b.value))
    b.value = "b2"  # no es dependencia todavía
    flag.value = False
    a.value = "a2"  # ya no es dependencia
    b.value = "b3"
    assert seen == ["a", "b2", "b3"]


def test_computed_is_lazy_and_cached():
    a = state(2)
    calls = []

    @computed
    def double():
        calls.append(1)
        return a.value * 2

    assert calls == []
    assert double.value == 4 and double.value == 4
    assert len(calls) == 1
    a.value = 5
    assert double.value == 10
    assert len(calls) == 2


def test_effect_depending_on_computed():
    first, last = state("Ada"), state("Lovelace")

    @computed
    def full():
        return f"{first.value} {last.value}"

    seen = []
    Effect(lambda: seen.append(full.value))
    last.value = "King"
    assert seen == ["Ada Lovelace", "Ada King"]


def test_batch_runs_effects_once():
    a, b = state(1), state(2)
    seen = []
    Effect(lambda: seen.append(a.value + b.value))
    with batch():
        a.value = 10
        b.value = 20
        assert seen == [3]
    assert seen == [3, 30]


def test_untracked_read():
    a, b = state(1), state(1)
    seen = []

    def run():
        with untracked():
            other = b.value
        seen.append(a.value + other)

    Effect(run)
    b.value = 5
    assert seen == [2]
    a.value = 2
    assert seen == [2, 7]


def test_scope_dispose_stops_updates_and_unsubscribes():
    s = state(0)
    scope = Scope()
    seen = []
    with scope.active():
        Effect(lambda: seen.append(s.value))

        @computed
        def plus_one():
            return s.value + 1

        Effect(lambda: plus_one.value)
    assert s.subscriber_count == 2
    scope.dispose()
    s.value = 1
    assert seen == [0]
    assert s.subscriber_count == 0


def test_effect_error_handler():
    s = state(1)
    errors = []
    Effect(lambda: 1 / s.value, on_error=errors.append)
    s.value = 0
    assert len(errors) == 1 and isinstance(errors[0], ZeroDivisionError)
    s.value = 2  # la dependencia se conserva tras el error
    s.value = 0
    assert len(errors) == 2


def test_cycle_detection():
    s = state(0)
    # el efecto se reactiva a sí mismo; debe cortarse con un error claro, no con RecursionError
    with pytest.raises(ReactiveCycleError):
        Effect(lambda: s.set(s.value + 1))


def test_effect_writing_other_state_settles():
    a, b = state(1), state(0)
    Effect(lambda: b.set(a.value * 2))
    seen = []
    Effect(lambda: seen.append(b.value))
    a.value = 5
    assert b.value == 10
    assert seen == [2, 10]
