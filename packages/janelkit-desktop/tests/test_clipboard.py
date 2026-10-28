"""Portapapeles (janelkit_desktop.clipboard): copiar, pegar y pegar reactivo."""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

from janelkit.inspect import mount
from janelkit_desktop import clipboard


@pytest.fixture
def app_from():
    apps = []

    def run(source: str):
        d = Path(tempfile.mkdtemp())
        (d / "App.janel").write_text(source, encoding="utf-8")
        ctx = mount(d / "App.janel")
        app = ctx.__enter__()
        apps.append(ctx)
        app.window.resize(400, 300)
        app.wait(0.05)
        return app

    yield run
    for ctx in apps:
        ctx.__exit__(None, None, None)


def test_copy_paste_and_paste_is_reactive(app_from):
    app = app_from("""<script>
from janelkit_desktop import clipboard
</script>
<Column>
  <Button text="Copiar" on:click={clipboard.copy("https://ejemplo.com/42")} />
  <Button text="Pegar" enabled={bool(clipboard.paste())} />
  <Text id="pegado">{clipboard.paste() or "(vacío)"}</Text>
</Column>""")
    clipboard.clear()
    app.process()
    assert app.find("Text", id="pegado").text == "(vacío)"
    assert app.find("Button", text="Pegar").item.property("enabled") is False
    app.find("Button", text="Copiar").click()
    assert QGuiApplication.clipboard().text() == "https://ejemplo.com/42"
    assert clipboard.paste() == "https://ejemplo.com/42"
    assert app.find("Text", id="pegado").text == "https://ejemplo.com/42"
    assert app.find("Button", text="Pegar").item.property("enabled") is True
    QGuiApplication.clipboard().setText("desde otra aplicación")  # cambio que no pasa por JanelKit
    app.process()
    assert app.find("Text", id="pegado").text == "desde otra aplicación"
