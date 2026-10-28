"""Navegación básica (lanzamiento.md, 25–27): secciones que se conservan, navigation(),
await push / back(valor), atrás con Alt+← y el ratón, before_leave, y {#hidden}."""
import tempfile
from pathlib import Path

import pytest

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError
from fluxui.inspect import mount

LISTA = """<script>
from fluxui import navigation, state
from Detalle import Detalle

nav = navigation()
q = state("")
elegido = state("-")


async def elegir():
    elegido.value = await nav.push(Detalle, item="x")
</script>
<flex direction="column">
  <Text>{f"lista {q} {elegido}"}</Text>
  <flex label="abrir" on:click={elegir()}><Text>abrir</Text></flex>
</flex>
"""

DETALLE = """<script>
import asyncio
from fluxui import before_leave, navigation, prop, state

item = prop("")
nav = navigation()
sucio = state(False)
lenta = state(False)  # la pregunta tarda (como un dialogs.confirm)
permitir = state(True)
preguntas = state(0)


@before_leave
def salir():
    preguntas.value += 1
    if lenta.value:
        return responder()
    return not sucio.value


async def responder():
    await asyncio.sleep(0.01)
    return permitir.value
</script>
<flex label="detalle" tabindex={0} direction="column">
  <Text>{f"detalle {item}"}</Text>
  <flex label="elegir" on:click={nav.back("rojo")}><Text>elegir</Text></flex>
</flex>
"""

PERSONAS = """<script>
from fluxui import on_mount, state
creada = state(True)
</script>
<flex><Text>personas</Text></flex>
"""

APP = """<script>
from fluxui import sections
from Lista import Lista
from Personas import Personas

s = sections(lista=Lista, personas=Personas)
</script>
<Window width={400} height={300}>
  <flex direction="column">
    <Text>{f"seccion {s.current}"}</Text>
    <Sections of={s} />
  </flex>
</Window>
"""


@pytest.fixture
def app():
    d = Path(tempfile.mkdtemp())
    for name, text in {"Lista": LISTA, "Detalle": DETALLE, "Personas": PERSONAS, "App": APP}.items():
        (d / f"{name}.flux").write_text(text, encoding="utf-8")
    with mount(d / "App.flux") as app:
        yield app


def secciones(app):
    return app.namespace["s"]


def detalle(app):
    nav = secciones(app)["lista"]
    nav.page.namespace["elegir"]  # existe la lista
    app.find("flex", label="abrir").click()
    app.wait(0.05)
    assert nav.current == "Detalle"
    return nav, nav.page.namespace


def test_a_section_is_created_when_first_shown_and_kept_when_hidden(app):
    s = secciones(app)
    assert s["personas"].page is None  # aún no se ha mostrado
    s["lista"].page.namespace["q"].value = "abc"
    s.show("personas")
    app.wait(0.05)
    assert app.texts() == ["seccion personas", "personas"]  # la lista está oculta
    lista = s["lista"].page
    s.show("lista")
    app.wait(0.05)
    assert s["lista"].page is lista and not lista.disposed
    assert app.texts() == ["seccion lista", "lista abc -", "abrir"]


def test_navigation_gives_the_page_its_own_stack(app):
    s = secciones(app)
    assert s["lista"].page.namespace["nav"] is s["lista"]
    s.show("personas")
    assert s.stack is s["personas"]


def test_await_push_receives_the_value_of_back(app):
    nav, _ = detalle(app)
    app.find("flex", label="elegir").click()
    app.wait(0.05)
    assert nav.depth == 1 and "lista  rojo" in app.texts()


def test_a_page_discarded_without_back_gives_none(app):
    nav, _ = detalle(app)
    nav.pop()
    app.wait(0.05)
    assert "lista  None" in app.texts()


def test_alt_left_goes_back_in_the_visible_stack(app):
    nav, _ = detalle(app)
    app.find("Detalle", label="detalle").focus()
    app.key("Alt+Left")
    app.wait(0.05)
    assert nav.depth == 1


def test_mouse_back_button_goes_back(app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    nav, _ = detalle(app)
    pages = nav._container
    centro = pages.mapToScene(pages.boundingRect().center()).toPoint()
    QTest.mouseClick(app.window, Qt.MouseButton.BackButton, Qt.KeyboardModifier.NoModifier, QPoint(centro.x(), centro.y()))
    app.wait(0.05)
    assert nav.depth == 1


def test_before_leave_can_keep_the_page(app):
    nav, ns = detalle(app)
    ns["sucio"].value = True
    nav.pop()
    app.find("Detalle", label="detalle").focus()
    app.key("Alt+Left")
    assert nav.current == "Detalle" and ns["preguntas"].value == 2
    ns["sucio"].value = False
    nav.pop()
    assert nav.depth == 1


def test_an_async_before_leave_decides_later(app):
    nav, ns = detalle(app)
    ns["lenta"].value, ns["permitir"].value = True, False
    nav.back("rojo")
    app.wait(0.1)
    assert nav.current == "Detalle"
    ns["permitir"].value = True
    nav.back("azul")
    app.wait(0.1)
    assert nav.depth == 1 and "lista  azul" in app.texts()


def test_before_leave_also_guards_closing_the_window(app):
    _, ns = detalle(app)
    ns["sucio"].value = True
    app.window.close()
    app.wait(0.05)
    assert app.window.isVisible() and ns["preguntas"].value == 1


def test_switching_sections_does_not_ask(app):
    _, ns = detalle(app)
    ns["sucio"].value = True
    secciones(app).show("personas")
    assert ns["preguntas"].value == 0  # la sección se conserva: no se pierde nada


# -- {#hidden} -------------------------------------------------------------------------

CAMPO = """<script>
from fluxui import inject, on_destroy, on_mount, state
n = state(0)
log = inject("log")
on_mount(lambda: log.append("mount"))
on_destroy(lambda: log.append("destroy"))
</script>
<flex label="campo" on:click={n += 1}><Text>{f"n={n}"}</Text></flex>
"""

OCULTO = """<script>
from fluxui import provide, state
from Campo import Campo
oculto = state(True)
log = state([])
provide("log", log.value)
</script>
<Window width={300} height={200}>
  <flex direction="column">
    {#hidden oculto}<Campo />{/hidden}
    {#hidden oculto}<Text visible={True}>con visible propio</Text>{/hidden}
    <Text>fin</Text>
  </flex>
</Window>
"""


@pytest.fixture
def oculto():
    d = Path(tempfile.mkdtemp())
    (d / "Campo.flux").write_text(CAMPO, encoding="utf-8")
    (d / "App.flux").write_text(OCULTO, encoding="utf-8")
    with mount(d / "App.flux") as app:
        yield app


def test_hidden_content_is_created_when_first_shown_and_then_only_hidden(oculto):
    o = oculto.namespace["oculto"]
    assert oculto.texts() == ["fin"] and oculto.get("log") == []  # no se crea mientras está oculto
    o.value = False
    oculto.wait(0.05)
    assert oculto.texts() == ["n=0", "con visible propio", "fin"]
    oculto.find("Campo", label="campo").click()
    o.value = True
    oculto.wait(0.05)
    assert oculto.texts() == ["fin"] and oculto.get("log") == ["mount"]  # oculto, no destruido
    o.value = False
    oculto.wait(0.05)
    assert oculto.texts() == ["n=1", "con visible propio", "fin"] and oculto.get("log") == ["mount"]


def test_unclosed_hidden_block_is_reported():
    with pytest.raises(FluxError, match=r"antes de cerrar el bloque \{#hidden\}"):
        compile_source("<script>\nx = True\n</script>\n<flex>{#hidden x}<Text>a</Text></flex>\n")
