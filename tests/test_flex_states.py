"""<flex> fase 2: estados (pseudo-clases), selectores compuestos y de descendiente, transform,
box-shadow, outline y cursor. Ver docs/flex.md."""
import tempfile
from pathlib import Path

import pytest

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError
from fluxui.inspect import mount

FLEX = Path(__file__).parent.parent / "examples" / "flex"


@pytest.fixture
def app_from():
    apps = []

    def run(source: str):
        d = Path(tempfile.mkdtemp())
        (d / "App.flux").write_text(source, encoding="utf-8")
        ctx = mount(d / "App.flux")
        app = ctx.__enter__()
        apps.append(ctx)
        app.window.resize(300, 300)
        app.wait(0.05)
        return app

    yield run
    for ctx in apps:
        ctx.__exit__(None, None, None)


def color(el, prop="color"):
    return el.prop(prop).name()


ROWS = """<script>
from fluxui import state
items = state(["a", "b", "c"])
</script>
<Column>
<Column class="lista" gap={4}>
  {#each items as i}
  <flex class="fila" label={i}>
    <Text>{i}</Text>
    <flex class="acciones" label={"acc-" + i}><Text>x</Text></flex>
  </flex>
  {/each}
</Column>
<Button text="quitar" on:click={items.pop(0)} />
</Column>
<style>
.fila { padding: 8px; background: #ffffff; }
.fila:hover { background: #ff0000; box-shadow: 0 2px 8px rgba(0, 0, 0, .15); }
.fila:pressed { transform: scale(0.5) translate(0, 3px); }
.fila:first-child { border-top: 3px solid #00ff00; }
.fila:last-child { border-bottom: 2px solid #0000ff; }
/* Más específica que .acciones aunque vaya antes (como en CSS). */
.fila:hover .acciones { opacity: 1; }
.acciones { opacity: 0; }
</style>"""


def rows(app):
    return [e for e in app.elements() if e.tag == "flex" and e.label in ("a", "b", "c")]


def test_hover_pressed_and_descendant_states(app_from):
    app = app_from(ROWS)
    a, b, c = rows(app)
    b.hover()
    assert color(b) == "#ff0000" and color(c) == "#ffffff"
    assert b.prop("fxShadow") is True and b.prop("fxShadowBlur") == 8
    acciones = {e.label: e for e in app.elements() if (e.label or "").startswith("acc-")}
    assert acciones["acc-b"].prop("opacity") == 1 and acciones["acc-c"].prop("opacity") == 0
    b.press()
    assert b.prop("scale") == 0.5 and b.prop("fxTy") == 3
    b.release()
    assert b.prop("scale") == 1
    b.unhover()
    assert color(b) == "#ffffff" and acciones["acc-b"].prop("opacity") == 0


def test_first_and_last_child_follow_the_list(app_from):
    app = app_from(ROWS)
    assert [r.prop("fxBorderTop") for r in rows(app)] == [3, -1, -1]
    assert [r.prop("fxBorderBottom") for r in rows(app)] == [-1, -1, 2]
    app.find(text="quitar").click()
    app.wait(0.05)
    assert [(r.label, r.prop("fxBorderTop")) for r in rows(app)] == [("b", 3), ("c", -1)]


def test_conditional_class_on_ancestor_reaches_descendants(app_from):
    app = app_from("""<script>
from fluxui import state
sel = state(False)
</script>
<Column>
  <flex class="fila" class:sel={sel}><Text id="t">hola</Text></flex>
  <Button text="elegir" on:click={sel = True} />
</Column>
<style>
.fila .t-none { color: #000000; }
.fila.sel Text { color: #ff0000; }
</style>""")
    t = app.find("Text", text="hola")
    assert color(t, "fxColor") != "#ff0000"
    app.find(text="elegir").click()
    assert color(t, "fxColor") == "#ff0000"


def test_dynamic_classes_compound_with_states(app_from):
    app = app_from("""<script>
from fluxui import state
v = state("primary")
</script>
<Column>
  <flex class={["boton", v]} label="boton" on:click={v = "ghost"}><Text>b</Text></flex>
</Column>
<style>
.boton { background: #ffffff; }
.boton.primary { background: #0000ff; }
.boton.primary:hover { background: #000088; }
</style>""")
    b = app.find(label="boton")
    b.unhover()
    assert color(b) == "#0000ff"
    b.hover()
    assert color(b) == "#000088"
    b.click()
    assert color(b) == "#ffffff"


def test_focus_visible_outline_replaces_the_default_ring(app_from):
    app = app_from("""<Column>
  <flex class="boton" label="boton" on:click={print}><Text>b</Text></flex>
</Column>
<style>.boton:focus-visible { outline: 2px solid #ff0000; outline-offset: 2px; }</style>""")
    b = app.find(label="boton")
    assert b.prop("fxOutlineWidth") == 0
    b.focus()
    assert b.prop("fxOutlineWidth") == 2 and b.prop("fxOutlineOffset") == 2
    assert b.prop("fxKeyFocus") is True and b.prop("fxFocusRing") is False  # sin el borde de siempre
    assert b.item.property("fxOutlineItem") is not None


def test_disabled_and_checked_states(app_from):
    app = app_from("""<Column>
  <flex class="x" label="caja" enabled={False} checked><Text>x</Text></flex>
  <Checkbox class="c" text="c" checked />
</Column>
<style>
.x:disabled { opacity: 0.5; }
.x:checked { background: #00ff00; }
.c:checked { opacity: 0.25; }
</style>""")
    x = app.find(label="caja")
    assert x.prop("opacity") == 0.5 and color(x) == "#00ff00"
    assert app.find("Checkbox").prop("opacity") == 0.25


def test_cursor_and_transform_on_controls_compile():
    qml = compile_source("""<Column><Text class="t">hola</Text><flex class="f" /></Column>
<style>
.t { cursor: text; transform: rotate(5deg) translateX(2px); transition: transform 100ms; }
.f { cursor: pointer; transform: scale(1.1); }
</style>""").qml
    assert "property int fxCursor: Qt.IBeamCursor" in qml and "cursorShape: fxs0.fxCursor" in qml
    assert "transform: Translate { x: fxs0.fxTx; y: fxs0.fxTy }" in qml
    assert "rotation: 5" in qml and "property real fxTx: 2" in qml
    assert "Behavior on fxTx" in qml
    assert "fxCursor: Qt.PointingHandCursor" in qml and "scale: 1.1" in qml


def test_selector_errors_and_warnings():
    with pytest.raises(FluxError, match="pseudo-clase no soportada: ':visited'"):
        compile_source("<Column />\n<style>.a:visited { color: red; }</style>")
    with pytest.raises(FluxError, match="selector incompleto"):
        compile_source("<Column />\n<style>.a > { color: red; }</style>")
    c = compile_source("""<Column><flex class="f" /></Column>
<style>.f { box-shadow: 0 1px 2px #000, 0 4px 8px #000; }</style>""")
    assert any("solo se dibuja la primera sombra" in w.message for w in c.ir.warnings)


def test_child_combinator_only_matches_direct_children():
    qml = compile_source("""<Column class="menu">
  <Text class="item">a</Text>
  <flex><Text class="item">b</Text></flex>
</Column>
<style>.menu > .item { opacity: 0.5; }</style>""").qml
    assert qml.count("opacity: 0.5") == 1


def test_catalog_card_lifts_and_shows_actions_on_hover():
    with mount(FLEX / "src" / "App.flux") as app:
        app.window.resize(900, 600)
        app.wait(0.1)
        card = app.find_all("Tarjeta")[1]
        card.hover()
        app.wait(0.3)  # transiciones de 150 ms
        assert card.item.property("fxTy") == -2 and card.item.property("fxShadow") is True
        abrir = [e for e in app.find_all(label="Abrir") if e.tag == "Boton"][1]
        assert abrir.item.parentItem().parentItem().property("opacity") == 1  # .acciones
        abrir.hover()
        abrir.press()
        app.wait(0.15)
        assert abrir.prop("scale") < 1
        abrir.release()  # un clic real con el ratón
        assert "Última acción: abrir Tarjeta 2" in app.texts()
