import pytest

from janelkit import batch, computed, state
from janelkit.reactivity import Effect, ReactiveCycleError, Scope, untracked


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


def test_effect_skips_when_its_computed_keeps_the_same_value():
    # Corte por igualdad: mil celdas que dependen de «¿está esta fila en la selección?».
    cursor = state(0)
    in_row_3 = computed(lambda: cursor.value == 3)
    runs = []
    Effect(lambda: runs.append(in_row_3.value))
    cursor.value = 1
    cursor.value = 2
    assert runs == [False]
    cursor.value = 3
    cursor.value = 4
    assert runs == [False, True, False]


def test_effect_still_runs_when_a_state_it_reads_changed():
    a, b = state(1), state("x")
    parity = computed(lambda: a.value % 2)
    runs = []
    Effect(lambda: runs.append((parity.value, b.value)))
    with batch():
        a.value = 3  # misma paridad...
        b.value = "y"  # ...pero b cambió: se ejecuta
    assert runs == [(1, "x"), (1, "y")]


def test_chained_computeds_cut_at_the_first_unchanged_value():
    n = state(1)
    sign = computed(lambda: n.value > 0)
    label = computed(lambda: "positivo" if sign.value else "no positivo")
    runs = []
    Effect(lambda: runs.append(label.value))
    n.value = 5
    n.value = -1
    assert runs == ["positivo", "no positivo"]


def test_mutable_computed_values_always_count_as_changed():
    # Un computed que devuelve un objeto mutable puede devolver el mismo cambiado por dentro.
    items = state([1, 2])
    same = computed(lambda: items.value)
    runs = []
    Effect(lambda: runs.append(len(same.peek())) or same.value)
    items.value.append(3)
    assert runs == [2, 3]


def test_a_failing_computed_lets_the_effect_report_the_error():
    a = state(1)
    inv = computed(lambda: 1 / a.value)
    errors = []
    Effect(lambda: inv.value, on_error=errors.append)
    a.value = 0
    assert len(errors) == 1 and isinstance(errors[0], ZeroDivisionError)
