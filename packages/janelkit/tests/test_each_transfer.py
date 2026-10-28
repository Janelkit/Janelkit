"""Traslado de filas entre {#each} (lenguaje.md, «Trasladar filas entre listas»): una fila
que sale de una lista y entra en otra de la misma declaración, con la misma clave y en
el mismo cambio, conserva sus componentes (estado, foco) en vez de recrearse."""
import tempfile
from pathlib import Path

import pytest

from janelkit.inspect import mount

FICHA = """<script>
from janelkit import event, inject, on_destroy, on_mount, prop, state

n = prop("")
col = prop("")
abierta = state(False)
log = inject("log")
quitar = event()
on_mount(lambda: log.append(f"mount {n.value}"))
on_destroy(lambda: log.append(f"destroy {n.value}"))
</script>
<flex class="ficha" label={n} tabindex={0}>
  <Text>{f"{n} en {col}" + (" abierta" if abierta else "")}</Text>
  <flex label={f"abrir {n}"} on:click={abierta = not abierta}><Text>abrir</Text></flex>
  <flex label={f"quitar {n}"} on:click={quitar.emit(n)}><Text>x</Text></flex>
</flex>
<style>
.ficha { direction: column; height: 40px; }
</style>
"""

SCRIPT = """<script>
from janelkit import batch, provide, state
from Ficha import Ficha

listas = state({"a": ["uno", "dos"], "b": [], "otra": []})
log = state([])
quitadas = state([])
provide("log", log.value)


def mover(n, desde, hacia, destino_primero=False):
    with batch():
        if destino_primero:
            listas.value[hacia].insert(0, n)
            listas.value[desde].remove(n)
        else:
            listas.value[desde].remove(n)
            listas.value[hacia].insert(0, n)
</script>
"""

# La misma declaración {#each} para las columnas "a" y "b"; "otra" es otra declaración.
CAJAS = SCRIPT + """<Window width={600} height={400}>
  <flex>
    {#each ["a", "b"] as c (c)}
      <flex label={c} direction="column" width={200}>
        {#each listas[c] as n (n)}
          <Ficha n={n} col={c} on:quitar={quitadas.append(f"{n}@{c}")} />
        {/each}
      </flex>
    {/each}
    <flex label="otra" direction="column" width={150}>
      {#each listas["otra"] as n (n)}<Ficha n={n} col="otra" />{/each}
    </flex>
  </flex>
</Window>
"""

LISTAS = SCRIPT + """<Window width={600} height={400}>
  <flex>
    {#each ["a", "b"] as c (c)}
      <List label={c} width={200} height={300}>
        {#each listas[c] as n (n)}
          <Ficha n={n} col={c} on:quitar={quitadas.append(f"{n}@{c}")} />
        {/each}
      </List>
    {/each}
    <flex label="otra" direction="column" width={150}>
      {#each listas["otra"] as n (n)}<Ficha n={n} col="otra" />{/each}
    </flex>
  </flex>
</Window>
"""


def montar(app_source: str):
    d = Path(tempfile.mkdtemp())
    (d / "Ficha.janel").write_text(FICHA, encoding="utf-8")
    (d / "App.janel").write_text(app_source, encoding="utf-8")
    return mount(d / "App.janel")


@pytest.fixture(params=["cajas", "listas"])
def app(request):
    with montar(CAJAS if request.param == "cajas" else LISTAS) as app:
        yield app


def texto(app, n):
    return next(t for t in app.texts() if t.startswith(f"{n} en "))


def mover(app, *args, **kwargs):
    app.namespace["mover"](*args, **kwargs)
    app.wait(0.3)  # <List animate> no, pero ListView crea las filas al pintar


@pytest.mark.parametrize("destino_primero", [False, True])
def test_a_moved_row_keeps_its_component_state(app, destino_primero):
    app.find("flex", label="abrir uno").click()
    assert texto(app, "uno") == "uno en a abierta"
    mover(app, "uno", "a", "b", destino_primero=destino_primero)
    assert texto(app, "uno") == "uno en b abierta"  # estado conservado, prop del padre nuevo
    assert app.get("log") == ["mount uno", "mount dos"]  # ni destroy ni otro on_mount
    mover(app, "uno", "b", "a", destino_primero=destino_primero)
    assert texto(app, "uno") == "uno en a abierta"
    assert app.get("log") == ["mount uno", "mount dos"]


def test_events_and_props_follow_the_new_parent(app):
    mover(app, "uno", "a", "b")
    app.find("flex", label="quitar uno").click()
    assert app.get("quitadas") == ["uno@b"]


def test_a_removed_row_is_destroyed_at_the_end_of_the_change(app):
    app.namespace["listas"].value["a"].remove("dos")  # sin batch: es un cambio por sí solo
    assert app.get("log") == ["mount uno", "mount dos", "destroy dos"]
    assert "dos" not in " ".join(app.texts())


def test_another_declaration_does_not_receive_the_row(app):
    app.find("flex", label="abrir uno").click()
    mover(app, "uno", "a", "otra")
    assert texto(app, "uno") == "uno en otra"  # recreada: sin su estado
    log = app.get("log")  # la nueva se monta al crearse; la vieja se libera al terminar el cambio
    assert log[:2] == ["mount uno", "mount dos"] and sorted(log[2:]) == ["destroy uno", "mount uno"]


def test_the_same_key_in_two_lists_at_once_is_two_rows(app):
    app.find("flex", label="abrir uno").click()
    app.namespace["listas"].value["b"].append("uno")  # copia, no movimiento
    app.wait(0.3)
    assert sorted(t for t in app.texts() if t.startswith("uno en ")) == ["uno en a abierta", "uno en b"]


def test_the_moved_row_keeps_the_focus(app):
    app.find("Ficha", label="uno").focus()
    mover(app, "uno", "a", "b")
    app.wait(0.1)
    from janelkit.inspect import Element

    focused = app.window.activeFocusItem()
    assert focused is not None and Element(app, focused).label == "uno"
    assert texto(app, "uno") == "uno en b"


def test_no_leaks_after_many_moves(app):
    from janelkit.runtime import component

    for i in range(100):
        mover_rapido = app.namespace["mover"]
        mover_rapido("uno", "a", "b") if i % 2 == 0 else mover_rapido("uno", "b", "a", destino_primero=True)
    app.wait(0.3)
    raiz = app.mounted.instance
    fichas = [c for c in raiz.children if c.compiled.file.endswith("Ficha.janel")]
    assert len(fichas) == 2 and not component._parked
    assert app.get("log") == ["mount uno", "mount dos"]


def test_a_row_not_yet_created_by_list_moves_without_errors():
    fuente = LISTAS.replace('"a": ["uno", "dos"]', '"a": ["uno", "dos"] + [f"n{i}" for i in range(40)]')
    with montar(fuente) as app:
        assert "mount n39" not in app.get("log")  # fuera de la vista: <List> no la creó
        mover(app, "n39", "a", "b")
        assert texto(app, "n39") == "n39 en b"
        assert app.get("log").count("mount n39") == 1
