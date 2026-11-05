"""Lo que no se ve espera también con la navegación: las páginas de debajo y las secciones
que no se muestran no recalculan su plantilla, `is_visible()` lo dice y `inspect` encuentra
la página visible. (Venían de las pruebas del núcleo antes de que la navegación saliera.)"""
from pathlib import Path

import pytest

from janelkit.inspect import mount

CONTADOR = """
from janelkit import state
veces = []


def visto(x):
    veces.append(x)
    return x
"""

PAGINAS = {
    "Inicio.janel": f"""<script>
{CONTADOR}
from janelkit import inject
n = inject("n")
</script>
<flex><text>{{f"inicio {{visto(n)}}"}}</text></flex>
""",
    "Otra.janel": "<text>otra</text>\n",
}

PANEL = """<script>
from janelkit import interval, is_visible, state
visible = is_visible()
ticks = state(0)

@interval(10, when=visible)
def muestrear():
    ticks.value += 1
</script>
<flex><text>panel {visible}</text></flex>
"""


@pytest.fixture
def project(tmp_path):
    def write(files: dict[str, str]) -> Path:
        for name, text in files.items():
            (tmp_path / name).write_text(text, encoding="utf-8")
        return tmp_path / "App.janel"
    return write


def test_pages_below_and_other_sections_wait(project):
    app_file = project({**PAGINAS, "App.janel": """<script>
from janelkit import provide, state
from janelkit_router import sections, Sections
from Inicio import Inicio
from Otra import Otra
n = state(0)
provide("n", n)
s = sections(a=Inicio, b=Otra)
</script>
<window><Sections of={s} /></window>
"""})
    with mount(app_file) as app:
        s, n = app.get("s"), app.namespace["n"]
        veces = s["a"].page.namespace["veces"]
        assert veces == [0]
        s["a"].push(app.namespace["Otra"])
        app.process()
        n.value = 1
        n.value = 2
        assert veces == [0]  # la página de debajo espera
        s["a"].pop()
        app.process()
        assert veces == [0, 2] and "inicio 2" in app.texts()
        s.show("b")
        app.process()
        n.value = 3
        assert veces == [0, 2]  # su sección no se ve
        s.show("a")
        app.process()
        assert veces == [0, 2, 3]


def test_sections_and_pages_below_are_not_visible_and_their_timers_wait(project):
    app_file = project({"Panel.janel": PANEL, "Otra.janel": "<text>otra</text>\n", "App.janel": """<script>
from janelkit import is_visible
from janelkit_router import sections, Sections
from Panel import Panel
from Otra import Otra
raiz = is_visible()
s = sections(a=Panel, b=Otra)
</script>
<window><Sections of={s} /></window>
"""})
    with mount(app_file) as app:
        s = app.get("s")
        panel = s["a"].page.namespace
        assert app.get("raiz") is True  # la raíz de la ventana siempre se ve
        assert panel["visible"].value is True and panel["muestrear"].active
        app.wait(0.1)
        assert panel["ticks"].value > 0

        s.show("b")
        app.process()
        assert panel["visible"].value is False and not panel["muestrear"].active
        quieto = panel["ticks"].value
        app.wait(0.1)
        assert panel["ticks"].value == quieto

        s.show("a")
        app.process()
        assert panel["visible"].value is True and panel["muestrear"].active
        app.wait(0.1)
        assert panel["ticks"].value > quieto

        s["a"].push(app.namespace["Otra"])  # la página de debajo tampoco se ve
        app.process()
        assert panel["visible"].value is False and not panel["muestrear"].active
        s["a"].pop()
        app.process()
        assert panel["visible"].value is True and "panel True" in app.texts()


def test_inspect_finds_a_section_page_whose_root_is_a_builtin(project):
    app_file = project({"Otra.janel": "<text>otra</text>\n", "App.janel": """<script>
from janelkit_router import sections, Sections
from Otra import Otra
s = sections(b=Otra)
</script>
<window><Sections of={s} /></window>
"""})
    with mount(app_file) as app:
        assert app.texts() == ["otra"]
        assert app.find("Otra").text == "otra" and app.find("text").text == "otra"
