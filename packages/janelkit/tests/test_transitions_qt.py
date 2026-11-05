"""Transiciones: transition:/in:/out: al montar y desmontar bloques, y transition en CSS."""
import time

import pytest
from janelkit.testing import find_all, texts

from janelkit.compiler import compile_source
from janelkit.diagnostics import JanelError

IF_APP = """<script>
from janelkit import state
show = state(True)
label = state("hola")
</script>
<column>
  {#if show}
    <text id="t" transition:fade={100}>{label}</text>
  {/if}
</column>
"""

EACH_APP = """<script>
from janelkit import state
items = state(["a", "b", "c"])
</script>
<column>
  {#each items as it (it)}
    <row id="row" out:slide={80}><text>{it}</text></row>
  {/each}
</column>
"""


def wait(janel_app, ms):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        janel_app.process_events()
        time.sleep(0.005)
    janel_app.process_events()


def test_enter_animation_starts_from_transparent(mount):
    m = mount(IF_APP)
    t = find_all(m, "t")[0]
    assert t.property("opacity") < 1  # la entrada acaba de empezar


def test_leave_keeps_the_view_and_bindings_until_the_animation_ends(mount, janel_app):
    m = mount(IF_APP)
    wait(janel_app, 150)
    ns = m.instance.namespace
    region = m.instance.root.regions[0]
    row = region.row
    ns["show"].value = False
    assert region.row is None  # lógicamente ya no está
    assert texts(m) == ["hola"]  # pero se sigue viendo mientras se anima
    ns["label"].value = "adiós"
    assert texts(m) == ["adiós"]  # y sus bindings siguen vivos
    assert not row.instance.disposed
    wait(janel_app, 200)
    assert texts(m) == [] and row.instance.disposed
    assert ns["label"].subscriber_count == 0


def test_toggling_back_during_the_leave_shows_a_new_row(mount, janel_app):
    m = mount(IF_APP)
    ns = m.instance.namespace
    ns["show"].value = False
    ns["show"].value = True
    assert texts(m) == ["hola", "hola"]  # la que sale y la nueva, a la vez
    wait(janel_app, 200)
    assert texts(m) == ["hola"]


def test_each_positions_ignore_leaving_rows(mount, janel_app):
    m = mount(EACH_APP)
    items = m.instance.namespace["items"]
    items.value.remove("a")
    assert len(find_all(m, "row")) == 3  # "a" aún sale
    items.value.insert(0, "z")
    items.value.reverse()  # c b z
    wait(janel_app, 150)
    assert texts(m) == ["c", "b", "z"]


def test_unmounting_during_a_leave_is_safe(mount, janel_app):
    m = mount(EACH_APP)
    m.instance.namespace["items"].value.clear()
    janel_app.unmount(m)
    wait(janel_app, 150)  # los temporizadores pendientes no fallan


def test_transition_only_on_block_roots():
    with pytest.raises(JanelError, match="solo se aplican al elemento raíz"):
        compile_source("<column><text transition:fade>x</text></column>")
    with pytest.raises(JanelError, match="transición desconocida 'wobble'"):
        compile_source("<script>\nx = True\n</script>\n<column>{#if x}<text transition:wobble>x</text>{/if}</column>")
    with pytest.raises(JanelError, match="duración en milisegundos"):
        compile_source("<script>\nx = True\n</script>\n<column>{#if x}<text in:fade={'r'}>x</text>{/if}</column>")


def test_css_transition_generates_behaviors():
    qml = compile_source(
        "<column class=\"c\"><text>x</text></column>\n<style>.c { background: #fff; transition: background 150ms, opacity .3s; }</style>"
    ).qml
    assert "Behavior on jkBackground { ColorAnimation { duration: 150" in qml
    assert "Behavior on opacity { NumberAnimation { duration: 300" in qml
    warnings = compile_source('<text class="c">x</text>\n<style>.c { transition: gap 1s; }</style>').warnings
    assert any("transition no puede animar 'gap'" in w.message for w in warnings)  # aviso, no error


def test_animated_list_releases_rows_after_the_animation(mount, janel_app, caplog):
    m = mount(
        """<script>
from janelkit import state
items = state([{"id": i} for i in range(5)])
</script>
<window width={300} height={300}>
  <list id="list" animate>
    {#each items as it (it["id"])}<row><text>fila {it["id"]}</text></row>{/each}
  </list>
</window>"""
    )
    region = m.instance.root.regions[0]
    assert region.slot.animated
    first = region.rows[0]
    assert first.instance is not None
    m.instance.namespace["items"].value.pop(0)
    assert not first.instance.disposed  # su vista aún se está desvaneciendo
    m.instance.namespace["items"].value.reverse()  # reordenar también se anima
    wait(janel_app, 300)
    assert first.instance.disposed
    assert caplog.text == ""
