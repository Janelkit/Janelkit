"""Reto 1 (docs/challenges_to_test.md): panel de monitorización, probado como un usuario.

Usa la fuente simulada (PANEL_SOURCE=sim): valores deterministas y 300 procesos.
"""
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject

from fluxui.inspect import mount

PANEL = Path(__file__).parent.parent / "examples" / "challenges" / "panel"


@pytest.fixture
def panel(monkeypatch):
    monkeypatch.setenv("PANEL_SOURCE", "sim")
    monkeypatch.setenv("PANEL_METRICS", "14")  # 6 generales + 8 núcleos
    monkeypatch.setenv("PANEL_RATE_MS", "50")
    monkeypatch.setenv("PANEL_HISTORY", "20")
    with mount(PANEL / "src" / "App.flux") as app:
        monitor = app.get("monitor")
        app.wait(until=lambda: len(monitor.processes.value) == 300)
        yield app


def list_view(app):
    item = app.find("List", id="procs").item
    return next(c for c in item.childItems() if c.inherits("QQuickListView"))


def top_row(view) -> int:
    return QMetaObject.invokeMethod(view, "indexAt", Q_RETURN_ARG("int"), Q_ARG("double", 1.0), Q_ARG("double", view.property("contentY") + 1))


def test_cards_cores_and_history(panel):
    app = panel
    monitor = app.get("monitor")
    assert [c.label for c in monitor.main] == ["CPU", "Memoria", "Red ↓", "Red ↑", "Disco (lectura)", "Disco (escritura)"]
    assert len(monitor.cores) == 8
    for label in ("CPU", "Memoria"):
        app.find("Card", label=label)
    for label in ("Núcleo 0", "Núcleo 7"):
        app.find("Column", label=label)
    cpu = monitor.series["cpu"]
    app.wait(until=lambda: len(cpu.history.value) == 20)
    samples = monitor.samples
    app.wait(until=lambda: monitor.samples >= samples + 5)
    assert len(cpu.history.value) == 20  # la historia no crece más allá de su capacidad
    assert cpu.history.value[-1] == cpu.value.value
    assert cpu.text() in app.texts()


def test_threshold_alert_and_notification(panel):
    app = panel
    monitor, source = app.get("monitor"), app.get("source")
    before = len(app.notifications())
    source.forced["cpu"] = 97.0
    app.wait(until=lambda: monitor.series["cpu"].alert.value)
    assert any(t.startswith("⚠ Por encima del umbral: CPU 97 %") for t in app.texts())
    assert len(app.notifications()) == before  # con la ventana activa no hace falta avisar al sistema

    source.forced.clear()
    app.wait(until=lambda: not monitor.series["cpu"].alert.value)
    app.namespace["active"].value = False
    source.forced["mem"] = 95.0
    app.wait(until=lambda: len(app.notifications()) == before + 1)
    assert app.notifications()[-1]["message"] == "Memoria: 95 %"


def test_sorting_and_filtering_keep_the_selection_and_the_scroll(panel):
    app = panel
    rows = lambda: app.get("rows")  # noqa: E731
    cpus = [p["cpu"] for p in rows()]
    assert cpus == sorted(cpus, reverse=True)  # por defecto, más CPU arriba

    app.find("Button", text="PID").click()
    assert [p["pid"] for p in rows()][:3] == [1299, 1298, 1297]
    app.find("Button", text="PID ▼").click()  # segundo clic: invierte
    assert [p["pid"] for p in rows()][:3] == [1000, 1001, 1002]

    app.find("Row", label=rows()[2]["name"]).click()
    assert app.get("selected") == 1002
    assert "PID 1002 · " in " ".join(app.texts())

    view = list_view(app)
    view.setProperty("contentY", view.property("originY") + 1500)
    app.wait(0.05)
    top = top_row(view)
    assert top > 20
    app.find("Button", text="CPU").click()  # reordenar mueve casi todas las filas
    reads = app.get("monitor").process_reads
    app.wait(until=lambda: app.get("monitor").process_reads >= reads + 2)  # y el refresco también
    assert top_row(view) == top
    assert app.get("selected") == 1002

    app.find("TextField", id="query").type("python")
    assert rows() and all("python" in p["name"] for p in rows())
    assert f"{len(rows())} procesos" in app.texts()
    app.find("TextField", id="query").type("1002")
    assert [p["pid"] for p in rows()] == [1002]


def test_chart_in_its_own_window_shares_the_same_state(panel, flux_app):
    app = panel
    cpu = app.get("monitor").series["cpu"]
    app.find("Button", label="Abrir CPU").click()
    window = app.get("windows")["cpu"]
    assert window.is_open
    (chart,) = app.windows()
    assert chart.window.title() == "CPU"
    texts = chart.texts
    app.wait(until=lambda: cpu.text() in texts())
    samples = app.get("monitor").samples
    app.wait(until=lambda: app.get("monitor").samples > samples + 2)
    assert cpu.text() in texts()  # se actualiza con la principal

    app.find("Button", label="Abrir CPU").click()  # otra vez: no abre una segunda
    assert app.get("windows")["cpu"] is window
    window.close()
    assert not window.is_open and app.windows() == []


def test_pause_and_sampling_rate(panel):
    app = panel
    monitor = app.get("monitor")
    app.find("Switch", text="Pausa").click()
    assert not app.get("sampler").active
    samples = monitor.samples
    app.wait(0.2)
    assert monitor.samples == samples
    app.find("Switch", text="Pausa").click()
    app.wait(until=lambda: monitor.samples > samples)

    app.find("Select").choose(1000)
    assert app.get("sampler").ms == 1000
    assert app.get("rate") == 1000
