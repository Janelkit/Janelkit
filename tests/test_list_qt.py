"""<List>: lista virtualizada. Solo se crean (en Python y en Qt) las filas visibles."""
import time

import pytest
from conftest import click, visual_items
from PySide6.QtCore import QMetaObject

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError

APP = """<script>
from fluxui import state
items = state([{"id": i, "t": f"fila {i}", "done": False} for i in range(%d)])
removed = state([])
</script>
<Window width={300} height={200}>
  <List id="list" class="list">
    {#each items as it, i (it["id"])}
      <Row>
        <Text>{i}:{it["t"]}{"*" if it["done"] else ""}</Text>
        <Button id="del" on:click={removed.append(it["id"]); items.remove(it)}>x</Button>
      </Row>
    {/each}
  </List>
</Window>
<style>
.list { gap: 2px; padding: 4px; }
</style>
"""


def region(m):
    return m.instance.root.regions[0]


def visible_texts(m):
    """Textos de las filas en el orden en que se ven (ListView no ordena sus hijos)."""
    from PySide6.QtCore import QCoreApplication, QPointF

    # ListView crea y coloca los delegados en su siguiente pasada de disposición, que en una
    # app real llega con el siguiente fotograma; sin ventana visible hay que forzarla.
    for view in (i for i in visual_items(m) if i.inherits("QQuickListView")):
        QMetaObject.invokeMethod(view, "forceLayout")
    QCoreApplication.processEvents()
    labels = [i for i in visual_items(m) if i.inherits("QQuickLabel") and i.isVisible() and ":" in i.property("text")]
    labels.sort(key=lambda i: i.mapToScene(QPointF(0, 0)).y())
    return [i.property("text") for i in labels]


def test_only_visible_rows_are_created(mount, caplog):
    m = mount(APP % 1000)
    assert caplog.text == ""
    model = region(m).model
    assert len(model) == 1000
    created = model.materialized()
    assert 0 < created < 60  # ventana de 200 px: unas pocas filas, no 1000
    assert visible_texts(m)[:3] == ["0:fila 0", "1:fila 1", "2:fila 2"]


def test_scrolling_creates_rows_on_demand(mount, flux_app):
    m = mount(APP % 1000)
    view = next(i for i in visual_items(m) if i.inherits("QQuickListView"))
    before = region(m).model.materialized()
    QMetaObject.invokeMethod(view, "positionViewAtEnd")
    flux_app.qt_app.processEvents()
    assert region(m).model.materialized() > before
    assert "999:fila 999" in visible_texts(m)


def test_list_reconciles_like_each(mount):
    m = mount(APP % 5)
    items = m.instance.namespace["items"]
    items.value.insert(0, {"id": 99, "t": "nueva", "done": False})
    assert visible_texts(m)[:2] == ["0:nueva", "1:fila 0"]
    items.value[1]["done"] = True
    assert visible_texts(m)[1] == "1:fila 0*"
    items.value.reverse()
    assert visible_texts(m)[0] == "0:fila 4" and visible_texts(m)[-1] == "5:nueva"
    del items.value[0]
    assert visible_texts(m)[0] == "0:fila 3"
    items.value = []
    assert visible_texts(m) == []


def test_row_handlers_and_released_rows(mount):
    m = mount(APP % 5)
    ns = m.instance.namespace
    first = next(i for i in visual_items(m) if i.objectName() == "del")
    click(first)
    assert ns["removed"].value == [0] and len(ns["items"].value) == 4
    assert visible_texts(m)[0] == "0:fila 1"


def test_ten_thousand_rows_build_quickly(mount, flux_app):
    m = mount(APP % 0)
    items = m.instance.namespace["items"]
    data = [{"id": i, "t": f"fila {i}", "done": False} for i in range(10_000)]
    t0 = time.perf_counter()
    items.value = data
    flux_app.qt_app.processEvents()
    elapsed = (time.perf_counter() - t0) * 1000
    assert region(m).model.materialized() < 60
    assert elapsed < 400, f"{elapsed:.0f} ms"  # objetivo documentado: < 100 ms en una máquina normal


def test_list_requires_a_single_each():
    with pytest.raises(FluxError, match="exactamente un bloque"):
        compile_source("<List><Text>x</Text></List>")
    with pytest.raises(FluxError, match="no está disponible dentro de <List>"):
        compile_source("<script>\nxs = []\n</script>\n<List>{#each xs as x}<Text>{x}</Text>{:else}<Text>-</Text>{/each}</List>")


def test_bulk_changes_reset_once_and_keep_row_instances(mount):
    m = mount(APP % 300)
    reg = region(m)
    first = reg.rows[0]
    assert first.instance is not None  # visible: ya creada
    resets = []
    reg.model.modelReset.connect(lambda: resets.append(1))
    m.instance.namespace["items"].value.reverse()  # 300 movimientos: un solo reinicio
    assert resets == [1]
    assert reg.rows[-1] is first and first.instance is not None and not first.instance.disposed
    assert visible_texts(m)[0] == "0:fila 299"


def test_few_changes_stay_fine_grained(mount):
    m = mount(APP % 300)
    reg = region(m)
    resets = []
    reg.model.modelReset.connect(lambda: resets.append(1))
    items = m.instance.namespace["items"]
    items.value.insert(1, items.value.pop(0))  # una sola fila se mueve
    assert resets == []
    assert visible_texts(m)[:2] == ["0:fila 1", "1:fila 0"]


def test_bulk_removal_disposes_created_rows(mount):
    m = mount(APP % 300)
    reg = region(m)
    created = [r.instance for r in reg.rows if r.instance is not None]
    m.instance.namespace["items"].value = []
    assert all(inst.disposed for inst in created)
    assert reg.model.materialized() == 0
