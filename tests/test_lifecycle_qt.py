"""Ciclo de vida (on_mount, on_destroy, efectos con limpieza), contexto (provide/inject) y referencias."""
import logging
from pathlib import Path

import pytest
from conftest import find, texts

from janelkit import effect, on_mount, provide, ref, state
from janelkit.compiler import compile_source

CHILD = """<script>
from janelkit import prop, on_mount, on_destroy, effect, inject
import tests_lifecycle_log as log
name = prop()
theme = inject("tema", "claro")
depth = inject("profundidad", 0)

@on_mount
def mounted():
    log.EVENTS.append(("mount", name.value))
    return lambda: log.EVENTS.append(("cleanup", name.value))

on_destroy(lambda: log.EVENTS.append(("destroy", name.value)))

def watch():
    log.EVENTS.append(("effect", name.value))
    return lambda: log.EVENTS.append(("effect-cleanup", name.value))

effect(watch)
</script>
<Text>{name}:{theme}:{depth}</Text>
"""

APP = """<script>
from janelkit import state, provide, on_mount
import tests_lifecycle_log as log
from components.Child import Child
items = state(["a", "b"])
provide("tema", "oscuro")

@on_mount
def mounted():
    log.EVENTS.append(("mount", "app"))
</script>
<Column>
  {#each items as it (it)}
    <Child name={it} />
  {/each}
</Column>
"""


@pytest.fixture
def log(monkeypatch):
    import sys
    import types

    module = types.ModuleType("tests_lifecycle_log")
    module.EVENTS = []
    monkeypatch.setitem(sys.modules, "tests_lifecycle_log", module)
    return module.EVENTS


@pytest.fixture
def project(tmp_path):
    def make(files: dict[str, str]) -> Path:
        for rel, text in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return tmp_path / "App.janel"

    return make


def test_on_mount_runs_after_the_view_exists_children_first(mount, project, log):
    mount(project({"App.janel": APP, "components/Child.janel": CHILD}))
    mounts = [e for e in log if e[0] == "mount"]
    assert mounts == [("mount", "a"), ("mount", "b"), ("mount", "app")]
    assert log.index(("effect", "a")) < log.index(("mount", "a"))  # el script corre antes que la vista


def test_dynamic_rows_mount_and_destroy_with_cleanups(mount, project, log):
    m = mount(project({"App.janel": APP, "components/Child.janel": CHILD}))
    items = m.instance.namespace["items"]
    log.clear()
    items.value.append("c")
    assert ("mount", "c") in log
    log.clear()
    items.value.remove("a")
    # Lo registrado después se libera antes: limpieza de on_mount, efecto, on_destroy.
    assert log == [("cleanup", "a"), ("effect-cleanup", "a"), ("destroy", "a")]


def test_unmounting_the_app_destroys_everything(mount, project, log, janel_app):
    m = mount(project({"App.janel": APP, "components/Child.janel": CHILD}))
    log.clear()
    janel_app.unmount(m)
    assert {e for e in log if e[0] == "destroy"} == {("destroy", "a"), ("destroy", "b")}


def test_inject_reads_the_nearest_provider_or_default(mount, project, log):
    m = mount(project({"App.janel": APP, "components/Child.janel": CHILD}))
    assert texts(m) == ["a:oscuro:0", "b:oscuro:0"]


def test_provide_shadows_for_a_subtree(mount, project, log):
    middle = """<script>
from janelkit import provide, inject
from components.Child import Child
provide("profundidad", inject("profundidad", 0) + 1)
provide("tema", "sepia")
</script>
<Column><Child name="m" /></Column>
"""
    app = APP.replace("<Child name={it} />", "<Child name={it} />\n    <Middle />").replace(
        "from components.Child import Child", "from components.Child import Child\nfrom components.Middle import Middle"
    )
    m = mount(project({"App.janel": app, "components/Child.janel": CHILD, "components/Middle.janel": middle}))
    assert texts(m) == ["a:oscuro:0", "m:sepia:1", "b:oscuro:0", "m:sepia:1"]


def test_lifecycle_functions_outside_a_component_explain_themselves():
    with pytest.raises(RuntimeError, match="solo puede llamarse mientras se ejecuta el <script>"):
        on_mount(lambda: None)
    with pytest.raises(RuntimeError, match="provide"):
        provide("x", 1)


def test_missing_provider_without_default_is_an_error(mount, caplog):
    with pytest.raises(LookupError, match="ningún componente antecesor provee 'sesion'"):
        mount("<script>\nfrom janelkit import inject\ns = inject('sesion')\n</script>\n<Text>x</Text>")


def test_error_in_on_mount_is_reported(mount, caplog):
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        mount("<script>\nfrom janelkit import on_mount\n@on_mount\ndef boom():\n    raise ValueError('mal')\n</script>\n<Text>x</Text>")
    assert "error en on_mount (boom): ValueError: mal" in caplog.text


def test_effect_cleanup_runs_before_rerun_and_on_dispose():
    n = state(0)
    seen = []

    def body():
        value = n.value
        seen.append(("run", value))
        return lambda: seen.append(("clean", value))

    e = effect(body)
    n.value = 1
    e.dispose()
    assert seen == [("run", 0), ("clean", 0), ("run", 1), ("clean", 1)]


# -- referencias -------------------------------------------------------------------
REFS = """<script>
from janelkit import state, ref, on_mount
field = ref()
row_ref = ref()
show = state(True)
focused = state(False)

@on_mount
def start():
    field.focus()
    focused.value = True
</script>
<Column>
  <TextField id="f" ref={field} value="hola" />
  {#if show}
    <Text id="t" ref={row_ref}>x</Text>
  {/if}
</Column>
"""


def test_ref_points_to_the_element_and_is_released(mount):
    m = mount(REFS)
    ns = m.instance.namespace
    assert ns["field"].value is find(m, "f")
    assert ns["focused"].value is True  # on_mount ya ve la referencia
    assert ns["row_ref"].value is find(m, "t")
    ns["show"].value = False
    assert ns["row_ref"].value is None and not ns["row_ref"].exists
    ns["show"].value = True
    assert ns["row_ref"].value is find(m, "t")


def test_ref_methods(mount):
    m = mount(REFS)
    field = m.instance.namespace["field"]
    field.select_all()
    assert find(m, "f").property("selectedText") == "hola"
    with pytest.raises(TypeError, match="no admite selectAll"):
        m.instance.namespace["row_ref"].select_all()


def test_ref_is_reactive():
    r = ref()
    seen = []
    effect(lambda: seen.append(r.value))
    r._attach("item")
    r._detach("otro")  # no es el actual: se ignora
    r._detach("item")
    assert seen == [None, "item", None]


def test_ref_must_name_a_script_ref():
    from janelkit.diagnostics import JanelError

    with pytest.raises(JanelError, match="ref necesita el nombre"):
        compile_source("<Text ref={1}>x</Text>")
    with pytest.raises(JanelError, match="variable de \\{#each\\}"):
        compile_source("<script>\nxs = [1]\n</script>\n<Column>{#each xs as x}<Text ref={x}>x</Text>{/each}</Column>")


def test_ref_to_something_else_is_reported(mount, caplog):
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        mount("<script>\nr = 3\n</script>\n<Text ref={r}>x</Text>")
    assert "ref: 'r' es int; declara r = ref()" in caplog.text
