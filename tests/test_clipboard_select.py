"""Portapapeles (fluxui.clipboard) y texto seleccionable (<Text selectable>, user-select: text)."""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from fluxui import clipboard
from fluxui.inspect import mount


@pytest.fixture
def app_from():
    apps = []

    def run(source: str):
        d = Path(tempfile.mkdtemp())
        (d / "App.flux").write_text(source, encoding="utf-8")
        ctx = mount(d / "App.flux")
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
from fluxui import clipboard
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
    QGuiApplication.clipboard().setText("desde otra aplicación")  # cambio que no pasa por FluxUI
    app.process()
    assert app.find("Text", id="pegado").text == "desde otra aplicación"


def test_selectable_text_selects_with_mouse_and_keyboard_and_copies(app_from):
    app = app_from("""<script>
from fluxui import state
sel = state(True)
</script>
<Column>
  <Text id="a" selectable={sel}>Pedido 4815 enviado</Text>
  <Text id="b" class="libre">Referencia ABC-123</Text>
  <Text id="c">Texto normal</Text>
  <Button text="fijo" on:click={sel = False} />
</Column>
<style>.libre { user-select: text; }</style>""")
    a, b, c = (app.find("Text", id=i).item for i in "abc")
    edit = a.property("fxSelect")
    assert edit is not None and b.property("fxSelect") is not None
    assert c.property("fxSelect") is None  # un texto normal no paga nada
    assert a.property("color").alpha() == 0  # lo dibuja la copia seleccionable
    assert edit.property("width") == a.width() and edit.property("height") == a.height()

    # Arrastrar con el ratón selecciona.
    start = a.mapToScene(QPointF(1, a.height() / 2)).toPoint()
    end = a.mapToScene(QPointF(a.width() - 1, a.height() / 2)).toPoint()
    QTest.mousePress(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(app.window, end)
    QTest.mouseRelease(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    app.wait(0.02)
    assert edit.property("selectedText") == "Pedido 4815 enviado"
    # Ctrl+C copia; Ctrl+A con el foco en el texto selecciona todo.
    clipboard.clear()
    QTest.keyClick(app.window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    app.wait(0.02)
    assert clipboard.paste() == "Pedido 4815 enviado"
    b.property("fxSelect").forceActiveFocus()
    QTest.keyClick(app.window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(app.window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    app.wait(0.02)
    assert clipboard.paste() == "Referencia ABC-123"

    app.find("Button").click()  # selectable pasa a False: vuelve a ser un texto normal
    assert edit.property("visible") is False and a.property("color").alpha() == 255


def test_selectable_markdown_keeps_links(app_from):
    app = app_from("""<script>
links = []
</script>
<Column><Text selectable format="markdown" on:link={links.append}>Ver [el pedido](https://ejemplo.com/p/1)</Text></Column>""")
    label = app.find("Text").item
    edit = label.property("fxSelect")
    assert "el pedido" in edit.property("text")
    edit.linkActivated.emit("https://ejemplo.com/p/1")
    app.process()
    assert app.get("links") == ["https://ejemplo.com/p/1"]


def test_selectable_with_line_height_copies_plain_text(app_from):
    app = app_from("""<Column><Text selectable class="lh">{"uno & <dos>" + chr(10) + "tres"}</Text></Column>
<style>.lh { line-height: 1.6; }</style>""")
    label = app.find("Text").item
    edit = label.property("fxSelect")
    # El interlineado se aplica a la copia: la segunda línea empieza a 1,6 líneas. (Que cuadre
    # al píxel con el <Text> se comprobó con fuentes reales; sin ventana, la fuente de reserva
    # mide distinto en Text y TextEdit también sin line-height.)
    from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QRectF

    rect = QMetaObject.invokeMethod(edit, "positionToRectangle", Q_RETURN_ARG(QRectF), Q_ARG(int, len("uno & <dos>") + 1))
    assert abs(rect.y() - 1.6 * rect.height()) < 1
    edit.forceActiveFocus()
    QTest.keyClick(app.window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(app.window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    app.wait(0.02)
    assert clipboard.paste() == "uno & <dos>\ntres"


def test_click_on_selectable_text_still_presses_its_row_but_dragging_selects(app_from):
    app = app_from("""<script>
log = []
</script>
<Column><flex as="button" label="fila" on:click={log.append("clic")}><Text selectable>Texto dentro de la fila</Text></flex></Column>""")
    label = app.find("Text").item
    at = lambda x: label.mapToScene(QPointF(x, label.height() / 2)).toPoint()  # noqa: E731
    QTest.mouseClick(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(20))
    app.wait(0.02)
    assert app.get("log") == ["clic"]
    QTest.mousePress(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(2))
    QTest.mouseMove(app.window, at(label.width() - 2))
    QTest.mouseRelease(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(label.width() - 2))
    app.wait(0.02)
    assert app.get("log") == ["clic"]  # arrastrar selecciona, no pulsa
    assert label.property("fxSelect").property("selectedText") != ""


def test_selectable_with_ellipsis_is_clipped(app_from):
    app = app_from("""<Column><Text selectable class="e">Un texto muy largo que no cabe en una sola línea de esta ventana estrecha</Text></Column>
<style>.e { white-space: nowrap; text-overflow: ellipsis; }</style>""")
    edit = app.find("Text").item.property("fxSelect")
    assert edit.property("clip") is True
