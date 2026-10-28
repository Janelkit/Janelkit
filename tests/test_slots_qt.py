"""Slots: contenido entre las etiquetas de un componente, y estilos en la etiqueta del componente."""
from pathlib import Path

import pytest
from conftest import click, find, find_all, texts

from janelkit.compiler import compile_file
from janelkit.diagnostics import JanelError

CARD = """<script>
from janelkit import prop, state
title = prop("Tarjeta")
opened = state(True)
</script>
<Column class="card">
  <Text>[{title}]</Text>
  {#if opened}
    <Slot />
  {/if}
  <Row><Slot name="footer"><Text>pie por defecto</Text></Slot></Row>
</Column>
<style>
.card { padding: 4px; }
</style>
"""

APP = """<script>
from janelkit import state
from components.Card import Card
items = state(["a", "b"])
n = state(0)
</script>
<Column>
  {#each items as it (it)}
    <Card title={it}>
      <Text>contenido {it} {n}</Text>
      <Button id="inc" on:click={n += 1}>+</Button>
    </Card>
  {/each}
  <Card title="pie">
    <Text>solo</Text>
    <Button id="custom" slot="footer">otro pie</Button>
  </Card>
</Column>
"""


@pytest.fixture
def project(tmp_path):
    def make(files: dict[str, str]) -> Path:
        for rel, text in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return tmp_path / "App.janel"

    return make


def test_slot_content_uses_the_parent_scope(mount, project, caplog):
    m = mount(project({"App.janel": APP, "components/Card.janel": CARD}))
    assert caplog.text == ""  # sin avisos de QML
    assert texts(m) == [
        "[a]", "contenido a 0", "pie por defecto",
        "[b]", "contenido b 0", "pie por defecto",
        "[pie]", "solo",
    ]  # fmt: skip
    click(find_all(m, "inc")[1])
    assert m.instance.namespace["n"].value == 1
    assert "contenido a 1" in texts(m) and "contenido b 1" in texts(m)
    assert find(m, "custom").property("text") == "otro pie"


def test_slot_content_follows_the_child_lifecycle(mount, project):
    m = mount(project({"App.janel": APP, "components/Card.janel": CARD}))
    n = m.instance.namespace["n"]
    before = n.subscriber_count
    cards = [c for c in m.instance.root.regions[0].rows]
    child = cards[0].child
    child.namespace["opened"].value = False  # el <Slot /> está dentro de un {#if} del hijo
    assert "contenido a 0" not in texts(m)
    assert n.subscriber_count == before - 1
    child.namespace["opened"].value = True
    assert "contenido a 0" in texts(m)
    m.instance.namespace["items"].value.remove("a")
    assert n.subscriber_count == before - 1


def test_content_without_a_slot_is_an_error(project):
    child = "<script>\nfrom janelkit import prop\ntitle = prop()\n</script>\n<Column><Text>x</Text></Column>"
    with pytest.raises(JanelError) as info:
        compile_file(project({"App.janel": APP, "components/Card.janel": child}))
    first = info.value.first
    assert "<Card> no admite contenido entre etiquetas" in first.message
    assert "no declara ningún <Slot />" in first.hint


def test_unknown_named_slot_is_an_error(project):
    app = APP.replace('slot="footer"', 'slot="header"')
    with pytest.raises(JanelError) as info:
        compile_file(project({"App.janel": app, "components/Card.janel": CARD}))
    assert "no admite el slot 'header'" in info.value.first.message
    assert '<Slot name="footer" />' in info.value.first.hint


def test_class_and_flex_on_a_component_tag_style_an_outer_box(mount, project):
    child = "<Text>hijo</Text>"
    app = """<script>
from components.Child import Child
</script>
<Row>
  <Child id="box" class="wide" flex={1} />
</Row>
<style>
.wide { padding: 10px; }
</style>
"""
    m = mount(project({"App.janel": app, "components/Child.janel": child}))
    box = find(m, "box")
    assert box.property("padding") == 10 and box.property("jkFlex") == 1
    assert texts(m) == ["hijo"]


def test_props_named_like_wrapper_attributes_stay_props(mount, project):
    child = "<script>\nfrom janelkit import prop\nwidth = prop(0)\n</script>\n<Text>{width}</Text>"
    app = "<script>\nfrom components.Child import Child\n</script>\n<Column><Child width={5} /></Column>"
    m = mount(project({"App.janel": app, "components/Child.janel": child}))
    assert texts(m) == ["5"]
