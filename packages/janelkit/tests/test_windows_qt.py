"""Ventanas secundarias con open_window: props, eventos, contexto, tema propio y cierre."""
from pathlib import Path

import pytest
from janelkit.testing import find
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor

from janelkit import theme

SETTINGS = """<script>
from janelkit import prop, event, state, inject
user = prop()
saved = event()
draft = state("")
session = inject("session", "sin sesión")

def save():
    saved.emit(draft.value or user.value)
</script>
<Window title="Ajustes" width={300} height={200}>
  <Column>
    <Text id="who">{user}·{session}</Text>
    <TextField id="name" bind:value={draft} />
    <Button id="save" on:click={save}>Guardar</Button>
  </Column>
</Window>
"""

APP = """<script>
from janelkit import state, open_window, provide
from components.Settings import Settings
user = state("ana")
saved = state([])
win = state(None)
provide("session", "S1")

def open_settings(**extra):
    win.value = open_window(Settings, user=user, on_saved=saved.value.append, **extra)
</script>
<Column><Text>principal</Text></Column>
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


def open_settings(m, **extra):
    m.instance.namespace["open_settings"](**extra)
    window = m.instance.namespace["win"].value
    return window, window._mounted


def test_props_events_and_context(mount, project, janel_app):
    m = mount(project({"App.janel": APP, "components/Settings.janel": SETTINGS}))
    window, mounted = open_settings(m)
    assert window.is_open and mounted in janel_app.mounted
    assert find(mounted, "who").property("text") == "ana·S1"  # prop y contexto del que la abre
    m.instance.namespace["user"].value = "bea"  # el state pasado como prop sigue siendo reactivo
    assert find(mounted, "who").property("text") == "bea·S1"
    window.instance.namespace["draft"].value = "carla"
    window.instance.namespace["save"]()
    assert m.instance.namespace["saved"].value == ["carla"]
    assert mounted.root.transientParent() is m.root


def test_closing_by_the_user_unmounts(mount, project, janel_app):
    m = mount(project({"App.janel": APP, "components/Settings.janel": SETTINGS}))
    window, mounted = open_settings(m)
    mounted.root.close()  # como pulsar la X
    janel_app.process_events()
    assert not window.is_open and mounted not in janel_app.mounted


def test_window_closes_with_its_opener(mount, project, janel_app):
    m = mount(project({"App.janel": APP, "components/Settings.janel": SETTINGS}))
    window, mounted = open_settings(m)
    janel_app.unmount(m)
    assert not window.is_open and mounted not in janel_app.mounted


def test_own_theme_and_modal(mount, project, janel_app):
    m = mount(project({"App.janel": APP, "components/Settings.janel": SETTINGS}))
    window, mounted = open_settings(m, theme="dark", modal=True)
    from PySide6.QtCore import Qt

    assert mounted.root.modality() == Qt.WindowModality.WindowModal
    dark_bg = QColor(theme.tokens_of("dark")["bg"])
    assert mounted.root.property("color") == dark_bg  # tema oscuro en esta ventana...
    assert m.root.property("color") == QColor(theme.tokens["bg"])  # ...y claro en la principal
    button = mounted.root.findChild(QObject, "save")
    assert button.property("jkBackground") == QColor(theme.tokens_of("dark")["surface"])


def test_unknown_props_are_rejected(mount, project):
    m = mount(project({"App.janel": APP, "components/Settings.janel": SETTINGS}))
    with pytest.raises(TypeError, match="no declara la prop 'colour'"):
        open_settings(m, colour="red")


def test_child_components_inside_a_themed_window_use_its_theme(mount, project, janel_app):
    badge = '<Text id="badge" class="b">x</Text>\n<style>.b { color: var(--primary); }</style>'
    settings = SETTINGS.replace(
        "from janelkit import prop, event, state, inject", "from janelkit import prop, event, state, inject\nfrom components.Badge import Badge"
    ).replace('<Text id="who">', '<Badge />\n    <Text id="who">')
    m = mount(project({"App.janel": APP, "components/Settings.janel": settings, "components/Badge.janel": badge}))
    window, mounted = open_settings(m, theme="dark")
    label = find(mounted, "badge")
    assert label.property("jkColor") == QColor(theme.tokens_of("dark")["primary"])
