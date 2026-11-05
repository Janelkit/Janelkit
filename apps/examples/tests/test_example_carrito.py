"""apps/examples/carrito: un store estricto que comparten dos ventanas, con registro y persistencia."""
import json
from pathlib import Path

import pytest

from janelkit.inspect import mount
from janelkit_store import StoreError

APP = Path(__file__).resolve().parents[1] / "carrito" / "src" / "App.janel"


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("JANELKIT_DATA_DIR", str(tmp_path))
    return tmp_path


def test_both_windows_share_the_cart(data):
    with mount(APP) as app:
        app.find(label="Añadir Pan").click()
        app.find(label="Añadir Pan").click()
        app.find(label="Añadir Café").click()
        app.find("button", text="Carrito (3) · 6.90 €").click()
        (ventana,) = app.windows()
        assert "Carrito · 3 unidades" in ventana.texts() and "Total: 6.90 €" in ventana.texts()
        ventana.find(label="Quitar Pan").click()
        app.process()
        assert app.find("button", text="Carrito (2) · 5.70 €")  # la principal lo ve al momento
        assert app.texts()[app.texts().index("Registro") + 1] == "Carrito.quitar: lineas"


def test_views_cannot_write_the_cart_directly(data):
    with mount(APP) as app:
        carrito = app.namespace["carrito"]
        with pytest.raises(StoreError, match="solo se escribe dentro de sus métodos"):
            carrito.lineas.append({"id": "x"})
        app.find("button", text="Carrito (0) · 0.00 €").click()
        (ventana,) = app.windows()
        ventana.find(placeholder="Nota para el pedido").type("Sin bolsa")
        assert carrito.nota == "Sin bolsa"  # nota admite bind:


def test_the_cart_is_saved(data):
    with mount(APP) as app:
        app.find(label="Añadir Fruta").click()
    guardado = json.loads((data / "carrito.json").read_text(encoding="utf-8"))
    assert [(l["id"], l["cantidad"]) for l in guardado["lineas"]] == [("fruta", 1)]
    with mount(APP) as app:
        assert app.find("button", text="Carrito (1) · 2.30 €")
