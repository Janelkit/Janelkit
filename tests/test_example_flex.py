"""examples/flex: elementos construidos solo con <flex> (docs/flex.md, catálogo de validación)."""
from pathlib import Path

import pytest

from janelkit.inspect import mount

FLEX = Path(__file__).parent.parent / "examples" / "flex"


@pytest.fixture
def catalog():
    with mount(FLEX / "src" / "App.janel") as app:
        yield app


def columns(app, width):
    app.window.setWidth(width)
    app.wait(0.05)
    cards = app.find_all("Tarjeta")
    assert len(cards) == 8
    tops = [c.item.mapToItem(None, 0, 0).y() for c in cards]
    return tops.count(tops[0])


def test_grid_goes_from_four_to_two_to_one_column(catalog):
    assert columns(catalog, 900) == 4
    assert columns(catalog, 500) == 2
    assert columns(catalog, 300) == 1
    assert columns(catalog, 900) == 4


def test_cards_in_a_row_share_the_width(catalog):
    columns(catalog, 900)
    widths = {round(c.item.width(), 1) for c in catalog.find_all("Tarjeta")}
    assert len(widths) == 1 and widths.pop() > 200


def test_toolbar_groups_wrap_and_buttons_work(catalog):
    catalog.window.setWidth(1400)  # cabe todo en una línea
    catalog.wait(0.05)
    title = catalog.find("Text", text="Catálogo de flex")
    copiar = catalog.find("Button", text="Copiar")
    assert title.item.mapToItem(None, 0, 0).x() < copiar.item.mapToItem(None, 0, 0).x()
    # space-between: el último grupo llega al borde derecho de la barra (menos su relleno)
    share = catalog.find("Button", text="Compartir")
    right = share.item.mapToItem(None, share.item.width(), 0).x()
    assert right == pytest.approx(1400 - 12 - 8, abs=1)
    # al estrechar, los grupos saltan de línea en lugar de salirse de la ventana
    catalog.window.setWidth(400)
    catalog.wait(0.05)
    right = share.item.mapToItem(None, share.item.width(), 0).x()
    assert right <= 400 and share.item.mapToItem(None, 0, 0).y() > copiar.item.mapToItem(None, 0, 0).y()
    copiar.click()
    assert "Última acción: copiar" in catalog.texts()
