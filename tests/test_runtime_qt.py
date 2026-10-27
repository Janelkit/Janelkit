"""Integración con Qt: el QML generado se carga y reacciona al estado Python."""
import logging

import pytest
from conftest import click as press
from conftest import find, find_all, texts, visual_items
from PySide6.QtCore import QMetaObject, QObject

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError

COUNTER = """<script lang="python">
from fluxui import state, computed

count = state(0)
name = state("")

@computed
def greeting():
    return f"Hola, {name.value or 'invitado'}"

def increment():
    count.value += 1
</script>

<Window title="Contador">
  <Column>
    <Text id="greeting">{greeting}</Text>
    <TextField id="name" bind:value={name} placeholder="Tu nombre" />
    <Button id="inc" on:click={increment} enabled={count < 3}>Clicks: {count}</Button>
    {#if count >= 2}
      <Text id="many">Muchos</Text>
    {:else}
      <Text id="few">Pocos: {2 - count}</Text>
    {/if}
  </Column>
</Window>
"""


def click(button: QObject) -> None:
    press(button)


def type_text(field: QObject, text: str) -> None:
    """Simula una edición del usuario: cambia el texto y emite textEdited."""
    field.setProperty("text", text)
    assert QMetaObject.invokeMethod(field, "textEdited")


def test_click_updates_only_through_python_state(mount):
    m = mount(COUNTER)
    button = find(m, "inc")
    assert button.property("text") == "Clicks: 0"
    click(button)
    click(button)
    assert m.instance.namespace["count"].value == 2
    assert button.property("text") == "Clicks: 2"


def test_python_state_change_updates_view(mount):
    m = mount(COUNTER)
    m.instance.namespace["count"].value = 41
    assert find(m, "inc").property("text") == "Clicks: 41"


def test_if_mounts_and_unmounts_branches(mount):
    m = mount(COUNTER)
    assert find_all(m, "many") == []
    assert find(m, "few").property("text") == "Pocos: 2"
    count = m.instance.namespace["count"]
    subscribers = count.subscriber_count
    for _ in range(3):
        click(find(m, "inc"))
    m.root.contentItem().polish()
    assert find_all(m, "few") == []  # la rama inactiva se destruye
    assert find(m, "many").property("text") == "Muchos"
    assert find(m, "inc").property("enabled") is False
    # el binding "Pocos: {2 - count}" se liberó con su rama
    assert count.subscriber_count == subscribers - 1


def test_two_way_binding_without_loops(mount):
    m = mount(COUNTER)
    field, greeting = find(m, "name"), find(m, "greeting")
    name = m.instance.namespace["name"]
    emitted = []
    m.instance.bridge.b1Changed.connect(lambda: emitted.append(1))  # b1 = bind:value

    type_text(field, "Ana")
    assert name.value == "Ana"
    assert greeting.property("text") == "Hola, Ana"
    # el puente no reemite el valor que acaba de llegar desde Qt
    assert emitted == [1]

    name.value = "Bea"
    assert field.property("text") == "Bea"
    # tras una edición del usuario, el binding Python -> Qt sigue activo
    type_text(field, "Bea2")
    name.value = "Carla"
    assert field.property("text") == "Carla"


def test_bindings_update_independently(mount):
    m = mount(COUNTER)
    greeting_updates, count_updates = [], []
    m.instance.bridge.b0Changed.connect(lambda: greeting_updates.append(1))
    m.instance.bridge.b3Changed.connect(lambda: count_updates.append(1))  # texto del botón
    click(find(m, "inc"))
    assert count_updates == [1]
    assert greeting_updates == []  # el saludo no depende de count


def test_two_instances_keep_independent_state(mount):
    a, b = mount(COUNTER), mount(COUNTER)
    click(find(a, "inc"))
    click(find(a, "inc"))
    click(find(b, "inc"))
    assert find(a, "inc").property("text") == "Clicks: 2"
    assert find(b, "inc").property("text") == "Clicks: 1"
    assert a.instance.namespace["count"] is not b.instance.namespace["count"]


def test_unmount_releases_subscriptions(mount, flux_app):
    m = mount(COUNTER)
    count = m.instance.namespace["count"]
    assert count.subscriber_count > 0
    flux_app.unmount(m)
    assert count.subscriber_count == 0
    count.value = 99  # no debe tocar el puente de la instancia desmontada
    assert m.instance.bridge.value("b3") == "Clicks: 0"


def test_handler_receives_event_arguments(mount):
    m = mount(
        """<script>
from fluxui import state
last = state("")
def submitted(text):
    last.value = text
</script>
<Column>
  <TextField id="f" on:submit={submitted} />
  <Text id="out">{last}</Text>
</Column>"""
    )
    field = find(m, "f")
    field.setProperty("text", "hola")
    assert QMetaObject.invokeMethod(field, "accepted")
    assert find(m, "out").property("text") == "hola"


def test_checkbox_and_textarea_two_way(mount):
    m = mount(
        """<script>
from fluxui import state
done = state(False)
notes = state("a")
</script>
<Column>
  <Checkbox id="c" bind:checked={done}>Hecho</Checkbox>
  <TextArea id="t" bind:value={notes} />
  <Text id="out">{"sí" if done else "no"} {len(notes)}</Text>
</Column>"""
    )
    box = find(m, "c")
    box.setProperty("checked", True)
    assert QMetaObject.invokeMethod(box, "toggled")
    assert m.instance.namespace["done"].value is True
    find(m, "t").setProperty("text", "hola\nmundo")
    assert m.instance.namespace["notes"].value == "hola\nmundo"
    assert find(m, "out").property("text") == "sí 10"
    m.instance.namespace["notes"].value = "x"
    assert find(m, "t").property("text") == "x"


def test_runtime_error_in_binding_is_reported_with_location(mount, caplog):
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        m = mount(
            """<script>
from fluxui import state
d = state(0)
</script>
<Column>
  <Text id="t">{10 // d}</Text>
</Column>""",
            "Div.flux",
        )
    assert "Div.flux:6:" in caplog.text and "ZeroDivisionError" in caplog.text
    m.instance.namespace["d"].value = 5
    assert find(m, "t").property("text") == "2"


def test_handler_error_does_not_crash(mount, caplog):
    m = mount(
        """<script>
def boom():
    raise ValueError("fallo")
</script>
<Button id="b" on:click={boom}>x</Button>"""
    )
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        click(find(m, "b"))
    assert "ValueError: fallo" in caplog.text


def test_handler_must_be_callable(mount, caplog):
    m = mount("<script>\nx = 3\n</script>\n<Button id=\"b\" on:click={x}>x</Button>")
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        click(find(m, "b"))
    assert "debe recibir una función" in caplog.text


def test_mutating_unwrapped_state_in_template_gives_a_hint(mount, caplog):
    m = mount("<script>\nfrom fluxui import state\nn = state(0)\n</script>\n<Button id=\"b\" on:click={lambda: n.set(1)}>x</Button>")
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        click(find(m, "b"))
    assert "desenvueltos" in caplog.text


def test_qt_rejection_is_mapped_to_flux_location(flux_app):
    c = compile_source("<Window>\n  <Column>\n    <Text>x</Text>\n  </Column>\n</Window>", "Bad.flux")
    # Simular un fallo de Qt corrompiendo el QML del texto.
    c.qml = c.qml.replace("FxText {", "FxText { noExiste: 1;")
    with pytest.raises(FluxError) as info:
        flux_app.mount(c)
    d = info.value.first
    assert "Qt rechazó el QML generado" in d.message
    assert d.location is not None and d.location.line == 3


# -- listas ------------------------------------------------------------------------

TODOS = """<script>
from fluxui import state
todos = state([{"id": 1, "t": "a"}, {"id": 2, "t": "b"}, {"id": 3, "t": "c"}])
removed = state([])
def remove(i):
    removed.value = [*removed.value, i]
    todos.value = [t for t in todos.value if t["id"] != i]
</script>
<Column>
  {#each todos as todo, i (todo["id"])}
    <Row id="row">
      <Text>{i}:{todo["t"]}</Text>
      <Button id="del" on:click={lambda: remove(todo["id"])}>x</Button>
    </Row>
  {:else}
    <Text id="empty">Sin tareas</Text>
  {/each}
</Column>"""


def test_each_renders_inserts_updates_and_removes(mount):
    m = mount(TODOS)
    todos = m.instance.namespace["todos"]
    assert texts(m) == ["0:a", "1:b", "2:c"]
    todos.value = [*todos.value, {"id": 4, "t": "d"}]
    assert texts(m) == ["0:a", "1:b", "2:c", "3:d"]
    todos.value = [{"id": 1, "t": "A"}, *todos.value[1:]]
    assert texts(m) == ["0:A", "1:b", "2:c", "3:d"]
    todos.value = [t for t in todos.value if t["id"] != 2]
    assert texts(m) == ["0:A", "1:c", "2:d"]
    todos.value = []
    assert texts(m) == ["Sin tareas"]
    todos.value = [{"id": 9, "t": "z"}]
    assert texts(m) == ["0:z"]


def test_keys_preserve_row_identity_when_reordering(mount):
    m = mount(TODOS)
    a, b, c = find_all(m, "row")
    todos = m.instance.namespace["todos"]
    todos.value = list(reversed(todos.value))
    assert texts(m) == ["0:c", "1:b", "2:a"]
    # los mismos objetos visuales, en otro orden: no se recrean
    assert find_all(m, "row") == [c, b, a]


def test_row_handlers_use_the_current_item(mount):
    m = mount(TODOS)
    todos = m.instance.namespace["todos"]
    todos.value = list(reversed(todos.value))
    click(find_all(m, "del")[0])  # primera fila tras invertir: id 3
    assert m.instance.namespace["removed"].value == [3]
    assert texts(m) == ["0:b", "1:a"]


def test_removed_rows_release_their_subscriptions(mount):
    m = mount(
        """<script>
from fluxui import state
items = state([1, 2, 3])
suffix = state("!")
</script>
<Column>{#each items as x (x)}<Text>{x}{suffix}</Text>{/each}</Column>"""
    )
    suffix, items = m.instance.namespace["suffix"], m.instance.namespace["items"]
    assert suffix.subscriber_count == 3
    items.value = [1]
    assert suffix.subscriber_count == 1
    suffix.value = "?"
    assert texts(m) == ["1?"]


def test_duplicate_keys_are_reported_and_still_render(mount, caplog):
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        m = mount(
            """<script>
from fluxui import state
items = state([1, 1, 2])
</script>
<Column>{#each items as x (x)}<Text>{x}</Text>{/each}</Column>""",
            "Dup.flux",
        )
    assert "clave repetida" in caplog.text and "Dup.flux:5:" in caplog.text
    assert texts(m) == ["1", "1", "2"]


def test_nested_each_and_if(mount):
    m = mount(
        """<script>
from fluxui import state
groups = state([{"n": "A", "xs": [1, 2]}, {"n": "B", "xs": []}])
show = state(True)
</script>
<Column>
  {#each groups as g (g["n"])}
    <Column>
      <Text>{g["n"]}</Text>
      {#if show}
        {#each g["xs"] as x (x)}<Text>{g["n"]}{x}</Text>{:else}<Text>{g["n"]} vacío</Text>{/each}
      {/if}
    </Column>
  {/each}
</Column>"""
    )
    assert texts(m) == ["A", "A1", "A2", "B", "B vacío"]
    m.instance.namespace["show"].value = False
    assert texts(m) == ["A", "B"]
    groups = m.instance.namespace["groups"]
    m.instance.namespace["show"].value = True
    groups.value = [{"n": "B", "xs": [7]}, {"n": "A", "xs": [1]}]
    assert texts(m) == ["B", "B7", "A", "A1"]


def test_each_over_non_iterable_reports_error(mount, caplog):
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        mount("<script>\nfrom fluxui import state\nn = state(3)\n</script>\n<Column>{#each n as x}<Text>{x}</Text>{/each}</Column>")
    assert "error en {#each}" in caplog.text and "TypeError" in caplog.text


def test_layout_positions_rows_in_order(mount):
    m = mount(TODOS)
    m.root.setProperty("width", 300)
    m.root.setProperty("height", 300)
    m.root.contentItem().update()
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.processEvents()
    rows = find_all(m, "row")
    ys = [r.property("y") for r in rows]
    assert ys == sorted(ys) and len(set(ys)) == 3
    assert all(isinstance(i, QObject) for i in visual_items(m))


def test_conditional_class_toggles_style(mount):
    from PySide6.QtGui import QColor

    m = mount(
        """<script>
from fluxui import state
sel = state(False)
</script>
<Column><Text id="t" class="base" class:sel={sel}>x</Text></Column>
<style>.base { color: #00ff00; }\n.sel { color: #ff0000; font-size: 30px; }</style>"""
    )
    t = find(m, "t")
    assert t.property("fxColor") == QColor("#00ff00")
    m.instance.namespace["sel"].value = True
    assert t.property("fxColor") == QColor("#ff0000") and t.property("font").pixelSize() == 30
    m.instance.namespace["sel"].value = False
    assert t.property("fxColor") == QColor("#00ff00")


def test_key_block_recreates_content(mount):
    m = mount(
        """<script>
from fluxui import state
k = state(1)
other = state("a")
</script>
<Column>{#key k}<TextField id="f" value={other} />{/key}</Column>"""
    )
    first = find(m, "f")
    first.setProperty("text", "escrito a mano")
    m.instance.namespace["other"].value = "b"  # misma clave: se actualiza, no se recrea
    assert find(m, "f") == first
    m.instance.namespace["k"].value = 2
    second = find(m, "f")
    assert second != first and second.property("text") == "b"


def test_in_place_mutations_update_the_view(mount):
    m = mount(TODOS)
    todos = m.instance.namespace["todos"]
    rows = find_all(m, "row")
    todos.value.append({"id": 4, "t": "d"})
    assert texts(m) == ["0:a", "1:b", "2:c", "3:d"]
    todos.value[0]["t"] = "A"
    assert texts(m) == ["0:A", "1:b", "2:c", "3:d"]
    todos.value.reverse()
    assert texts(m) == ["0:d", "1:c", "2:b", "3:A"]
    assert find_all(m, "row")[1:] == rows[::-1]  # las filas existentes se movieron, no se recrearon
    todos.value.clear()
    assert texts(m) == ["Sin tareas"]


INLINE = """<script>
from fluxui import state
n = state(0)
last = state("")
todos = state([{"id": 1, "done": False}])
plain = 5
</script>
<Column>
  <Button id="inc" on:click={n += 1}>{n}</Button>
  <Button id="reset" on:click={n = 0; last = "reset"}>reset</Button>
  <TextField id="field" on:input={last = event} />
  <Button id="plain" on:click={plain = 1}>x</Button>
  {#each todos as todo (todo["id"])}
    <Checkbox id="check" checked={todo["done"]} on:change={todo["done"] = event}>{todo["done"]}</Checkbox>
    <Button id="add" on:click={todos.append({"id": len(todos) + 1, "done": False})}>+</Button>
  {/each}
</Column>"""


def test_inline_handlers_assign_state(mount, caplog):
    m = mount(INLINE)
    ns = m.instance.namespace
    click(find(m, "inc"))
    click(find(m, "inc"))
    assert ns["n"].value == 2 and find(m, "inc").property("text") == "2"
    click(find(m, "reset"))
    assert ns["n"].value == 0 and ns["last"].value == "reset"
    type_text(find(m, "field"), "hola")
    assert ns["last"].value == "hola"
    with caplog.at_level(logging.ERROR, logger="fluxui"):
        click(find(m, "plain"))
    assert "'plain' es int, no un state" in caplog.text


def test_inline_handlers_mutate_collections(mount):
    m = mount(INLINE)
    todos = m.instance.namespace["todos"]
    check = find(m, "check")
    check.setProperty("checked", True)
    assert QMetaObject.invokeMethod(check, "toggled")
    assert todos.value[0]["done"] is True
    click(find_all(m, "add")[0])
    assert len(todos.value) == 2 and len(find_all(m, "check")) == 2


def test_unmount_releases_bindings_of_a_script_without_effects(mount, flux_app):
    # Regresión: un ámbito vacío es falso (len 0) y la raíz creaba otro ámbito sin registrar.
    m = mount("<script>\nfrom fluxui import state\nn = state(1)\n</script>\n<Text>{n}</Text>")
    n = m.instance.namespace["n"]
    assert n.subscriber_count == 1
    flux_app.unmount(m)
    assert n.subscriber_count == 0


def test_flex_splits_free_space_in_proportion(mount, caplog):
    m = mount(
        """<Window width={900} height={300}>
  <Column>
    <Row id="r" flex={1}>
      <Column id="a" flex={2}><Text>corto</Text></Column>
      <Column id="b" flex={1}><Text>un texto bastante más largo que el otro para ver el reparto</Text></Column>
      <Button id="c">fijo</Button>
    </Row>
    <Column id="d" flex={1}><Text>abajo</Text></Column>
    <Column id="e" flex={3}><Text>abajo</Text></Column>
  </Column>
</Window>"""
    )
    a, b, c = (find(m, n).property("width") for n in "abc")
    assert a == 2 * b and a + b + c == 900  # como flex: 2 / flex: 1 en CSS, sin importar el contenido
    r, d, e = (find(m, n).property("height") for n in "rde")
    assert e == 3 * d and r == d and r + d + e == 300
    assert "loop" not in caplog.text.lower()


def test_dynamic_class_expression(mount, caplog):
    from PySide6.QtGui import QColor

    m = mount(
        """<script>
from fluxui import state
kind = state("info")
big = state(False)
</script>
<Column><Text id="t" class={["base", kind, {"big": big}]} class:alert={kind == "error"}>x</Text></Column>
<style>
.base { color: #000000; }
.info { color: #0000ff; }
.error { color: #ff0000; }
.big { font-size: 30px; }
.alert { font-weight: 700; }
</style>"""
    )
    t, ns = find(m, "t"), m.instance.namespace
    assert t.property("fxColor") == QColor("#0000ff")  # .info gana a .base: va después en <style>
    ns["kind"].value = "error"
    assert t.property("fxColor") == QColor("#ff0000") and t.property("font").bold()
    ns["big"].value = True
    assert t.property("font").pixelSize() == 30
    ns["kind"].value = ""
    assert t.property("fxColor") == QColor("#000000") and not t.property("font").bold()
    with caplog.at_level(logging.WARNING, logger="fluxui"):
        ns["kind"].value = "nada"
    assert "la clase 'nada' no tiene reglas en <style>" in caplog.text
