"""Arrastrar y soltar en <flex> (docs/flex.md, «Arrastrar y soltar»): draggable,
on:dragstart/dragover/drop/dragend, :dragging y :drag-over, Escape para cancelar."""
import pytest

from fluxui.inspect import mount

APP = """<script>
from fluxui import state

zonas = state({"a": ["uno", "dos"], "b": []})
log = state([])
encima = state("")


def empezar(event, nombre):
    event.data = nombre
    log.value.append(f"start {nombre}")


def sobre(event, zona):
    encima.set(zona)


def soltar(event, zona):
    for k in zonas.value:
        if event.data in zonas.value[k]:
            zonas.value[k].remove(event.data)
    zonas.value[zona].append(event.data)
    log.value.append(f"drop {event.data} {zona}")


def terminar(event):
    log.value.append(f"end {event.data} {event.dropped}")


def bloquear(event):
    event.prevent()
</script>
<Window width={500} height={300}>
  <flex class="tablero">
    {#each ["a", "b"] as z (z)}
      <flex class="zona" label={z} on:drop={soltar(event, z)} on:dragover={sobre(event, z)}>
        {#each zonas[z] as n (n)}
          <flex class="ficha" label={n} draggable on:dragstart={empezar(event, n)} on:dragend={terminar}
                on:click={log.append(f"click {n}")}>
            <Text>{n}</Text>
          </flex>
        {/each}
      </flex>
    {/each}
    <flex class="fija" label="fija" draggable on:dragstart={bloquear}><Text>fija</Text></flex>
  </flex>
</Window>
<style>
.tablero { gap: 10px; padding: 10px; }
.zona { direction: column; width: 150px; height: 200px; gap: 4px; padding: 4px; border: 1px solid #888888; }
.zona:drag-over { background: #ddeeff; }
.ficha { padding: 6px; background: #eeeeee; }
.ficha:dragging { opacity: 0.4; }
</style>
"""


@pytest.fixture
def app():
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp())
    (d / "App.flux").write_text(APP, encoding="utf-8")
    with mount(d / "App.flux") as app:
        yield app


def zona(app, z):
    return app.find("flex", label=z)


def ficha(app, n):
    return app.find("flex", label=n)


def test_drag_a_box_to_another_zone(app):
    ficha(app, "uno").drag_to(zona(app, "b"))
    assert app.get("zonas") == {"a": ["dos"], "b": ["uno"]}
    assert app.get("log") == ["start uno", "drop uno b"]  # la ficha se recreó: no hay dragend
    assert app.get("encima") == "b"


def test_states_while_dragging_and_no_click_at_the_end(app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    uno, b = ficha(app, "uno"), zona(app, "b")
    start, end = uno._center(), b._center()
    QTest.mousePress(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(app.window, start + QPoint(30, 0))
    QTest.mouseMove(app.window, end)
    app.process()
    assert uno.prop("fxDragging") is True and b.prop("fxDragOver") is True
    assert b.prop("fxBackground").name() == "#ddeeff"  # :drag-over
    assert uno.prop("opacity") == pytest.approx(0.4)  # :dragging
    QTest.mouseMove(app.window, start)  # de vuelta a su zona
    app.process()
    assert b.prop("fxDragOver") is False and zona(app, "a").prop("fxDragOver") is True
    QTest.mouseRelease(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    app.process()
    assert "click uno" not in app.get("log")  # soltar no es hacer clic
    assert app.get("log")[-1] == "end uno True"  # soltada en su misma zona: sigue viva
    assert uno.prop("fxDragging") is False


def test_escape_cancels_and_prevent_blocks(app):
    ficha(app, "dos").drag_to(zona(app, "b"), cancel=True)
    assert app.get("zonas") == {"a": ["uno", "dos"], "b": []}
    assert app.get("log") == ["start dos", "end dos False"]
    app.find("flex", label="fija").drag_to(zona(app, "b"))  # on:dragstart con prevent(): no hay arrastre
    assert app.get("log") == ["start dos", "end dos False"]


def test_a_short_press_is_still_a_click(app):
    ficha(app, "uno").click()
    assert app.get("log") == ["click uno"]


def test_dragging_near_the_edge_scrolls_the_list(tmp_path):
    (tmp_path / "App.flux").write_text("""<script>
from fluxui import state
filas = state([f"f{i}" for i in range(60)])
soltada = state("")
</script>
<Window width={300} height={240}>
  <List>
    {#each filas as f (f)}
      <flex class="fila" label={f} draggable on:dragstart={event.data = f} on:drop={soltada = f}><Text>{f}</Text></flex>
    {/each}
  </List>
</Window>
<style>.fila { height: 30px; }</style>""", encoding="utf-8")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    with mount(tmp_path / "App.flux") as app:
        view = next(i for i in app._walk(app.window.contentItem()) if i.inherits("QQuickListView"))
        start = app.find("flex", label="f1")._center()
        bottom = view.mapToScene(view.boundingRect().bottomLeft()).toPoint() + QPoint(start.x(), -5)
        QTest.mousePress(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(app.window, start + QPoint(0, 20))
        QTest.mouseMove(app.window, bottom)
        app.wait(0.4)  # quieto cerca del borde: la lista baja sola
        assert view.property("contentY") > 100
        QTest.mouseRelease(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, bottom)
        app.process()
        assert int(app.get("soltada")[1:]) > 8  # una fila que al empezar no se veía
