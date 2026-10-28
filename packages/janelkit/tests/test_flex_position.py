"""<flex> fase 6: position (relative, absolute, fixed), top/left…, inset y z-index. Ver docs/flex.md."""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from janelkit.compiler import compile_source
from janelkit.inspect import mount

FLEX = Path(__file__).resolve().parents[3] / "apps" / "examples" / "flex"

APP = """<script>
from janelkit import state
mx = state(30)
abierto = state(False)
</script>
<Column>
  <flex class="icono" label="icono">
    <Text>✉</Text>
    <flex class="insignia" label="insignia"><Text>3</Text></flex>
  </flex>
  <flex class="fila">
    <flex class="c" label="c1" />
    <flex class="c rel" label="c2" />
    <flex class="c" label="c3" />
  </flex>
  <flex class="zona" label="zona">
    <flex class="dentro">
      <flex class="pop" label="pop" style={{"left": mx, "top": "10px"}} />
    </flex>
  </flex>
  <Button text="abrir" on:click={abierto = True} />
  {#if abierto}
    <flex class="velo" label="velo"><flex class="dialogo" label="dialogo"><Text>hola</Text></flex></flex>
  {/if}
</Column>
<style>
.icono { position: relative; width: 40px; height: 40px; background: #dddddd; }
.insignia { position: absolute; top: -4px; right: -4px; padding: 0 4px; background: #ff0000; z-index: 2; }
.fila { gap: 10px; }
.c { width: 50px; height: 20px; background: #cccccc; }
.rel { position: relative; top: 5px; left: 7px; }
.zona { position: relative; height: 100px; padding: 10px; border: 2px solid #000000; }
.dentro { padding: 20px; }
.pop { position: absolute; width: 50%; height: 30px; background: #00ff00; }
.velo { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); justify-content: center; align-items: center; z-index: 10; }
.dialogo { padding: 20px; background: #ffffff; }
</style>
"""


@pytest.fixture
def app():
    d = Path(tempfile.mkdtemp())
    (d / "App.janel").write_text(APP, encoding="utf-8")
    with mount(d / "App.janel") as app:
        app.window.resize(400, 400)
        app.wait(0.05)
        yield app


def rect(app, label):
    it = app.find("flex", label=label).item
    p = it.mapToScene(QPointF(0, 0))
    return (round(p.x()), round(p.y()), round(it.width()), round(it.height()))


def test_absolute_badge_in_corner(app):
    x, y, w, h = rect(app, "icono")
    bx, by, bw, bh = rect(app, "insignia")
    assert bx + bw == x + w + 4 and by == y - 4  # top: -4px; right: -4px
    assert app.find("flex", label="insignia").item.z() == 2
    assert w == 40  # la insignia no cuenta para el tamaño del icono


def test_relative_moves_without_moving_siblings(app):
    c1, c2, c3 = rect(app, "c1"), rect(app, "c2"), rect(app, "c3")
    assert c2[0] == c1[0] + 50 + 10 + 7 and c2[1] == c1[1] + 5
    assert c3[0] == c1[0] + 120 and c3[1] == c1[1]


def test_absolute_uses_nearest_positioned_ancestor_and_percent(app):
    zona = rect(app, "zona")
    pop = rect(app, "pop")
    # .dentro no tiene position: cuenta .zona (dentro de su borde de 2px)
    assert pop[0] == zona[0] + 2 + 30 and pop[1] == zona[1] + 2 + 10
    assert pop[2] == round((400 - 4) / 2)  # width: 50% del bloque contenedor
    app.namespace["mx"].set("25%")
    app.wait(0.05)
    assert rect(app, "pop")[0] == zona[0] + 2 + round(396 / 4)


def test_fixed_covers_window_and_follows_resize(app):
    app.find("Button").click()
    app.wait(0.05)
    assert rect(app, "velo") == (0, 0, 400, 400)
    app.window.resize(600, 500)
    app.wait(0.1)
    assert rect(app, "velo") == (0, 0, 600, 500)
    d = rect(app, "dialogo")
    assert d[0] + d[2] / 2 == pytest.approx(300, abs=1)  # centrado por el velo


def test_position_compiles_and_validates():
    qml = compile_source("""<Column><Text class="t">x</Text></Column>
<style>.t { position: absolute; inset: 0 10px; z-index: 3; }</style>""").qml
    assert 'property string jkPosition: "absolute"' in qml and "z: 3" in qml
    assert "property var jkLeft: 10" in qml and "Jk.positionDeps(" in qml
    c = compile_source('<Column class="c" />\n<style>.c { position: sticky; }</style>')
    assert any("position" in w.message for w in c.warnings)


def test_catalog_dialog_menu_and_badge():
    with mount(FLEX / "src" / "App.janel") as app:
        app.window.resize(900, 640)
        app.wait(0.2)
        zona = app.find("flex", label="Zona con menú contextual")
        at = zona.item.mapToScene(QPointF(300, 30)).toPoint()
        QTest.mouseClick(app.window, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, at)
        app.wait(0.1)
        menu = [e for e in app.elements() if e.tag == "Menu"][0]
        p = menu.item.mapToScene(QPointF(0, 0))
        assert (round(p.x()), round(p.y())) == (at.x() + 1, at.y() + 1)  # en el puntero (más el borde)
        QTest.keyClick(app.window, Qt.Key.Key_Escape)
        app.wait(0.05)

        borrar = app.find("Boton", label="Eliminar…")
        borrar.click()
        app.wait(0.1)
        aceptar = app.find("Boton", label="Aceptar")
        cancelar = app.find_all("Boton", label="Cancelar")[-1]
        assert aceptar.item.hasActiveFocus()
        QTest.keyClick(app.window, Qt.Key.Key_Tab)
        assert cancelar.item.hasActiveFocus()
        QTest.keyClick(app.window, Qt.Key.Key_Tab)
        assert aceptar.item.hasActiveFocus()  # el foco no sale del diálogo
        QTest.keyClick(app.window, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        assert cancelar.item.hasActiveFocus()

        dialogo = [e for e in app.elements() if e.tag == "flex" and e.prop("jkRole") == "dialog"][0]
        QTest.mouseClick(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         dialogo.item.mapToScene(QPointF(15, 15)).toPoint())
        app.wait(0.05)
        assert app.get("dialog_open")  # un clic dentro no lo cierra

        chip = app.find("Chip", label="datos")
        before = app.get("chosen")
        QTest.mouseClick(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         chip.item.mapToScene(QPointF(10, 10)).toPoint())
        app.wait(0.05)
        assert app.get("chosen") == before  # el velo no deja pulsar lo de debajo...
        assert not app.get("dialog_open")  # ...y su clic lo cierra
        assert app.find("Boton", label="Eliminar…").item.hasActiveFocus()  # el foco vuelve

        app.find("Boton", label="Eliminar…").click()
        app.wait(0.1)
        QTest.keyClick(app.window, Qt.Key.Key_Escape)
        app.wait(0.05)
        assert not app.get("dialog_open")
