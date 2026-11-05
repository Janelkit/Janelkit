"""El ámbito del componente sobrevive a los `await`: lo creado después también le pertenece.

Caso del primer usuario externo: un `timeout` creado tras un `await` en un manejador
async nunca se disparaba (el `Timer` quedaba sin ámbito y Python lo recolectaba).
"""
import asyncio
import gc

from janelkit.testing import click, find

from janelkit import state, timeout

AFTER_AWAIT_APP = """<script>
import asyncio
from janelkit import state, timeout, interval, effect, spawn, on_mount

fired = state([])
ticks = state(0)
runs = state(0)
source = state(0)
created = {}
gate = asyncio.Event()

def hide_a():
    fired.value = fired.value + ["a"]

def hide_b():
    fired.value = fired.value + ["b"]

def sync_handler():
    timeout(30, hide_a)

async def async_handler():
    await asyncio.sleep(0)
    timeout(30, hide_b)

async def start_things():
    await asyncio.sleep(0)
    created["interval"] = interval(10, lambda: ticks.set(ticks.peek() + 1))
    created["effect"] = effect(lambda: runs.set(runs.peek() + source.value))
    created["task"] = spawn(gate.wait())
</script>
<column>
  <button id="a" on:click={sync_handler}>a</button>
  <button id="b" on:click={async_handler}>b</button>
  <button id="start" on:click={start_things}>start</button>
  <text id="out">{",".join(fired)}</text>
</column>
"""


def settle(janel_app, seconds: float = 0.05):
    janel_app.run_until(asyncio.sleep(seconds))


def test_timeout_created_after_await_fires(mount, janel_app):
    m = mount(AFTER_AWAIT_APP)
    click(find(m, "a"))
    click(find(m, "b"))
    for _ in range(3):  # sin referencias externas: antes el Timer se recolectaba aquí
        gc.collect()
        settle(janel_app, 0.03)
    settle(janel_app, 0.1)
    assert m.instance.namespace["fired"].value == ["a", "b"]
    assert find(m, "out").property("text") == "a,b"


def test_things_created_after_await_are_released_on_unmount(mount, janel_app):
    m = mount(AFTER_AWAIT_APP)
    ns = m.instance.namespace
    click(find(m, "start"))
    settle(janel_app, 0.06)
    created = ns["created"]
    assert created["interval"].active and ns["ticks"].value > 0
    assert ns["source"].subscriber_count == 1
    assert not created["task"].done()

    janel_app.unmount(m)
    settle(janel_app, 0.02)
    ticks = ns["ticks"].peek()
    settle(janel_app, 0.06)
    assert ns["ticks"].peek() == ticks and not created["interval"].active
    assert ns["source"].subscriber_count == 0  # el efecto se liberó
    assert created["task"].cancelled()


def test_timer_without_component_fires_without_keeping_a_reference(janel_app):
    seen = state([])
    timeout(10, lambda: seen.set([*seen.peek(), "x"]))  # sin guardar la referencia
    gc.collect()
    settle(janel_app, 0.08)
    assert seen.value == ["x"]
