"""Temporizadores ligados al componente: interval, timeout, restart y parada al desmontar."""
import asyncio
import logging
import time

from conftest import texts

from fluxui import interval, state, timeout


def settle(flux_app, seconds: float):
    """Procesa eventos durante `seconds` (run_until(asyncio.sleep) se pasa unos 20 ms)."""
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        flux_app.qt_app.processEvents()
        time.sleep(0.001)


TIMERS_APP = """<script>
from fluxui import state, interval, timeout, effect

ticks = state(0)
runs = state(0)          # cuántas veces se ejecutaron los efectos de la plantilla
a = state(0)
b = state(0)
fired = state("no")

@interval(20)
def tick():
    ticks.value += 1
    a.value += 1         # dos cambios en el mismo tic: un único recálculo
    b.value += 1

once = timeout(30, lambda: fired.set("sí"))

def seen():
    a.value, b.value
    runs.set(runs.peek() + 1)

effect(seen)
</script>
<Column>
  <Text>tics {ticks}</Text>
  <Text>una vez {fired}</Text>
</Column>
"""


def test_interval_ticks_batches_and_stops_on_unmount(mount, flux_app):
    m = mount(TIMERS_APP)
    ns = m.instance.namespace
    settle(flux_app, 0.2)
    ticks = ns["ticks"].value
    assert ticks >= 4
    assert ns["runs"].value == ticks + 1  # una vez al crearse y una por tic, no dos
    assert "una vez sí" in texts(m)
    assert ns["once"].active is False
    assert ns["tick"].active is True
    flux_app.unmount(m)
    assert ns["tick"].active is False
    settle(flux_app, 0.08)
    assert ns["ticks"].value == ticks


def test_timeout_restart_and_stop(flux_app):
    hits = []
    t = timeout(150, lambda: hits.append(1))
    settle(flux_app, 0.1)
    t.restart()  # vuelve a contar: a los 100 ms todavía no salta
    settle(flux_app, 0.1)
    assert hits == []
    settle(flux_app, 0.1)
    assert hits == [1]
    assert not t.active
    t.start()
    t.stop()
    settle(flux_app, 0.2)
    assert hits == [1]
    t.dispose()


def test_errors_are_logged_and_the_interval_keeps_going(flux_app, caplog):
    calls = state(0)

    def boom():
        calls.value += 1
        raise ValueError("fallo")

    t = interval(15, boom)
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        settle(flux_app, 0.1)
    t.dispose()
    assert calls.value >= 3
    assert "error en el temporizador boom" in caplog.text


ASYNC_TIMER_APP = """<script>
import asyncio
from fluxui import state, interval

started = state(0)
finished = state(0)

@interval(10)
async def poll():
    started.value += 1
    await asyncio.sleep(0.2)
    finished.value += 1
</script>
<Text>{started}</Text>
"""


def test_async_timer_runs_do_not_overlap_and_are_cancelled_with_the_component(mount, flux_app):
    m = mount(ASYNC_TIMER_APP)
    ns = m.instance.namespace
    flux_app.run_until(asyncio.sleep(0.1))
    assert ns["started"].value == 1  # los tics no se acumulan mientras la anterior sigue en curso
    flux_app.unmount(m)
    flux_app.run_until(asyncio.sleep(0.3))
    assert ns["finished"].value == 0  # las corrutinas en curso se cancelaron
