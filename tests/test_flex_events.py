"""<flex> fase 3: eventos con propagación, prevent()/stop(), as, tabindex, disabled, title,
pointer-events y visibility. Ver docs/flex.md."""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtTest import QTest

from fluxui.compiler import compile_source
from fluxui.inspect import mount

FLEX = Path(__file__).parent.parent / "examples" / "flex"


@pytest.fixture
def app_from():
    apps = []

    def run(source: str, width=300, height=300):
        d = Path(tempfile.mkdtemp())
        (d / "App.flux").write_text(source, encoding="utf-8")
        ctx = mount(d / "App.flux")
        app = ctx.__enter__()
        apps.append(ctx)
        app.window.resize(width, height)
        app.wait(0.05)
        return app

    yield run
    for ctx in apps:
        ctx.__exit__(None, None, None)


def real_click(app, el, button=Qt.MouseButton.LeftButton, at=None):
    """Un clic real del ratón: en el centro del elemento, o en `at` (coordenadas del elemento)."""
    el.hover()
    pos = el._center() if at is None else el.item.mapToScene(QPointF(*at)).toPoint()
    QTest.mouseClick(app.window, button, Qt.KeyboardModifier.NoModifier, pos)
    app.wait(0.02)


LOG = """<script>
log = []
def stopper(event):
    log.append(("x", event.type))
    event.stop()
def keys(event):
    log.append(("k", event.key))
    if event.key == "a":
        event.prevent()
</script>
"""


def test_click_bubbles_and_stop_cuts_it(app_from):
    app = app_from(LOG + """<Column>
<flex label="fuera" padding={20} on:click={log.append(("fuera", event.type))} on:pointerdown={log.append(("fuera", event.type))}>
  <flex label="dentro" padding={10} on:click={log.append(("dentro", event.type))}><Text>d</Text>
    <flex label="cerrar" on:click={stopper}><Text>x</Text></flex>
  </flex>
  <Button text="btn" />
</flex>
</Column>""")
    log = app.get("log")
    real_click(app, app.find("flex", label="dentro"), at=(3, 3))  # en su relleno, fuera del ✕
    assert log == [("fuera", "pointerdown"), ("dentro", "click"), ("fuera", "click")]
    log.clear()
    real_click(app, app.find("flex", label="cerrar"))
    assert log == [("fuera", "pointerdown"), ("x", "click")]
    log.clear()
    # Un control de Qt se queda el clic (como antes); pointerdown sí llega, como en la web.
    real_click(app, app.find("Button"))
    assert log == [("fuera", "pointerdown")]
    log.clear()
    app.find("flex", label="dentro").click()  # inspect: como desde el teclado, también sube
    assert log == [("dentro", "click"), ("fuera", "click")]


def test_click_event_has_position_and_pointer(app_from):
    app = app_from("""<script>
got = []
</script>
<Column><flex label="caja" padding={30} on:click={got.append(event)}><Text>c</Text></flex></Column>""")
    caja = app.find("flex", label="caja")
    real_click(app, caja)
    ev = app.get("got")[0]
    assert ev.pointer == "mouse" and ev.button == "left"
    assert abs(ev.x - caja.item.width() / 2) < 1.5 and abs(ev.y - caja.item.height() / 2) < 1.5


def test_keydown_bubbles_from_focus_and_prevent_blocks_typing(app_from):
    app = app_from(LOG + """<Column><flex on:keydown={keys}><TextField label="campo" /></flex></Column>""")
    campo = app.find("TextField")
    campo.focus()
    QTest.keyClick(app.window, Qt.Key.Key_A)
    QTest.keyClick(app.window, Qt.Key.Key_B)
    QTest.keyClick(app.window, Qt.Key.Key_Down)
    app.wait(0.02)
    assert app.get("log") == [("k", "a"), ("k", "b"), ("k", "ArrowDown")]
    assert campo.item.property("text") == "b"


def test_wheel_prevent_stops_scrolling(app_from):
    app = app_from("""<script>
seen = []
def rueda(event):
    seen.append(event.dy)
    event.prevent()
</script>
<Column><flex class="zona" on:wheel={rueda}><Text>{"\\n".join(str(i) for i in range(80))}</Text></flex></Column>
<style>.zona { height: 100px; overflow: auto; }</style>""")
    zona = [e for e in app.elements() if e.tag == "flex"][0]
    flick = zona.item.property("fxScroller")
    pos = QPointF(zona._center())
    ev = QWheelEvent(pos, app.window.mapToGlobal(pos), QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QGuiApplication.sendEvent(app.window, ev)
    app.wait(0.05)
    assert app.get("seen") == [100.0]
    assert flick.property("contentY") == 0


def test_focus_blur_resize_and_hover_events(app_from):
    app = app_from("""<script>
from fluxui import state
log = []
wide = state(True)
</script>
<Column>
  <flex as="button" label="b" on:focus={log.append(("focus", event.reason))} on:blur={log.append(("blur", event.reason))}
        on:pointerenter={log.append(("enter", event.type))} on:pointerleave={log.append(("leave", event.type))}><Text>b</Text></flex>
  <flex class="medida" on:resize={log.append(("resize", event.width, event.height))} width={200 if wide else 100}><Text>m</Text></flex>
  <Button text="estrechar" on:click={wide = False} />
</Column>""")
    log = app.get("log")
    log.clear()
    b = app.find("flex", label="b")
    b.focus()
    QTest.keyClick(app.window, Qt.Key.Key_Tab)  # sale con Tab
    app.wait(0.02)
    assert log == [("focus", "code"), ("blur", "tab")]
    b.hover()
    b.unhover()
    app.find("Button").click()
    app.wait(0.05)
    assert ("enter", "pointerenter") in log and ("leave", "pointerleave") in log
    resizes = [e for e in log if e[0] == "resize"]
    assert len(resizes) == 1 and resizes[0][1] == 100


def test_contextmenu_with_right_click_and_menu_key(app_from):
    app = app_from(LOG + """<Column><flex as="button" label="z" padding={20} on:contextmenu={log.append(("z", event.type))}><Text>z</Text></flex></Column>""")
    z = app.find("flex", label="z")
    real_click(app, z, Qt.MouseButton.RightButton)
    z.focus()
    QTest.keyClick(app.window, Qt.Key.Key_Menu)
    app.wait(0.02)
    assert app.get("log") == [("z", "contextmenu"), ("z", "contextmenu")]


def test_roles_keyboard_tabindex_and_disabled(app_from):
    app = app_from(LOG + """<Column>
  <flex as="switch" label="s" on:click={log.append(("s", event.type))}><Text>s</Text></flex>
  <flex as="link" label="l" on:click={log.append(("l", event.type))}><Text>l</Text></flex>
  <flex label="t" tabindex={0}><Text>t</Text></flex>
  <flex label="nada"><Text>n</Text></flex>
  <flex as="button" label="off" disabled on:click={log.append(("off", event.type))} on:pointerdown={log.append(("off", event.type))}><Text>o</Text></flex>
</Column>""")
    s, link, t, nada, off = (app.find("flex", label=n) for n in ("s", "l", "t", "nada", "off"))
    assert s.prop("activeFocusOnTab") and link.prop("activeFocusOnTab") and t.prop("activeFocusOnTab")
    assert not nada.prop("activeFocusOnTab") and not off.prop("enabled")
    s.focus()
    QTest.keyClick(app.window, Qt.Key.Key_Space)
    QTest.keyClick(app.window, Qt.Key.Key_Return)  # Intro no activa una casilla/interruptor
    link.focus()
    QTest.keyClick(app.window, Qt.Key.Key_Space)  # Espacio no activa un enlace
    QTest.keyClick(app.window, Qt.Key.Key_Return)
    real_click(app, off)
    app.wait(0.02)
    assert app.get("log") == [("s", "click"), ("l", "click")]


def test_pointer_events_none_and_visibility_hidden(app_from):
    app = app_from(LOG + """<Column>
  <flex label="fuera" on:pointerdown={log.append(("fuera", event.type))}>
    <flex class="velo" label="velo" on:pointerdown={log.append(("velo", event.type))}><Text>v</Text></flex>
  </flex>
  <flex class="oculta" label="oculta"><Text>texto oculto</Text></flex>
  <Text>debajo</Text>
</Column>
<style>.velo { pointer-events: none; } .oculta { visibility: hidden; height: 40px; }</style>""")
    real_click(app, app.find("flex", label="velo"))
    assert app.get("log") == [("fuera", "pointerdown")]
    oculta = app.find("flex", label="oculta")
    assert oculta.visible and oculta.item.height() == 40
    assert oculta.item.property("fxLay").property("opacity") == 0


def test_title_and_accessibility_warning_compile():
    c = compile_source("""<Column>
  <flex as="button" title="Guarda el archivo" on:click={print}><Text>Guardar</Text></flex>
  <flex as="button" on:click={print}><Image src="x.png" /></flex>
  <flex as="button" label="Cerrar" on:click={print}><Image src="x.png" /></flex>
</Column>""")
    assert 'ToolTip.text: "Guarda el archivo"' in c.qml and "ToolTip.visible: hovered" in c.qml
    warns = [w.message for w in c.warnings if "lector de pantalla" in w.message]
    assert len(warns) == 1 and 'as="button"' in warns[0]


def test_invalid_role_is_an_error():
    from fluxui.diagnostics import FluxError

    with pytest.raises(FluxError, match="valor no válido para 'as'"):
        compile_source('<Column><flex as="botón" /></Column>')


def test_catalog_controls():
    with mount(FLEX / "src" / "App.flux") as app:
        app.window.resize(900, 640)
        app.wait(0.1)
        last = lambda: next(t for t in app.texts() if t.startswith("Última"))  # noqa: E731
        app.find("Boton", label="Guardar").focus()
        QTest.keyClick(app.window, Qt.Key.Key_Space)
        app.wait(0.02)
        assert last() == "Última acción: guardar"
        assert not app.find("Boton", label="Desactivado").enabled
        # Interruptor: Espacio lo cambia; el pomo se desplaza con transform.
        sw = app.find("Interruptor", label="Compacto")
        sw.focus()
        QTest.keyClick(app.window, Qt.Key.Key_Space)
        app.wait(0.3)
        assert app.get("compact") is True and sw.prop("checked") is True
        # Chip: el ✕ quita el chip sin elegirlo (event.stop()).
        real_click(app, app.find("flex", label="Quitar red"))
        assert list(app.get("chips")) == ["diseño", "datos", "texto"] and app.get("chosen") == "diseño"
        real_click(app, app.find("Chip", label="datos"))
        assert app.get("chosen") == "datos"
        # Menú: clic derecho lo abre; las flechas y la Intro eligen.
        real_click(app, app.find("flex", label="Zona con menú contextual"), Qt.MouseButton.RightButton)
        app.wait(0.05)
        for key in (Qt.Key.Key_Down, Qt.Key.Key_Down, Qt.Key.Key_Return):
            QTest.keyClick(app.window, key)
        app.wait(0.05)
        assert last() == "Última acción: menú: Renombrar" and app.get("menu_open") is False
