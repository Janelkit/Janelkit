"""Lo que no se ve espera: los bindings de {#hidden}, de las secciones que no se muestran
y de las páginas de debajo no se recalculan; se ponen al día (una vez) al volver a verse.
Los effect y temporizadores del script siguen funcionando."""
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


@pytest.fixture
def project(tmp_path):
    def write(files: dict[str, str]) -> Path:
        for name, text in files.items():
            (tmp_path / name).write_text(text, encoding="utf-8")
        return tmp_path / "App.janel"
    return write


def test_hidden_waits_and_catches_up_once(project):
    app_file = project({"App.janel": f"""<script>
{CONTADOR}
oculto = state(False)
n = state(0)
</script>
<flex direction="column">
  {{#hidden oculto}}
    <Text>{{f"n={{visto(n)}}"}}</Text>
    {{#each list(range(n)) as i (i)}}<Text>{{f"fila {{i}}"}}</Text>{{/each}}
  {{/hidden}}
</flex>
"""})
    with mount(app_file) as app:
        veces, n, oculto = app.get("veces"), app.namespace["n"], app.namespace["oculto"]
        assert veces == [0]
        oculto.value = True
        for i in range(1, 6):
            n.value = i
        app.process()
        assert veces == [0]  # oculto: no se recalcula
        oculto.value = False
        app.process()
        assert veces == [0, 5]  # al verse, una vez y con el último valor
        assert "n=5" in app.texts() and "fila 4" in app.texts()
        n.value = 6
        assert veces == [0, 5, 6]


def test_else_branch_and_nested_hidden(project):
    app_file = project({"App.janel": f"""<script>
{CONTADOR}
fuera = state(False)
dentro = state(False)
n = state(0)
</script>
<flex direction="column">
  {{#hidden fuera}}
    {{#hidden dentro}}<Text>{{f"a{{visto(n)}}"}}</Text>{{:else}}<Text>{{f"b{{visto(-n)}}"}}</Text>{{/hidden}}
  {{/hidden}}
</flex>
"""})
    with mount(app_file) as app:
        veces, ns = app.get("veces"), app.namespace
        assert veces == [0]
        ns["dentro"].value = True  # se ve la rama else (y se crea)
        app.process()
        assert veces == [0, 0]
        ns["fuera"].value = True  # el de fuera se cierra: las dos ramas esperan
        ns["n"].value = 3
        ns["dentro"].value = False  # la de dentro se «abre», pero la de fuera sigue cerrada
        app.process()
        assert veces == [0, 0]
        ns["fuera"].value = False
        app.process()
        assert veces[2:] == [3] and "a3" in app.texts()  # la rama a; la else (oculta) sigue esperando
        ns["dentro"].value = True
        app.process()
        assert veces[3:] == [-3] and "b-3" in app.texts()


def test_script_effects_and_timers_keep_running_while_hidden(project):
    app_file = project({
        "Reloj.janel": """<script>
from janelkit import effect, interval, inject, state
n = inject("n")
ticks = inject("ticks")
vistos = inject("vistos")
effect(lambda: vistos.append(n.value))
interval(20, lambda: ticks.set(ticks.peek() + 1))
</script>
<Text>{n}</Text>
""",
        "App.janel": """<script>
from janelkit import provide, state
from Reloj import Reloj
oculto = state(False)
n = state(0)
ticks = state(0)
vistos = []
provide("n", n)
provide("ticks", ticks)
provide("vistos", vistos)
</script>
<flex>{#hidden oculto}<Reloj />{/hidden}</flex>
""",
    })
    with mount(app_file) as app:
        ns = app.namespace
        ns["oculto"].value = True
        ns["n"].value = 7
        antes = ns["ticks"].value
        app.wait(0.15)
        assert app.get("vistos") == [0, 7] and ns["ticks"].value > antes


PAGINAS = {
    "Inicio.janel": f"""<script>
{CONTADOR}
from janelkit import inject
n = inject("n")
</script>
<flex><Text>{{f"inicio {{visto(n)}}"}}</Text></flex>
""",
    "Otra.janel": "<Text>otra</Text>\n",
}


def test_pages_below_and_other_sections_wait(project):
    app_file = project({**PAGINAS, "App.janel": """<script>
from janelkit import provide, sections, state
from Inicio import Inicio
from Otra import Otra
n = state(0)
provide("n", n)
s = sections(a=Inicio, b=Otra)
</script>
<Window><Sections of={s} /></Window>
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
