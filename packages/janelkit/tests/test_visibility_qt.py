"""Saber si el componente se ve (`is_visible()`) y condicionar temporizadores (`when=`).

Caso del primer usuario externo: un panel que muestrea a 30 Hz no debe seguir haciéndolo
mientras está en otra sección o en una página de debajo.
"""
import gc
import time
from pathlib import Path

import pytest

from janelkit import computed, interval, state, timeout
from janelkit.inspect import mount


def settle(janel_app, seconds: float):
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        janel_app.qt_app.processEvents()
        time.sleep(0.001)


@pytest.fixture
def project(tmp_path):
    def write(files: dict[str, str]) -> Path:
        for name, text in files.items():
            (tmp_path / name).write_text(text, encoding="utf-8")
        return tmp_path / "App.janel"
    return write


PANEL = """<script>
from janelkit import interval, is_visible, state
visible = is_visible()
ticks = state(0)

@interval(10, when=visible)
def muestrear():
    ticks.value += 1
</script>
<flex><text>panel {visible}</text></flex>
"""


def test_a_component_inside_hidden_follows_it(project):
    app_file = project({"Panel.janel": PANEL, "App.janel": """<script>
from janelkit import state
from Panel import Panel
oculto = state(True)
</script>
<flex>{#hidden oculto}<Panel />{/hidden}</flex>
"""})
    with mount(app_file) as app:
        app.namespace["oculto"].value = False  # se crea la primera vez que se muestra
        app.process()
        panel = app.mounted.instance.children[0].namespace
        assert panel["visible"].value is True
        app.namespace["oculto"].value = True
        app.process()
        assert panel["visible"].value is False and not panel["muestrear"].active
        app.namespace["oculto"].value = False
        app.process()
        assert panel["visible"].value is True and panel["muestrear"].active


def test_is_visible_only_while_the_script_runs():
    from janelkit import is_visible

    with pytest.raises(RuntimeError, match="is_visible"):
        is_visible()


def test_when_pauses_and_resumes_from_zero(janel_app):
    on = state(False)
    ticks = []
    timer = interval(10, lambda: ticks.append(1), when=on)
    try:
        assert not timer.active and "en espera de when" in repr(timer)
        settle(janel_app, 0.06)
        assert ticks == []
        on.value = True
        assert timer.active
        settle(janel_app, 0.06)
        assert ticks
        on.value = False
        n = len(ticks)
        settle(janel_app, 0.06)
        assert len(ticks) == n and not timer.active
    finally:
        timer.dispose()


def test_stop_wins_over_when_and_start_waits_for_it(janel_app):
    on = state(True)
    timer = interval(10, lambda: None, when=on)
    try:
        timer.stop()
        on.value = False
        on.value = True
        assert not timer.active  # parado a mano: `when` no lo vuelve a arrancar
        on.value = False
        timer.start()
        assert not timer.active  # lo pidió, pero espera a que `when` se cumpla
        on.value = True
        assert timer.active
    finally:
        timer.dispose()


def test_when_accepts_computed_and_functions(janel_app):
    n = state(0)
    fired = []
    by_computed = interval(10, lambda: None, when=computed(lambda: n.value > 1))
    by_function = timeout(10, lambda: fired.append(1), when=lambda: n.value == 3)
    try:
        assert not by_computed.active and not by_function.active
        n.value = 2
        assert by_computed.active and not by_function.active
        n.value = 3
        settle(janel_app, 0.06)
        assert fired == [1] and not by_function.active
        n.value = 0
        n.value = 3
        settle(janel_app, 0.06)
        assert fired == [1]  # un timeout que ya se disparó no vuelve a hacerlo
    finally:
        by_computed.dispose()
        by_function.dispose()


def test_unscoped_timer_waiting_on_when_is_not_collected(janel_app):
    on = state(False)
    ticks = []
    interval(10, lambda: ticks.append(1), when=on)  # sin guardar la referencia
    gc.collect()
    on.value = True
    settle(janel_app, 0.06)
    on.value = False  # que no siga contando en otras pruebas
    assert ticks


def test_when_must_be_reactive_or_callable(janel_app):
    with pytest.raises(TypeError, match="when="):
        interval(10, lambda: None, when=True)
