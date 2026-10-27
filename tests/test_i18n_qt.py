"""Internacionalización: t(), plurales, cambio de idioma en caliente, formatos y derecha a izquierda."""
import logging
import time
from datetime import date

import pytest
from conftest import find, texts

from fluxui import i18n, t
from fluxui.i18n import I18nError

APP = """<script>
from fluxui import state, t, i18n
n = state(1)
name = state("Ana")
</script>
<Window width={300} height={200}>
  <Column>
    <Row id="row"><Text id="a">{t("hello", name=name)}</Text><Spacer /><Text id="b">{t("tasks", n=n)}</Text></Row>
    <Text>{i18n.number(12345.5, 1)}</Text>
  </Column>
</Window>
"""


@pytest.fixture(autouse=True)
def catalogs(tmp_path):
    (tmp_path / "es.json").write_text(
        '{"hello": "Hola, {name}", "tasks": {"zero": "Sin tareas", "one": "{n} tarea", "other": "{n} tareas"}, "only_es": "solo es"}',
        encoding="utf-8",
    )
    (tmp_path / "en.json").write_text('{"hello": "Hello, {name}", "tasks": {"one": "{n} task", "other": "{n} tasks"}}', encoding="utf-8")
    (tmp_path / "ar.json").write_text('{"hello": "مرحبا {name}", "tasks": {"other": "{n} مهام"}}', encoding="utf-8")
    i18n.load(tmp_path)
    i18n.set("es")
    yield
    i18n.reset()


def test_translate_with_params_plurals_and_fallback(caplog):
    assert t("hello", name="Ana") == "Hola, Ana"
    assert [t("tasks", n=k) for k in (0, 1, 3)] == ["Sin tareas", "1 tarea", "3 tareas"]
    i18n.set("en")
    assert t("tasks", n=0) == "0 tasks"  # sin forma "zero": "other"
    assert t("only_es") == "solo es"  # reserva: el idioma por defecto
    with caplog.at_level(logging.WARNING, logger="fluxui"):
        assert t("missing") == "missing"
    assert "falta la traducción de 'missing'" in caplog.text
    with pytest.raises(I18nError, match="idioma sin catálogo: 'fr'"):
        i18n.set("fr")


def test_language_switch_updates_the_view(mount):
    m = mount(APP)
    assert texts(m) == ["Hola, Ana", "1 tarea", "12.345,5"]
    i18n.set("en")
    assert texts(m) == ["Hello, Ana", "1 task", "12,345.5"]
    m.instance.namespace["n"].value = 2
    assert texts(m)[1] == "2 tasks"


def settle(flux_app):
    """Los layouts se recolocan en su siguiente pasada: dejar correr el bucle un momento."""
    for _ in range(5):
        flux_app.process_events()
        time.sleep(0.01)


def test_rtl_language_mirrors_the_layout(mount, flux_app):
    m = mount(APP)
    a, row = find(m, "a"), find(m, "row")
    i18n.set("ar")
    settle(flux_app)
    assert i18n.rtl and texts(m)[0] == "مرحبا Ana"
    assert a.x() > row.width() / 2  # el primer elemento de la fila pasa a la derecha
    i18n.set("es")
    settle(flux_app)
    assert a.x() < row.width() / 2


def test_formats():
    assert i18n.number(1234567.5) == "1.234.567,5" and i18n.number(2.5, 2) == "2,50"
    assert i18n.date(date(2026, 10, 26)) == "26/10/26"
    i18n.set("en")
    assert i18n.number(1234567.5) == "1,234,567.5" and i18n.date(date(2026, 10, 26)) == "10/26/26"
    assert i18n.currency(9.5, "€") == "€9.50"
