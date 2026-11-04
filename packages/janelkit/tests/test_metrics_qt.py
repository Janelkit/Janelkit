"""Métricas para depurar: tics saltados y duración en `Timer`, `subscriber_count` y los
`repr` de `Effect` y `Scope`."""
import asyncio
import time

from janelkit import effect, interval, state
from janelkit.reactivity import Scope


def settle(janel_app, seconds: float):
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        janel_app.qt_app.processEvents()
        time.sleep(0.001)


def test_timer_counts_runs_and_measures_the_last_one(janel_app):
    timer = interval(10, lambda: time.sleep(0.005))
    try:
        assert timer.runs == 0 and timer.skipped == 0 and timer.last_duration is None
        settle(janel_app, 0.08)
        assert timer.runs >= 2 and timer.skipped == 0
        assert 0.004 <= timer.last_duration < 0.1
        assert f"{timer.runs} ejecuciones" in repr(timer) and "última" in repr(timer)
    finally:
        timer.dispose()


def test_slow_async_tick_counts_skipped_and_its_full_duration(janel_app):
    async def slow():
        await asyncio.sleep(0.05)

    timer = interval(10, slow)
    try:
        janel_app.run_until(asyncio.sleep(0.2))
        assert timer.skipped > 0 and "saltados" in repr(timer)
        assert timer.last_duration is not None and timer.last_duration >= 0.04  # cuenta la parte async
    finally:
        timer.dispose()


def test_subscriber_count_goes_down_when_released():
    n = state(0)
    scope = Scope()
    with scope.active():
        effect(lambda: n.value)
        effect(lambda: n.value)
    assert n.subscriber_count == 2
    scope.dispose()
    assert n.subscriber_count == 0


def test_effect_and_scope_repr():
    n, m = state(0), state(1)
    scope = Scope()
    assert repr(scope) == "Scope(vacío)"
    with scope.active():
        def sumar():
            n.value + m.value

        e = effect(sumar)
    assert repr(e).startswith("effect ") and "sumar: lee 2 fuentes" in repr(e)
    assert repr(scope) == "Scope(1 Effect)"
    scope.dispose()
    assert repr(e).endswith("sumar (liberado)") and repr(scope) == "Scope (liberado)"
