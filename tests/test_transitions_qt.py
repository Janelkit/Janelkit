"""Transiciones: transition:/in:/out: al montar y desmontar bloques, y transition en CSS."""
import time

import pytest
from conftest import find_all, texts

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError

IF_APP = """<script>
from fluxui import state
show = state(True)
label = state("hola")
</script>
<Column>
  {#if show}
    <Text id="t" transition:fade={100}>{label}</Text>
  {/if}
</Column>
"""

EACH_APP = """<script>
from fluxui import state
items = state(["a", "b", "c"])
</script>
<Column>
  {#each items as it (it)}
    <Row id="row" out:slide={80}><Text>{it}</Text></Row>
  {/each}
</Column>
"""


def wait(flux_app, ms):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        flux_app.process_events()
        time.sleep(0.005)
    flux_app.process_events()


def test_enter_animation_starts_from_transparent(mount):
    m = mount(IF_APP)
    t = find_all(m, "t")[0]
    assert t.property("opacity") < 1  # la entrada acaba de empezar


def test_leave_keeps_the_view_and_bindings_until_the_animation_ends(mount, flux_app):
    m = mount(IF_APP)
    wait(flux_app, 150)
    ns = m.instance.namespace
    region = m.instance.root.regions[0]
    row = region.row
    ns["show"].value = False
    assert region.row is None  # lógicamente ya no está
    assert texts(m) == ["hola"]  # pero se sigue viendo mientras se anima
    ns["label"].value = "adiós"
    assert texts(m) == ["adiós"]  # y sus bindings siguen vivos
    assert not row.instance.disposed
    wait(flux_app, 200)
    assert texts(m) == [] and row.instance.disposed
    assert ns["label"].subscriber_count == 0


def test_toggling_back_during_the_leave_shows_a_new_row(mount, flux_app):
    m = mount(IF_APP)
    ns = m.instance.namespace
    ns["show"].value = False
    ns["show"].value = True
    assert texts(m) == ["hola", "hola"]  # la que sale y la nueva, a la vez
    wait(flux_app, 200)
    assert texts(m) == ["hola"]


def test_each_positions_ignore_leaving_rows(mount, flux_app):
    m = mount(EACH_APP)
    items = m.instance.namespace["items"]
    items.value.remove("a")
    assert len(find_all(m, "row")) == 3  # "a" aún sale
    items.value.insert(0, "z")
    items.value.reverse()  # c b z
    wait(flux_app, 150)
    assert texts(m) == ["c", "b", "z"]


def test_unmounting_during_a_leave_is_safe(mount, flux_app):
    m = mount(EACH_APP)
    m.instance.namespace["items"].value.clear()
    flux_app.unmount(m)
    wait(flux_app, 150)  # los temporizadores pendientes no fallan


def test_transition_only_on_block_roots():
    with pytest.raises(FluxError, match="solo se aplican al elemento raíz"):
        compile_source("<Column><Text transition:fade>x</Text></Column>")
    with pytest.raises(FluxError, match="transición desconocida 'wobble'"):
        compile_source("<script>\nx = True\n</script>\n<Column>{#if x}<Text transition:wobble>x</Text>{/if}</Column>")
    with pytest.raises(FluxError, match="duración en milisegundos"):
        compile_source("<script>\nx = True\n</script>\n<Column>{#if x}<Text in:fade={'r'}>x</Text>{/if}</Column>")


def test_css_transition_generates_behaviors():
    qml = compile_source(
        "<Column class=\"c\"><Text>x</Text></Column>\n<style>.c { background: #fff; transition: background 150ms, opacity .3s; }</style>"
    ).qml
    assert "Behavior on fxBackground { ColorAnimation { duration: 150" in qml
    assert "Behavior on opacity { NumberAnimation { duration: 300" in qml
    warnings = compile_source('<Text class="c">x</Text>\n<style>.c { transition: gap 1s; }</style>').warnings
    assert any("transition no puede animar 'gap'" in w.message for w in warnings)  # aviso, no error


def test_animated_list_releases_rows_after_the_animation(mount, flux_app, caplog):
    m = mount(
        """<script>
from fluxui import state
items = state([{"id": i} for i in range(5)])
</script>
<Window width={300} height={300}>
  <List id="list" animate>
    {#each items as it (it["id"])}<Row><Text>fila {it["id"]}</Text></Row>{/each}
  </List>
</Window>"""
    )
    region = m.instance.root.regions[0]
    assert region.slot.animated
    first = region.rows[0]
    assert first.instance is not None
    m.instance.namespace["items"].value.pop(0)
    assert not first.instance.disposed  # su vista aún se está desvaneciendo
    m.instance.namespace["items"].value.reverse()  # reordenar también se anima
    wait(flux_app, 300)
    assert first.instance.disposed
    assert caplog.text == ""
