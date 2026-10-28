"""Temporizadores ligados al componente: interval, timeout, restart y parada al desmontar."""
import asyncio
import logging
import time

from conftest import texts

from janelkit import interval, state, timeout


def settle(janel_app, seconds: float):
    """Procesa eventos durante `seconds` (run_until(asyncio.sleep) se pasa unos 20 ms)."""
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        janel_app.qt_app.processEvents()
        time.sleep(0.001)


TIMERS_APP = """<script>
from janelkit import state, interval, timeout, effect

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


def test_interval_ticks_batches_and_stops_on_unmount(mount, janel_app):
    m = mount(TIMERS_APP)
    ns = m.instance.namespace
    settle(janel_app, 0.2)
    ticks = ns["ticks"].value
    assert ticks >= 4
    assert ns["runs"].value == ticks + 1  # una vez al crearse y una por tic, no dos
    assert "una vez sí" in texts(m)
    assert ns["once"].active is False
    assert ns["tick"].active is True
    janel_app.unmount(m)
    assert ns["tick"].active is False
    settle(janel_app, 0.08)
    assert ns["ticks"].value == ticks


def test_timeout_restart_and_stop(janel_app):
    hits = []
    t = timeout(150, lambda: hits.append(1))
    settle(janel_app, 0.1)
    t.restart()  # vuelve a contar: a los 100 ms todavía no salta
    settle(janel_app, 0.1)
    assert hits == []
    settle(janel_app, 0.1)
    assert hits == [1]
    assert not t.active
    t.start()
    t.stop()
    settle(janel_app, 0.2)
    assert hits == [1]
    t.dispose()


def test_errors_are_logged_and_the_interval_keeps_going(janel_app, caplog):
    calls = state(0)

    def boom():
        calls.value += 1
        raise ValueError("fallo")

    t = interval(15, boom)
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        settle(janel_app, 0.1)
    t.dispose()
    assert calls.value >= 3
    assert "error en el temporizador boom" in caplog.text


ASYNC_TIMER_APP = """<script>
import asyncio
from janelkit import state, interval

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


def test_async_timer_runs_do_not_overlap_and_are_cancelled_with_the_component(mount, janel_app):
    m = mount(ASYNC_TIMER_APP)
    ns = m.instance.namespace
    janel_app.run_until(asyncio.sleep(0.1))
    assert ns["started"].value == 1  # los tics no se acumulan mientras la anterior sigue en curso
    janel_app.unmount(m)
    janel_app.run_until(asyncio.sleep(0.3))
    assert ns["finished"].value == 0  # las corrutinas en curso se cancelaron
