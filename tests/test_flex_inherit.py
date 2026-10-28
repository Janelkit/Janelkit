"""<flex> fase 4: texto heredado, variables propias (--x) y style=. Ver docs/flex.md."""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError
from fluxui.inspect import mount

FLEX = Path(__file__).parent.parent / "examples" / "flex"

CAJA = """<flex class="caja"><Text>hijo</Text><Slot /></flex>
<style>.caja { padding: 4px; background: var(--fondo, #eeeeee); }</style>
"""

APP = """<script>
from fluxui import state
from components.Caja import Caja
sel = state(False)
pct = state(30)
acento = state("#00ff00")
</script>
<Column>
  <flex class="fila" class:sel={sel} label="fila">
    <Text>a</Text>
    <Text class="propio">b</Text>
    <Caja><Text>slot</Text></Caja>
  </flex>
  <flex class="tarjeta" label="tarjeta"><Text class="titulo">t</Text></flex>
  <flex label="inline" style={{"--fondo": acento, "width": f"{pct}%"}}><Caja /></flex>
  <flex label="fijo" class="gris" style="background: #123456; gap: 3px" />
  <Button text="sel" on:click={sel = True} />
</Column>
<style>
.fila { color: #0000ff; font-size: 20px; font-weight: bold; }
.fila.sel { color: #ff0000; }
.propio { color: #00ff00; }
.tarjeta { --acento: #aa0000; }
.tarjeta:hover { --acento: #00aa00; }
.titulo { color: var(--acento); }
.gris:hover { background: #999999; }
</style>"""


@pytest.fixture
def app():
    d = Path(tempfile.mkdtemp())
    (d / "components").mkdir()
    (d / "components" / "Caja.flux").write_text(CAJA, encoding="utf-8")
    (d / "App.flux").write_text(APP, encoding="utf-8")
    with mount(d / "App.flux") as app:
        app.window.resize(400, 400)
        app.wait(0.05)
        yield app


def color(app, text):
    return app.find(text=text).prop("color").name()


def test_text_inherits_through_components_and_slots(app):
    assert color(app, "a") == "#0000ff" and color(app, "slot") == "#0000ff"
    a = app.find(text="a").item.property("font")
    assert a.pixelSize() == 20 and a.bold()
    assert color(app, "b") == "#00ff00"  # lo propio gana a lo heredado
    hijos = [e.prop("color").name() for e in app.find_all("Text", text="hijo")]
    assert hijos[0] == "#0000ff" and hijos[1] != "#0000ff"  # el de fuera de .fila, el del tema
    app.find("Button").click()
    assert color(app, "a") == "#ff0000" and color(app, "slot") == "#ff0000"
    assert app.find_all("Text", text="hijo")[0].prop("color").name() == "#ff0000"


def test_variables_follow_states_and_cross_components(app):
    assert color(app, "t") == "#aa0000"
    app.find("flex", label="tarjeta").hover()
    assert color(app, "t") == "#00aa00"
    cajas = [e for e in app.elements() if e.tag == "Caja"]
    assert [c.prop("fxBackground").name() for c in cajas] == ["#eeeeee", "#00ff00"]
    app.namespace["acento"].set("#0000aa")
    app.wait(0.02)
    assert cajas[1].prop("fxBackground").name() == "#0000aa"


def test_inline_style_wins_and_reacts(app):
    inline = app.find("flex", label="inline")
    assert inline.prop("fxWidthPct") == 30 and inline.item.width() == pytest.approx(120)
    app.namespace["pct"].set(50)
    app.wait(0.05)
    assert inline.item.width() == pytest.approx(200)
    fijo = app.find("flex", label="fijo")
    assert fijo.prop("fxBackground").name() == "#123456" and fijo.prop("gap") == 3
    fijo.hover()
    assert fijo.prop("fxBackground").name() == "#123456"  # el estilo en línea gana también a :hover


def test_style_errors_and_theme_tokens_stay_static():
    with pytest.raises(FluxError, match="style=\\{...\\} espera un diccionario"):
        compile_source("<Column><flex style={estilo} /></Column>\n<script>\nestilo = {}\n</script>")
    with pytest.raises(FluxError, match="no admite 'transform'"):
        compile_source('<Column><flex style={{"transform": "scale(2)"}} /></Column>')
    qml = compile_source("""<Column><flex class="a"><Text>x</Text></flex></Column>
<style>.a { background: var(--surface); --propia: 4px; gap: var(--propia); }</style>""").qml
    assert "fxBackground: fxtheme.surface" in qml  # token del tema: como siempre
    assert 'gap: Fx.cssVar(fxCtx, "propia", fxtheme.propia, 0)' in qml
    assert "FxContext {" in qml and "property var fxV_propia: 4" in qml
    # Sin contexto, los textos no crean nada extra.
    plain = compile_source("<Column><Text>hola</Text></Column>").qml
    assert "FxContext" not in plain and "fxOwn" not in plain


def test_white_space_and_text_overflow():
    qml = compile_source("""<Column><Text class="t">x</Text><flex class="f"><Text>y</Text></flex></Column>
<style>.t { white-space: nowrap; text-overflow: ellipsis; } .f { white-space: nowrap; }</style>""").qml
    assert "wrapMode: Text.NoWrap" in qml and "elide: Text.ElideRight" in qml
    assert "property var fxT_wrap: Text.NoWrap" in qml


def test_catalog_table_and_tabs():
    with mount(FLEX / "src" / "App.flux") as app:
        app.window.resize(900, 760)
        app.wait(0.1)
        fila = app.find("flex", label="base-de-datos")
        assert fila.prop("selected") is True
        estado = app.find(text="● alerta")
        on_primary = estado.prop("color").name()
        app.find("flex", label="servidor-web").click()
        assert app.get("process") == 1
        assert app.find(text="● alerta").prop("color").name() != on_primary  # vuelve a --danger
        assert app.find(text="servidor-web").prop("color").name() == on_primary  # hereda de la fila elegida
        tabs = app.find("flex", label="Todos")
        tabs.focus()
        QTest.keyClick(app.window, Qt.Key.Key_Right)
        QTest.keyClick(app.window, Qt.Key.Key_Right)
        app.wait(0.05)
        assert app.get("view") == "Alertas"
        assert [e.label for e in app.elements() if e.tag == "flex" and e.prop("fxRole") == "option"] == ["base-de-datos"]
        # El texto del botón primario hereda --on-primary de la caja.
        assert app.find(text="Guardar").prop("color").name() != app.find(text="Cancelar").prop("color").name()


def test_inherited_text_follows_a_row_moved_to_another_box():
    # La fila (un componente) pasa de una columna roja a una grande: el <Text> deja el color
    # heredado (vuelve al del tema) y toma el tamaño. Solo hay un enlace por clave usada.
    d = Path(tempfile.mkdtemp())
    (d / "components").mkdir()
    (d / "components" / "Item.flux").write_text("""<script>
from fluxui import prop
texto = prop("")
</script>
<Text>{texto}</Text>""", encoding="utf-8")
    (d / "App.flux").write_text("""<script>
from fluxui import state
from components.Item import Item
cols = state([{"id": "a", "items": ["x"]}, {"id": "b", "items": []}])
def mover():
    a, b = cols.value
    b["items"].append(a["items"].pop())
</script>
<Column>
  <Row>{#each cols as c (c["id"])}<flex class="col" class:rojo={c["id"] == "a"} class:grande={c["id"] == "b"}>{#each c["items"] as it (it)}<Item texto={it} />{/each}</flex>{/each}</Row>
  <Text id="suelto">fuera</Text>
  <Button text="mover" on:click={mover()} />
</Column>
<style>.col { padding: 2px; } .rojo { color: #ff0000; } .grande { font-size: 22px; }</style>""", encoding="utf-8")
    with mount(d / "App.flux") as app:
        app.wait(0.05)
        x = app.find(text="x").item
        theme_size = app.find(text="fuera").item.property("font").pixelSize()
        assert x.property("color").name() == "#ff0000" and x.property("font").pixelSize() == theme_size
        assert sorted(x.property("fxInherit").toVariant()) == ["color", "size"]
        assert app.find(text="fuera").item.property("fxInherit") is None  # sin caja con texto: nada
        app.find("Button").click()
        app.wait(0.05)
        x = app.find(text="x").item
        assert x.property("color").name() == app.find(text="fuera").item.property("color").name()
        assert x.property("font").pixelSize() == 22
