"""<flex> fase 5: componentes usados como elementos (atributos a la raíz). Ver docs/flex.md."""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from fluxui.compiler import compile_file
from fluxui.diagnostics import FluxError
from fluxui.inspect import mount

CAJA = """<script>
from fluxui import prop
texto = prop("")
</script>
<flex class="caja" as="button" label={texto}><Text>{texto}</Text></flex>
<style>
.caja { padding: 4px; background: #eeeeee; }
.caja.fuerte { background: #000000; }
</style>
"""

CERRADA = """<script>
from fluxui import prop
inherit_attrs = False
texto = prop("")
</script>
<flex class="cerrada"><Text>{texto}</Text></flex>
"""

APP = """<script>
from fluxui import state, ref
from components.Caja import Caja
from components.Cerrada import Cerrada
log = state([])
items = state([1, 2, 3])
caja = ref()
off = state(False)
def foco():
    caja.focus()
</script>
<Column>
  <Caja texto="uno" class="a" on:click={log = log + ["uno"]} />
  <Caja texto="dos" class="fuerte" ref={caja} disabled={off} title="pista" />
  <Caja texto="tres" />
  <Cerrada texto="cerrada" class="a" />
  <flex class="fila">
    {#each items as i (i)}
      <Caja texto={f"n{i}"} class="celda" on:keydown={log = log + [event.key]} />
    {/each}
  </flex>
  <Button text="rev" on:click={items = list(reversed(items))} />
  <Button text="foco" on:click={foco()} />
</Column>
<style>
.a { width: 150px; }
.a:hover { background: #00ff00; }
.celda { flex: 1; }
</style>"""


@pytest.fixture
def project():
    d = Path(tempfile.mkdtemp())
    (d / "components").mkdir()
    (d / "components" / "Caja.flux").write_text(CAJA, encoding="utf-8")
    (d / "components" / "Cerrada.flux").write_text(CERRADA, encoding="utf-8")
    (d / "App.flux").write_text(APP, encoding="utf-8")
    return d


@pytest.fixture
def app(project):
    with mount(project / "App.flux") as app:
        app.window.resize(500, 400)
        app.wait(0.05)
        yield app


def cajas(app):
    return {e.label: e for e in app.elements() if e.tag == "Caja"}


def test_no_wrapper_box_for_box_roots(project):
    qml = compile_file(project / "App.flux").qml
    assert qml.count("FxRemote {") == 3  # uno, dos y las filas; tres no lleva atributos
    assert 'property: "fxInClass"' in qml
    # inherit_attrs = False: como antes, con caja exterior.
    assert "fxFill: true" in qml


def test_tag_styles_and_states_apply_to_root(app):
    uno = cajas(app)["uno"]
    assert uno.item.width() == pytest.approx(150)
    uno.unhover()
    assert uno.prop("fxBackground").name() == "#eeeeee"
    uno.hover()
    assert uno.prop("fxBackground").name() == "#00ff00"  # :hover de la etiqueta, en la raíz


def test_native_events_ref_and_disabled_reach_root(app):
    c = cajas(app)
    c["uno"].click()
    assert app.get("log") == ["uno"]
    app.find("Button", text="foco").click()
    assert c["dos"].item.hasActiveFocus()
    app.namespace["off"].set(True)
    app.wait(0.02)
    assert not c["dos"].item.isEnabled()
    n1 = c["n1"]
    n1.focus()
    QTest.keyClick(app.window, Qt.Key.Key_A)
    app.wait(0.02)
    assert app.get("log") == ["uno", "a"]


def test_class_on_tag_activates_component_rules(app):
    c = cajas(app)
    assert c["dos"].prop("fxBackground").name() == "#000000"  # .caja.fuerte del componente
    assert c["tres"].prop("fxBackground").name() == "#eeeeee"


def test_reordered_rows_keep_their_place(app):
    xs = lambda: {e.label: round(e.item.x()) for e in cajas(app).values() if e.label.startswith("n")}  # noqa: E731
    before = xs()
    assert before["n1"] < before["n2"] < before["n3"]
    app.find("Button", text="rev").click()
    app.wait(0.05)
    after = xs()
    assert after["n3"] < after["n2"] < after["n1"]


def test_undeclared_attrs_still_error_without_box_root(project):
    (project / "components" / "Boton2.flux").write_text(
        '<script>\nfrom fluxui import prop\ntext = prop("")\n</script>\n<Button text={text} />\n', encoding="utf-8"
    )
    (project / "B.flux").write_text(
        "<script>\nfrom components.Boton2 import Boton2\n</script>\n<Column><Boton2 text=\"x\" on:click={print(1)} /></Column>\n",
        encoding="utf-8",
    )
    with pytest.raises(FluxError, match="no declara el evento 'click'"):
        compile_file(project / "B.flux")
