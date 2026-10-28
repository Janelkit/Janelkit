"""examples/preferencias: lo que se cambia sigue ahí al cerrar y volver a abrir (persisted)."""
import json
from pathlib import Path

import pytest

from janelkit import storage, theme
from janelkit.inspect import mount

APP = Path(__file__).parent.parent / "examples" / "preferencias" / "src" / "App.janel"


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv(storage.DATA_ENV, str(tmp_path))  # la misma carpeta en los dos montajes
    yield tmp_path
    theme.set("light")


def test_preferences_and_notes_survive_a_restart(data):
    with mount(APP) as app:
        assert app.texts()[:2] == ["Hola", "Has abierto esta aplicación 1 vez."]
        app.find("TextField", label="Nombre").type("Ana")
        app.find("RadioGroup").choose("Oscuro")
        app.find("Slider").slide(18)
        nueva = app.find("TextField", label="Nueva nota")
        nueva.type("Comprar pan").submit()
        nueva.type("Llamar a Luis").submit()
        app.find("Checkbox", label="Comprar pan").check()
        nueva.type("a medias").key("Escape")  # Escape vacía el campo (on:keydown)
        assert nueva.item.property("text") == ""
        assert theme.name == "dark"
    # Cerrar escribe lo pendiente.
    assert json.loads((data / "prefs.nombre.json").read_text(encoding="utf-8")) == "Ana"

    theme.set("light")
    with mount(APP) as app:  # otra sesión
        assert app.texts()[:2] == ["Hola, Ana", "Has abierto esta aplicación 2 veces."]
        assert theme.name == "dark"
        assert app.find("Slider").item.property("value") == 18
        notas = [c.label for c in app.find_all("Checkbox")]
        assert notas == ["Comprar pan", "Llamar a Luis"]
        assert app.find("Checkbox", label="Comprar pan").item.property("checked") is True
        app.find("Button", text="Restablecer").click()
        assert theme.name == "light" and app.find_all("Checkbox") == []

    with mount(APP) as app:
        assert app.texts()[:2] == ["Hola", "Has abierto esta aplicación 3 veces."]
