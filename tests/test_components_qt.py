"""Composición de componentes .flux: props, eventos, estado local y ciclo de vida."""
import logging
from pathlib import Path

import pytest
from conftest import find, find_all, texts
from PySide6.QtCore import QMetaObject
from PySide6.QtGui import QColor

from fluxui import theme
from fluxui.compiler import compile_file
from fluxui.diagnostics import FluxError

ITEM = """<script>
from fluxui import prop, event, state
todo = prop()
prefix = prop("-")
removed = event()
toggled = event()
clicks = state(0)

def remove():
    removed.emit(todo.value["id"])

def bump():
    clicks.value += 1
</script>
<Row>
  <Text>{prefix}{todo["t"]}#{clicks}</Text>
  <Button id="bump" on:click={bump}>+</Button>
  <Button id="remove" on:click={remove}>x</Button>
</Row>
"""

APP = """<script>
from fluxui import state
from components.Item import Item
todos = state([{"id": 1, "t": "a"}, {"id": 2, "t": "b"}, {"id": 3, "t": "c"}])
prefix = state(">")
log = state([])
def on_removed(todo_id):
    log.value = [*log.value, todo_id]
    todos.value = [t for t in todos.value if t["id"] != todo_id]
</script>
<Column>
  {#each todos as todo (todo["id"])}
    <Item todo={todo} prefix={prefix} on:removed={on_removed} />
  {/each}
</Column>
"""


@pytest.fixture
def project(tmp_path):
    def make(files: dict[str, str]) -> Path:
        for rel, text in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return tmp_path / "App.flux"

    return make


def click(item):
    assert QMetaObject.invokeMethod(item, "click")


def test_props_flow_down_and_update(mount, project):
    m = mount(project({"App.flux": APP, "components/Item.flux": ITEM}))
    assert texts(m) == [">a#0", ">b#0", ">c#0"]
    m.instance.namespace["prefix"].value = "*"
    assert texts(m) == ["*a#0", "*b#0", "*c#0"]
    todos = m.instance.namespace["todos"]
    todos.value = [{"id": 1, "t": "A"}, *todos.value[1:]]
    assert texts(m) == ["*A#0", "*b#0", "*c#0"]


def test_child_events_reach_the_parent(mount, project):
    m = mount(project({"App.flux": APP, "components/Item.flux": ITEM}))
    click(find_all(m, "remove")[1])
    assert m.instance.namespace["log"].value == [2]
    assert texts(m) == [">a#0", ">c#0"]


def test_removing_a_row_keeps_local_state_of_the_others(mount, project):
    m = mount(project({"App.flux": APP, "components/Item.flux": ITEM}))
    bumps = find_all(m, "bump")
    click(bumps[0])
    click(bumps[2])
    click(bumps[2])
    assert texts(m) == [">a#1", ">b#0", ">c#2"]
    click(find_all(m, "remove")[0])
    assert texts(m) == [">b#0", ">c#2"]
    todos = m.instance.namespace["todos"]
    todos.value = list(reversed(todos.value))
    assert texts(m) == [">c#2", ">b#0"]


def test_unmounted_child_stops_receiving_notifications(mount, project):
    m = mount(project({"App.flux": APP, "components/Item.flux": ITEM}))
    prefix = m.instance.namespace["prefix"]
    assert prefix.subscriber_count == 3  # un efecto de prop por fila
    m.instance.namespace["todos"].value = []
    assert prefix.subscriber_count == 0


def test_component_instances_are_independent(mount, project):
    app = """<script>
from components.Item import Item
</script>
<Column>
  <Item todo={{"id": 1, "t": "x"}} />
  <Item todo={{"id": 2, "t": "y"}} prefix="+" />
</Column>"""
    m = mount(project({"App.flux": app, "components/Item.flux": ITEM}))
    click(find_all(m, "bump")[1])
    assert texts(m) == ["-x#0", "+y#1"]


def test_props_are_read_only_in_the_child(mount, project, caplog):
    child = """<script>
from fluxui import prop
v = prop(1)
def change():
    v.value = 2
</script>
<Button id="b" on:click={change}>{v}</Button>"""
    m = mount(project({"App.flux": "<script>\nfrom C import C\n</script>\n<Column><C /></Column>", "C.flux": child}))
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        click(find(m, "b"))
    assert "solo lectura" in caplog.text


def test_unconnected_event_is_a_noop(mount, project):
    child = """<script>
from fluxui import event
done = event()
</script>
<Button id="b" on:click={lambda: done.emit(1)}>ok</Button>"""
    m = mount(project({"App.flux": "<script>\nfrom C import C\n</script>\n<C />", "C.flux": child}))
    click(find(m, "b"))


def test_child_component_can_toggle_with_if(mount, project):
    app = """<script>
from fluxui import state
from components.Item import Item
show = state(True)
</script>
<Column>{#if show}<Item todo={{"id": 1, "t": "x"}} />{:else}<Text>oculto</Text>{/if}</Column>"""
    m = mount(project({"App.flux": app, "components/Item.flux": ITEM}))
    assert texts(m) == ["-x#0"]
    m.instance.namespace["show"].value = False
    assert texts(m) == ["oculto"]
    m.instance.namespace["show"].value = True
    assert texts(m) == ["-x#0"]  # estado local nuevo: el hijo se volvió a crear


def test_recursive_component_renders_a_tree(mount, project):
    tree = """<script>
from fluxui import prop
from Tree import Tree
node = prop()
</script>
<Column>
  <Text>{node["n"]}</Text>
  {#each node.get("kids", []) as k (k["n"])}<Tree node={k} />{/each}
</Column>"""
    app = '<script>\nfrom Tree import Tree\n</script>\n<Tree node={{"n": "r", "kids": [{"n": "a", "kids": [{"n": "a1"}]}, {"n": "b"}]}} />'
    m = mount(project({"App.flux": app, "Tree.flux": tree}))
    assert texts(m) == ["r", "a", "a1", "b"]


def test_error_in_child_script_is_reported_and_row_skipped(mount, project, caplog):
    child = "<script>\nfrom fluxui import prop\nv = prop()\nif v.value == 2:\n    raise ValueError('dos')\n</script>\n<Text>{v}</Text>"
    app = "<script>\nfrom C import C\n</script>\n<Column>{#each [1, 2, 3] as v (v)}<C v={v} />{/each}</Column>"
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        m = mount(project({"App.flux": app, "C.flux": child}))
    assert "ValueError: dos" in caplog.text
    assert texts(m) == ["1", "3"]


def test_compile_errors_in_children_point_to_the_child_file(project):
    with pytest.raises(FluxError) as info:
        compile_file(project({"App.flux": "<script>\nfrom C import C\n</script>\n<C />", "C.flux": "<Text>{nada}</Text>"}))
    assert info.value.first.location.file.endswith("C.flux")


# -- temas ---------------------------------------------------------------------------


def test_theme_switch_updates_tokens_in_qml(mount, flux_app):
    m = mount('<Column class="c"><Text id="t" class="t">x</Text></Column>\n<style>.c { background: var(--surface); }\n.t { color: var(--primary); }</style>')
    label = find(m, "t")
    assert label.property("color") == QColor(theme.tokens["primary"])
    assert m.root.property("color") == QColor("#f5f6f8")
    theme.set("dark")
    assert label.property("color") == QColor(theme.tokens["primary"])
    assert m.root.property("color") == QColor("#14161a")
    theme.extend("dark", primary="#ff00ff")
    assert label.property("color") == QColor("#ff00ff")


def test_custom_theme_and_reactive_name(mount):
    theme.define("sepia", base="light", bg="#f4ecd8")
    m = mount("<script>\nfrom fluxui import theme\n</script>\n<Text id=\"t\">{theme.name}</Text>")
    assert find(m, "t").property("text") == "light"
    theme.set("sepia")
    assert find(m, "t").property("text") == "sepia"
    assert m.root.property("color") == QColor("#f4ecd8")


def test_unknown_token_is_a_warning_at_mount(flux_app, project):
    compiled = compile_file(project({"App.flux": '<Text class="t">x</Text>\n<style>.t { color: var(--brnad); }</style>'}))
    warnings = flux_app.check_tokens(compiled)
    assert len(warnings) == 1 and "--brnad" in warnings[0].message
    theme.extend(brnad="#000")
    assert flux_app.check_tokens(compiled) == []


def test_theme_validation():
    with pytest.raises(ValueError):
        theme.set("no-existe")
    with pytest.raises(ValueError):
        theme.extend(**{"Mal-Nombre": "#000"})
