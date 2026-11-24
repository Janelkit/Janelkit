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
<column>
  <button id="save" on:click={save}>{status}</button>
  <button id="load" on:click={load.run("hola")}>cargar</button>
  <button id="bad" on:click={load.run("mal")}>mal</button>
  <button id="compute" on:click={compute()}>calcular</button>
  {#if load.loading}
    <text>Cargando…</text>
  {:else if load.error}
    <text>Error: {load.error}</text>
  {:else if load.value}
    <text>{", ".join(load.value)}</text>
  {/if}
</column>
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
        '<button id="b" on:click={boom}>x</button>'
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


def settle_until(janel_app, condition, timeout: float = 5.0):
    """Deja correr el bucle hasta que `condition()` sea cierto."""

    async def wait():
        while not condition():
            await asyncio.sleep(0.01)

    janel_app.run_until(asyncio.wait_for(wait(), timeout))


PROGRESS_APP = """<script>
import threading
from janelkit import state, background, call_in_ui

progress = state(0)
result = state("")
cancel = threading.Event()
step = threading.Event()
on_ui = []

def show(i):
    on_ui.append(threading.current_thread() is threading.main_thread())
    progress.value = i

def work(n):
    for i in range(1, n + 1):
        if cancel.is_set():
            return "cancelado"
        call_in_ui(show, i).result()  # espera a que la interfaz lo haya aplicado
        step.wait()
    return "hecho"

async def start(n):
    cancel.clear()
    result.value = await background(work, n)
</script>
<column>
  <button id="start" on:click={start(3)}>Empezar</button>
  <button id="cancel" on:click={cancel.set()}>Cancelar</button>
  <progressbar value={progress} max={3} />
</column>
"""


def test_call_in_ui_applies_progress_from_a_background_thread(mount, janel_app):
    m = mount(PROGRESS_APP)
    ns = m.instance.namespace
    click(find(m, "start"))
    settle_until(janel_app, lambda: ns["progress"].value == 1)
    ns["step"].set()
    settle_until(janel_app, lambda: ns["result"].value == "hecho")
    assert ns["progress"].value == 3 and ns["on_ui"] == [True, True, True]


def test_a_threading_event_cancels_background_work(mount, janel_app):
    m = mount(PROGRESS_APP)
    ns = m.instance.namespace
    click(find(m, "start"))
    settle_until(janel_app, lambda: ns["progress"].value == 1)
    click(find(m, "cancel"))
    ns["step"].set()
    settle_until(janel_app, lambda: ns["result"].value == "cancelado")
    assert ns["progress"].value == 1


def test_call_in_ui_returns_a_future_and_logs_errors(janel_app, caplog):
    from janelkit import call_in_ui

    out = {}

    def worker():
        out["ok"] = call_in_ui(lambda a, b=0: (a + b, threading.current_thread() is threading.main_thread()), 2, b=3)
        out["bad"] = call_in_ui(lambda: 1 / 0)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    settle_until(janel_app, lambda: out["ok"].done() and out["bad"].done())
    assert out["ok"].result() == (5, True)
    assert isinstance(out["bad"].exception(), ZeroDivisionError)
    assert "ZeroDivisionError" in caplog.text

    from_ui = call_in_ui(lambda: "también desde la interfaz")  # se programa, no se ejecuta ya
    assert not from_ui.done()
    settle_until(janel_app, from_ui.done)
    assert from_ui.result() == "también desde la interfaz"


def test_call_in_ui_needs_a_running_application(monkeypatch):
    from janelkit import call_in_ui, tasks

    monkeypatch.setattr(tasks, "_ui_loop", None)
    import pytest

    with pytest.raises(RuntimeError, match="aplicación"):
        call_in_ui(print)
