"""Control del desplazamiento en <List>: follow, on:top/on:bottom, ref.scroll_to_*,
y las piezas de un chat: texto con Markdown, on:link y eventos de activación de la ventana."""
from conftest import find, visual_items
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QCoreApplication, QMetaObject, QPointF

from fluxui.compiler import compile_source

CHAT = """<script>
from fluxui import state, ref
msgs = state([{"id": i, "t": f"mensaje {i}"} for i in range(%d)])
tops = state(0)
bottoms = state(0)
pos = state({})
lista = ref()

def prepend(n):
    first = msgs.value[0]["id"] if msgs.value else 0
    msgs.value[0:0] = [{"id": first - n + k, "t": f"mensaje {first - n + k}"} for k in range(n)]

def append():
    last = msgs.value[-1]["id"] if msgs.value else 0
    msgs.value.append({"id": last + 1, "t": f"mensaje {last + 1}"})
</script>
<Window width={300} height={200}>
  <List id="list" follow ref={lista} on:top={tops += 1} on:bottom={bottoms += 1} on:scroll={pos = event}>
    {#each msgs as m (m["id"])}
      <Text>{m["t"]}</Text>
    {/each}
  </List>
</Window>
"""


def view_of(m):
    return next(i for i in visual_items(m) if i.inherits("QQuickListView"))


def settle(m, view=None):
    view = view or view_of(m)
    for _ in range(3):
        QMetaObject.invokeMethod(view, "forceLayout")
        QCoreApplication.processEvents()
    return view


def shown(m):
    """Textos de las filas visibles, de arriba abajo, con su posición en pantalla."""
    view = settle(m)
    top = view.mapToScene(QPointF(0, 0)).y()
    rows = []
    for item in visual_items(m):
        if item.inherits("QQuickLabel") and item.isVisible() and item.property("text").startswith("mensaje"):
            y = item.mapToScene(QPointF(0, 0)).y() - top
            if -item.height() < y < view.height():
                rows.append((round(y), item.property("text")))
    return sorted(rows)


def test_follow_starts_at_the_end_and_follows_new_rows(mount):
    m = mount(CHAT % 100)
    view = settle(m)
    assert view.property("atYEnd")
    assert shown(m)[-1][1] == "mensaje 99"
    m.instance.namespace["append"]()
    settle(m)
    assert view.property("atYEnd")
    assert shown(m)[-1][1] == "mensaje 100"


def test_follow_does_not_jump_when_the_user_scrolled_up(mount):
    m = mount(CHAT % 100)
    view = settle(m)
    view.setProperty("contentY", view.property("contentY") - 300)
    before = shown(m)
    m.instance.namespace["append"]()
    assert shown(m) == before


def test_prepending_history_keeps_the_visible_rows_in_place(mount):
    m = mount(CHAT % 100)
    view = settle(m)
    view.setProperty("contentY", view.property("contentY") - 400)
    before = shown(m)
    m.instance.namespace["prepend"](200)  # más que el umbral de reinicio del modelo
    assert shown(m) == before
    assert len(m.instance.root.regions[0].model) == 300


def test_prepending_at_the_very_top_keeps_reading_position(mount):
    m = mount(CHAT % 100)
    settle(m)
    m.instance.namespace["lista"].scroll_to_start()  # lo que hace un chat al llegar arriba: pedir historial
    before = shown(m)
    assert before[0] == (0, "mensaje 0")
    m.instance.namespace["prepend"](50)
    assert shown(m) == before


def test_reaching_the_top_emits_on_top(mount):
    m = mount(CHAT % 100)
    view = settle(m)
    ns = m.instance.namespace
    assert ns["tops"].value == 0
    lista = ns["lista"]
    lista.scroll_to_start()
    settle(m, view)
    assert view.property("atYBeginning")
    assert ns["tops"].value == 1
    lista.scroll_to_end()
    settle(m, view)
    assert view.property("atYEnd")
    assert ns["bottoms"].value >= 1
    assert ns["pos"].value["bottom"] is True and ns["pos"].value["top"] is False
    lista.scroll_to(10)
    assert any(text == "mensaje 10" for _, text in shown(m))


def test_markdown_text_and_links(mount):
    m = mount(
        """<script>
from fluxui import state
opened = state("")
</script>
<Window>
  <Column>
    <Text id="md" format="markdown" on:link={opened = event}>**hola** [web](https://example.com)</Text>
    <Text id="plain">**hola** [web](https://example.com)</Text>
  </Column>
</Window>"""
    )
    md, plain = find(m, "md"), find(m, "plain")
    assert md.property("format") == "markdown"
    assert plain.property("format") == "plain"
    # El Markdown se interpreta: hay un enlace pulsable en la línea.
    def links(item):
        found = set()
        for x in range(0, 200, 4):
            found.add(QMetaObject.invokeMethod(item, "linkAt", Q_RETURN_ARG("QString"), Q_ARG("qreal", x), Q_ARG("qreal", 6)))
        return found - {""}

    assert links(md) == {"https://example.com"}
    assert links(plain) == set()
    md.linkActivated.emit("https://example.com")
    assert m.instance.namespace["opened"].value == "https://example.com"


def test_window_activation_events():
    compiled = compile_source(
        """<script>
from fluxui import state
active = state(None)
</script>
<Window on:activate={active = True} on:deactivate={active = False}><Text>x</Text></Window>"""
    )
    assert "onActiveChanged: { if (active) fx.invoke(" in compiled.qml
    assert "if (!active) fx.invoke(" in compiled.qml


def test_text_accepts_background_border_and_radius(mount):
    m = mount(
        """<Window><Column><Text id="badge" class="badge">3</Text></Column></Window>
<style>.badge { background: #ff0000; border: 1px solid #00ff00; border-radius: 9px; padding: 0 6px; }</style>"""
    )
    badge = find(m, "badge")
    assert badge.property("fxBackground").name() == "#ff0000"
    assert badge.property("fxRadius") == 9
    assert badge.property("leftPadding") == 6
