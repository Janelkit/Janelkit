"""Trabajo asíncrono: manejadores async, tareas con estado, trabajo en hilos y cancelación al desmontar."""
import asyncio
import logging
import threading

from janelkit.testing import click as press
from janelkit.testing import find, texts

from janelkit import background, spawn, state, task


def click(item):
    press(item)


def settle(janel_app, seconds: float = 0.05):
    """Deja correr el bucle de asyncio (integrado con Qt) un momento."""
    janel_app.run_until(asyncio.sleep(seconds))


ASYNC_APP = """<script>
import asyncio
from janelkit import state, task, background, on_mount
import threading

status = state("listo")
log = state([])
gate = asyncio.Event()

async def save():
    status.value = "guardando"
    await gate.wait()
    status.value = "guardado"

@task
async def load(q):
    await asyncio.sleep(0.01)
    if q == "mal":
        raise ValueError("consulta no válida")
    return [q, q.upper()]

def heavy(n):
    return (n * 2, threading.current_thread().name)

async def compute():
    result, thread = await background(heavy, 21)
    log.value.append((result, thread.startswith("janelkit-background")))

@on_mount
async def started():
    await asyncio.sleep(0)
    log.value.append("montado")
</script>
<Column>
  <Button id="save" on:click={save}>{status}</Button>
  <Button id="load" on:click={load.run("hola")}>cargar</Button>
  <Button id="bad" on:click={load.run("mal")}>mal</Button>
  <Button id="compute" on:click={compute()}>calcular</Button>
  {#if load.loading}
    <Text>Cargando…</Text>
  {:else if load.error}
    <Text>Error: {load.error}</Text>
  {:else if load.value}
    <Text>{", ".join(load.value)}</Text>
  {/if}
</Column>
"""


def test_async_handler_runs_without_blocking(mount, janel_app):
    m = mount(ASYNC_APP)
    ns = m.instance.namespace
    click(find(m, "save"))
    settle(janel_app)
    assert ns["status"].value == "guardando"  # esperando: la interfaz sigue viva
    ns["gate"].set()
    settle(janel_app)
    assert ns["status"].value == "guardado" and find(m, "save").property("text") == "guardado"


def test_task_exposes_loading_error_and_value(mount, janel_app):
    m = mount(ASYNC_APP)
    click(find(m, "load"))
    assert texts(m) == ["Cargando…"]
    settle(janel_app)
    assert texts(m) == ["hola, HOLA"]
    click(find(m, "bad"))
    settle(janel_app)
    assert texts(m) == ["Error: consulta no válida"]


def test_background_runs_in_another_thread(mount, janel_app):
    m = mount(ASYNC_APP)
    click(find(m, "compute"))
    settle(janel_app, 0.2)
    assert (42, True) in m.instance.namespace["log"].value


def test_async_on_mount(mount, janel_app):
    m = mount(ASYNC_APP)
    settle(janel_app)
    assert "montado" in m.instance.namespace["log"].value


def test_unmount_cancels_pending_work(mount, janel_app):
    m = mount(ASYNC_APP)
    ns = m.instance.namespace
    click(find(m, "save"))
    click(find(m, "load"))
    settle(janel_app, 0)
    janel_app.unmount(m)
    ns["gate"].set()
    settle(janel_app)
    assert ns["status"].value == "guardando"  # la corrutina se canceló antes de terminar
    assert ns["load"].loading is False and ns["load"].value is None


def test_errors_in_async_handlers_are_reported(mount, janel_app, caplog):
    m = mount(
        "<script>\nasync def boom():\n    raise RuntimeError('fallo async')\n</script>\n"
        '<Button id="b" on:click={boom}>x</Button>'
    )
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        click(find(m, "b"))
        settle(janel_app)
    assert "error en el manejador on:click: RuntimeError: fallo async" in caplog.text
    assert "App.janel:5" in caplog.text


def test_task_run_cancels_the_previous_run(janel_app):
    seen = []

    @task
    async def slow(x):
        await asyncio.sleep(0.02)
        seen.append(x)
        return x

    slow.run(1)
    slow.run(2)
    settle(janel_app)
    assert seen == [2] and slow.value == 2 and not slow.loading


def test_spawn_outside_components_logs_errors(janel_app, caplog):
    async def boom():
        raise KeyError("x")

    with caplog.at_level(logging.ERROR, logger="janelkit"):
        spawn(boom())
        settle(janel_app)
    assert "error en una tarea asíncrona: KeyError" in caplog.text


def test_background_result_is_applied_in_the_ui_thread(janel_app):
    s = state(None)
    main = threading.current_thread()

    async def work():
        value = await background(lambda: threading.current_thread() is main)
        s.value = (value, threading.current_thread() is main)

    janel_app.run_until(work())
    assert s.value == (False, True)


def test_exec_runs_the_asyncio_loop(janel_app, monkeypatch):
    """exec() usa el bucle integrado: una corrutina programada antes de arrancar se ejecuta."""
    done = []

    async def job():
        await asyncio.sleep(0)
        done.append(True)
        janel_app.qt_app.quit()

    monkeypatch.delenv("JANELKIT_EXIT_AFTER_MS", raising=False)
    monkeypatch.setattr(janel_app, "close", lambda: None)  # la app de la sesión sigue viva
    spawn(job())
    assert janel_app.exec() == 0
    assert done == [True]


def test_background_threads_do_not_track_and_cannot_write(janel_app):
    from janelkit.reactivity import Effect
    from janelkit.reactivity.effects import WrongThreadError

    items = state([{"a": 1}])
    runs = []
    Effect(lambda: runs.append(len(items.value)))

    def read_and_write():
        total = sum(d["a"] for d in items.value)  # leer en otro hilo: permitido, sin dependencias
        try:
            items.value.append({"a": 2})
        except WrongThreadError as exc:
            return total, str(exc)
        return total, None

    async def work():
        return await background(read_and_write)

    total, error = janel_app.run_until(work())
    assert total == 1 and "hilo de la interfaz" in error
    assert runs == [1] and len(items.value) == 1
