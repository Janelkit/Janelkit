"""bind: a un atributo gestionado por un descriptor que define __jk_bind__ (los campos de un store)."""
import logging

from janelkit.inspect import mount

CAMPO = '''
from janelkit import state


class Campo:
    """Atributo reactivo sin .value que solo deja escribir por bind: si `abierto`."""

    def __init__(self, abierto=True):
        self.abierto = abierto

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.setdefault("_" + self.name, state("")).value

    def __jk_bind__(self, obj, value):
        if not self.abierto:
            raise PermissionError(f"{self.name} no admite bind:")
        obj.__dict__.setdefault("_" + self.name, state("")).value = value
        obj.escrituras.append((self.name, value))


class Ficha:
    nombre = Campo()
    clave = Campo(abierto=False)

    def __init__(self):
        self.escrituras = []


ficha = Ficha()
'''

APP = """<script>
from servicio import ficha
</script>
<window><column>
  <textfield bind:value={ficha.nombre} placeholder="nombre" />
  <textfield bind:value={ficha.clave} placeholder="clave" />
  <text>{ficha.nombre}</text>
</column></window>
"""


def test_bind_writes_through_the_descriptor_and_reads_back(tmp_path):
    (tmp_path / "servicio.py").write_text(CAMPO, encoding="utf-8")
    (tmp_path / "App.janel").write_text(APP, encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        ficha = app.namespace["ficha"]
        app.find(placeholder="nombre").type("Ana")
        assert ficha.escrituras == [("nombre", "Ana")] and ficha.nombre == "Ana"
        assert app.texts() == ["Ana"]


def test_the_descriptor_can_refuse_and_the_error_is_reported(tmp_path, caplog):
    (tmp_path / "servicio.py").write_text(CAMPO, encoding="utf-8")
    (tmp_path / "App.janel").write_text(APP, encoding="utf-8")
    with caplog.at_level(logging.ERROR, logger="janelkit"):
        with mount(tmp_path / "App.janel") as app:
            app.find(placeholder="clave").type("x")
            assert app.namespace["ficha"].escrituras == []
    assert "bind: 'ficha.clave': clave no admite bind:" in caplog.text
