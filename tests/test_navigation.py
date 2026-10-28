"""Navegación básica (lanzamiento.md, 25–27): secciones que se conservan, navigation(),
await push / back(valor), atrás con Alt+← y el ratón, before_leave, y {#hidden}."""
import tempfile
from pathlib import Path

import pytest

from janelkit.compiler import compile_source
from janelkit.diagnostics import JanelError
from janelkit.inspect import mount

LISTA = """<script>
from janelkit import navigation, state
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
from janelkit import before_leave, navigation, prop, state

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
from janelkit import on_mount, state
creada = state(True)
</script>
<flex><Text>personas</Text></flex>
"""

APP = """<script>
from janelkit import sections
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
        (d / f"{name}.janel").write_text(text, encoding="utf-8")
    with mount(d / "App.janel") as app:
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
from janelkit import inject, on_destroy, on_mount, state
n = state(0)
log = inject("log")
on_mount(lambda: log.append("mount"))
on_destroy(lambda: log.append("destroy"))
</script>
<flex label="campo" on:click={n += 1}><Text>{f"n={n}"}</Text></flex>
"""

OCULTO = """<script>
from janelkit import provide, state
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
    (d / "Campo.janel").write_text(CAMPO, encoding="utf-8")
    (d / "App.janel").write_text(OCULTO, encoding="utf-8")
    with mount(d / "App.janel") as app:
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
    with pytest.raises(JanelError, match=r"antes de cerrar el bloque \{#hidden\}"):
        compile_source("<script>\nx = True\n</script>\n<flex>{#hidden x}<Text>a</Text></flex>\n")


ELSE = """<script>
from janelkit import state
from Campo import Campo
oculto = state(False)
log = state([])
from janelkit import provide
provide("log", log.value)
</script>
<Window width={300} height={200}>
  <flex direction="column">
    {#hidden oculto}
      <Campo />
    {:else}
      <flex transition:fade={50}><Text>{"vacío"}</Text></flex>
    {/hidden}
  </flex>
</Window>
"""


def test_hidden_else_is_also_kept_and_transitions_finish_hidden():
    d = Path(tempfile.mkdtemp())
    (d / "Campo.janel").write_text(CAMPO, encoding="utf-8")
    (d / "App.janel").write_text(ELSE, encoding="utf-8")
    with mount(d / "App.janel") as app:
        o = app.namespace["oculto"]
        assert app.texts() == ["n=0"]  # {:else} aún no existe
        app.find("Campo", label="campo").click()
        o.value = True
        app.wait(0.15)  # la entrada de {:else} dura 50 ms
        assert app.texts() == ["vacío"]
        o.value = False
        app.wait(0.15)  # la salida de {:else} termina oculta
        assert app.texts() == ["n=1"] and app.get("log") == ["mount"]
        o.value = True
        app.wait(0.15)
        assert app.texts() == ["vacío"]


def test_else_is_not_allowed_in_key():
    with pytest.raises(JanelError, match=r"\{:else\} inesperada dentro de \{#key\}"):
        compile_source("<script>\nx = 1\n</script>\n<flex>{#key x}<Text>a</Text>{:else}<Text>b</Text>{/key}</flex>\n")


def test_pages_transition_animates_the_entering_page(app):
    s = secciones(app)
    nav = s["lista"]
    nav._container.setProperty("jkTransition", "slide")
    nav._container.setProperty("jkTransitionMs", 100)
    nav.push(nav.page.namespace["Detalle"], item="y")
    pagina = nav._pages[-1][1]
    assert pagina.opacity() < 1 and pagina.x() > 0  # entra desde la derecha
    app.wait(0.25)
    assert pagina.opacity() == 1 and pagina.x() == 0
    nav.pop()
    abajo = nav._pages[-1][1]
    assert abajo.x() < 0  # al volver, entra desde la izquierda
    app.wait(0.25)
    assert abajo.x() == 0 and abajo.opacity() == 1


def test_transition_on_pages_compiles_to_its_properties():
    src = "<script>\nfrom janelkit import pages\nnav = None\n</script>\n<Pages stack={nav} transition:slide={150} />\n"
    qml = compile_source(src).qml
    assert 'jkTransition: "slide"' in qml and "jkTransitionMs: 150" in qml


def test_leaving_can_be_awaited_to_chain_navigation(app):
    import asyncio

    nav, ns = detalle(app)
    ns["lenta"].value, ns["permitir"].value = True, False
    resultados = []

    async def ir():
        resultados.append(await nav.pop())

    app.application.run_until(ir())
    assert resultados == [False] and nav.current == "Detalle"
    ns["permitir"].value = True
    app.application.run_until(ir())
    assert resultados == [False, True] and nav.depth == 1
    assert app.application.run_until(asyncio.ensure_future(_await(nav.pop()))) is False  # en la primera, no hace nada


async def _await(x):
    return await x


def test_a_page_fits_its_window_and_its_scrolling_grid_wraps(tmp_path):
    """La página de <Sections> se estrecha con la ventana (su mínimo es el de su contenido,
    no su ancho natural) y una rejilla con wrap y overflow: auto reparte en filas."""
    (tmp_path / "Rejilla.janel").write_text("""<flex class="pagina">
  <flex class="barra"><Text>Título</Text><Spacer /><Button text="Nuevo" /></flex>
  <flex class="rejilla" label="rejilla">
    {#each list(range(12)) as i (i)}<flex class="ficha"><Text>{f"ficha {i}"}</Text></flex>{/each}
  </flex>
</flex>
<style>
.pagina { direction: column; flex: 1; }
.rejilla { flex: 1; flex-wrap: wrap; gap: 10px; overflow: auto; align-content: start; }
.ficha { width: 200px; height: 60px; }
</style>
""", encoding="utf-8")
    (tmp_path / "App.janel").write_text("""<script>
from janelkit import sections
from Rejilla import Rejilla
s = sections(a=Rejilla)
</script>
<Window width={800} height={600}>
  <flex class="app"><flex class="lateral" /><Sections of={s} /></flex>
</Window>
<style>
.app { flex: 1; }
.lateral { width: 200px; }
</style>
""", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        app.window.resize(800, 600)
        app.wait(0.1)
        boton = app.find("Button", text="Nuevo").item
        derecha = boton.mapToScene(boton.boundingRect().topRight()).x()
        assert derecha <= 800  # antes: la página medía lo que la rejilla en una sola fila
        rejilla = app.find("flex", label="rejilla").item
        assert rejilla.width() == pytest.approx(600)  # 800 - la lateral
        fila = [app.find("Text", text=f"ficha {i}").item for i in (0, 1, 2)]
        y = [t.mapToScene(t.boundingRect().topLeft()).y() for t in fila]
        assert y[0] == y[1] and y[2] > y[0]  # caben 2 por fila (200 + 10 + 200 + 10 + 200 > 600)


@pytest.mark.parametrize("css, esperado", [
    ("", (200, 0, 600, 600)),  # llena su <Sections>
    ("width: 400px; height: 300px;", (200, 0, 400, 300)),
    ("max-width: 400px; margin: 0 auto;", (300, 0, 400, 600)),  # centrada
    ("align-self: end; width: 100px;", (700, 0, 100, 600)),
    ("margin: 50px;", (250, 50, 500, 500)),
])  # fmt: skip
def test_the_root_of_a_page_adjusts_its_place_with_css(tmp_path, css, esperado):
    (tmp_path / "Pag.janel").write_text(f"""<flex class="pag"><Text>hola</Text></flex>
<style>
.pag {{ direction: column; {css} }}
</style>
""", encoding="utf-8")
    (tmp_path / "App.janel").write_text("""<script>
from janelkit import sections
from Pag import Pag
s = sections(a=Pag)
</script>
<Window width={800} height={600}>
  <flex class="app"><flex class="lateral" /><Sections of={s} /></flex>
</Window>
<style>
.app { flex: 1; }
.lateral { width: 200px; }
</style>
""", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        app.window.resize(800, 600)
        app.wait(0.1)
        pag = app.find("Text", text="hola").item.parentItem().parentItem()  # el lay y su caja
        pos = pag.mapToScene(pag.boundingRect().topLeft())
        assert (pos.x(), pos.y(), pag.width(), pag.height()) == esperado
