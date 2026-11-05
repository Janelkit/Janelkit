"""Stores en una aplicación: una instancia por sesión, compartida por vistas y ventanas."""
import json
import logging
import sys

import pytest

from janelkit.inspect import mount

TIENDA = '''
from janelkit import computed
from janelkit_store import field, store


@store(strict=True, persist="tienda")
class Carrito:
    items: list[dict] = []
    nota: str = field("", bind=True, persist=False)
    codigo: str = ""

    @computed
    def total(self):
        return sum(i["precio"] for i in self.items)

    def agregar(self, nombre, precio):
        self.items.append({"nombre": nombre, "precio": precio})


@store
class Libre:
    marcas: list = []


@store
class Documento:
    texto: str = ""
    abiertos = []  # no es un campo: lo comparten todas (para la prueba)

    def setup(self, key):
        self.texto = f"doc {key}"
        Documento.abiertos.append(key)

    def teardown(self):
        Documento.abiertos.remove(self.texto[4:])
'''

LINEA = """<script>
from janelkit_store import use
from tienda import Carrito
carrito = use(Carrito)
</script>
<text>{len(carrito.items)} · {carrito.total}</text>
"""

VISTA_DOC = """<script>
from janelkit import prop
from janelkit_store import use
from tienda import Documento
ruta = prop("")
doc = use(Documento, key=ruta.value)
</script>
<text>{doc.texto}</text>
"""

APP = """<script>
from janelkit import open_window, state
from janelkit_store import use
from tienda import Carrito, Libre
from Linea import Linea
from VistaDoc import VistaDoc
carrito = use(Carrito)
libre = use(Libre)
abierto = state(True)
</script>
<window><column>
  <Linea />
  <Linea />
  <textfield bind:value={carrito.nota} placeholder="nota" />
  <textfield bind:value={carrito.codigo} placeholder="codigo" />
  <button on:click={carrito.agregar("pan", 2)}>Añadir</button>
  {#if abierto}<VistaDoc ruta="a" /><VistaDoc ruta="a" />{/if}
</column></window>
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("JANELKIT_DATA_DIR", str(tmp_path / "datos"))
    (tmp_path / "tienda.py").write_text(TIENDA, encoding="utf-8")
    (tmp_path / "Linea.janel").write_text(LINEA, encoding="utf-8")
    (tmp_path / "VistaDoc.janel").write_text(VISTA_DOC, encoding="utf-8")
    (tmp_path / "App.janel").write_text(APP, encoding="utf-8")
    return tmp_path / "App.janel"


def test_every_view_gets_the_same_instance(project):
    with mount(project) as app:
        app.find("button", text="Añadir").click()
        assert app.texts().count("1 · 2") == 2  # las dos vistas lo ven
        carrito = app.namespace["carrito"]
        assert app.store(type(carrito)) is carrito
        lineas = [c for c in app.find_all("Linea")]
        assert len(lineas) == 2
        assert [m.action for m in app.mutations()] == ["agregar"]


def test_each_mount_starts_with_new_instances(project):
    with mount(project) as app:
        app.find("button", text="Añadir").click()
        primero = app.namespace["carrito"]
    with mount(project) as app:
        assert app.namespace["carrito"] is not primero
        assert app.mutations() == []


def test_persist_saves_public_fields_and_reads_them_back(project, tmp_path):
    with mount(project) as app:
        app.find("button", text="Añadir").click()
        app.find(placeholder="nota").type("sin gluten")
        app.wait(0.4)
        guardado = json.loads((tmp_path / "datos" / "tienda.json").read_text(encoding="utf-8"))
        assert guardado == {"items": [{"nombre": "pan", "precio": 2}], "codigo": ""}  # nota: persist=False
    with mount(project) as app:
        carrito = app.namespace["carrito"]
        assert carrito.items == [{"nombre": "pan", "precio": 2}] and carrito.nota == ""


def test_bind_writes_bindable_fields_and_reports_the_others(project, caplog):
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        with mount(project) as app:
            carrito = app.namespace["carrito"]
            app.find(placeholder="nota").type("x")
            app.find(placeholder="codigo").type("y")
            assert carrito.nota == "x" and carrito.codigo == ""
            assert [m.action for m in app.mutations()] == ["bind:nota"]
    assert "codigo no admite bind:" in caplog.text


def test_keyed_instances_are_shared_and_released_with_their_last_view(project):
    with mount(project) as app:
        Documento = sys.modules["tienda"].Documento
        assert Documento.abiertos == ["a"] and app.texts().count("doc a") == 2  # una para las dos vistas
        app.namespace["abierto"].value = False
        app.process()
        assert Documento.abiertos == []  # teardown al desmontarse la última


def test_outside_writes_in_a_non_strict_store_are_logged_after_the_event(project):
    with mount(project) as app:
        libre = app.namespace["libre"]
        libre.marcas.append(1)
        libre.marcas.append(2)
        app.process()
        log = app.mutations()
        assert [(m.store, m.action, [c.field for c in m.changes]) for m in log] == [("Libre", None, ["marcas"])]


def test_the_log_env_var_writes_each_mutation(project, monkeypatch, caplog):
    monkeypatch.setenv("JANELKIT_STORE_LOG", "1")
    with caplog.at_level(logging.INFO, logger="janelkit_store"):
        with mount(project) as app:
            app.find("button", text="Añadir").click()
    assert "Carrito.agregar: items" in caplog.text


def test_effects_created_by_a_store_end_with_the_session(project, tmp_path):
    (tmp_path / "reloj.py").write_text('''
from janelkit import interval
from janelkit_store import store


@store
class Reloj:
    tics: int = 0
    timer = None

    def arrancar(self):
        Reloj.timer = interval(5, self.tic)

    def tic(self):
        self.tics += 1
''', encoding="utf-8")
    (tmp_path / "App.janel").write_text("<script>\nfrom janelkit_store import use\nfrom reloj import Reloj\nr = use(Reloj)\n</script>\n<window />",
                                        encoding="utf-8")
    with mount(project) as app:
        r = app.namespace["r"]
        r.arrancar()
        app.wait(0.05)
        assert r.tics > 0 and type(r).timer.active
    assert not type(r).timer.active  # era del store: se para al terminar la sesión
