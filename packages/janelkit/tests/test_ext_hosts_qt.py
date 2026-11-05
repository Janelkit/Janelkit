"""Anfitriones (janelkit.ext.Host): un objeto del script monta componentes dentro de un elemento
`.qml` (raíz JkDeck, propiedad JkHost). Es lo que usa janelkit-router; aquí, con uno mínimo."""
import logging

import pytest

from janelkit.compiler import compile_file
from janelkit.inspect import mount

MAZO = """import QtQuick
import Janel

JkDeck {
    property JkHost of
    property string titulo: ""
    property bool jkInterno: false
    signal jkAviso()
}
"""

UNO = '''
from janelkit.ext import Host, ask_to_leave, is_component


class Uno(Host):
    """Monta todos sus componentes y muestra uno."""

    def __init__(self, *components):
        assert all(is_component(c) for c in components)
        self.components = components
        self.children = []
        self.log = []
        self.container = None

    def attach(self, container):
        self.container = container
        self.log.append("attach")
        for i, component in enumerate(self.components):
            self.children.append(container.mount(component, context={"pos": i}, nombre=f"n{i}"))
        self.show(0)

    def show(self, index):
        for i, child in enumerate(self.children):
            child.visibility.set_open(i == index)
        self.container.item.setProperty("currentIndex", index)

    def detach(self, container):
        self.log.append("detach")
        while self.children:
            self.children.pop().dispose()

    def leave(self, done):
        guards = [g for c in self.children for g in c.leave_guards()]
        return ask_to_leave(guards, lambda: done.append(True), lambda: done.append(False))
'''

HOJA = """<script>
from janelkit import before_leave, inject, on_destroy, prop
nombre = prop("")
pos = inject("pos")
n = inject("n")
veces = []
cerradas = []
salir = [True]


def visto(x):
    veces.append(x)
    return x


on_destroy(lambda: cerradas.append(nombre.value))
before_leave(lambda: salir[0])
</script>
<text>{nombre} {pos} {visto(n)}</text>
"""

APP = """<script>
from janelkit import provide, state
from services.uno import Uno
from Mazo import Mazo
from Hoja import Hoja
n = state(0)
provide("n", n)
on = state(True)
mazo = Uno(Hoja, Hoja)
</script>
<window>{#if on}<Mazo of={mazo} transition:fade={120} titulo="x" />{/if}</window>
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "services" / "uno.py").write_text(UNO, encoding="utf-8")
    (tmp_path / "Mazo.qml").write_text(MAZO, encoding="utf-8")
    (tmp_path / "Hoja.janel").write_text(HOJA, encoding="utf-8")
    (tmp_path / "App.janel").write_text(APP, encoding="utf-8")
    return tmp_path / "App.janel"


def test_a_deck_element_takes_the_host_attribute_and_transitions(project):
    qml = compile_file(project).qml
    assert 'jkTransition: "fade"' in qml and "jkTransitionMs: 120" in qml
    assert "jkFlex: 1" in qml  # un mazo crece sin pedirlo
    assert 'titulo: "x"' in qml and "of:" not in qml  # of= no se escribe: se le pasa el elemento al anfitrión


def test_jk_members_of_a_qml_element_are_internal(project, tmp_path):
    (tmp_path / "Otro.janel").write_text(
        "<script>\nfrom Mazo import Mazo\n</script>\n<window><Mazo jkInterno={True} /></window>\n", encoding="utf-8")
    with pytest.raises(Exception, match="jkInterno"):
        compile_file(tmp_path / "Otro.janel")


def test_mount_creates_children_with_context_and_their_own_visibility(project):
    with mount(project) as app:
        mazo, n = app.get("mazo"), app.namespace["n"]
        assert mazo.log == ["attach"] and [c.name for c in mazo.children] == ["Hoja", "Hoja"]
        assert app.texts() == ["n0 0 0"]  # solo se ve el primero
        first, second = (c.instance.namespace for c in mazo.children)
        assert (first["pos"], second["pos"]) == (0, 1)  # context= llega a inject del propio hijo
        assert second["veces"] == [0]
        n.value = 1
        n.value = 2
        app.process()
        assert first["veces"][-1] == 2
        assert second["veces"] == [0]  # oculto: espera
        mazo.show(1)
        app.process()
        assert second["veces"] == [0, 2] and app.texts() == ["n1 1 2"]


def test_unmounting_the_element_detaches_and_disposes_the_children(project):
    with mount(project) as app:
        mazo = app.get("mazo")
        hojas = [c.instance.namespace for c in mazo.children]
        app.namespace["on"].value = False
        app.process()
        assert mazo.log == ["attach", "detach"] and mazo.children == []
        assert [h["cerradas"] for h in hojas] == [["n0"], ["n1"]]
        app.namespace["on"].value = True
        app.process()
        assert mazo.log == ["attach", "detach", "attach"] and app.texts() == ["n0 0 0"]


def test_leave_guards_of_the_children(project):
    with mount(project) as app:
        mazo = app.get("mazo")
        done = []
        assert mazo.leave(done) is True and done == [True]
        mazo.children[1].instance.namespace["salir"][0] = False
        done.clear()
        assert mazo.leave(done) is False and done == [False]


def test_a_host_attribute_that_gets_something_else_is_reported(tmp_path, caplog):
    (tmp_path / "Mazo.qml").write_text(MAZO, encoding="utf-8")
    (tmp_path / "App.janel").write_text(
        "<script>\nfrom Mazo import Mazo\nx = 3\n</script>\n<window><Mazo of={x} /></window>\n", encoding="utf-8")
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        with mount(tmp_path / "App.janel") as app:
            app.process()
    assert "of: 'x' es int; espera un anfitrión (janelkit.ext.Host)" in caplog.text
