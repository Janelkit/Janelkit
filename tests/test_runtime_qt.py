"""Integración con Qt: el QML generado se carga y reacciona al estado Python."""
import logging

import pytest
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


def find(mounted, name: str) -> QObject:
    obj = mounted.root.findChild(QObject, name)
    assert obj is not None, f"no se encontró id={name}"
    return obj


def click(button: QObject) -> None:
    assert QMetaObject.invokeMethod(button, "click")


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


def test_dynamic_property_and_conditionals(mount):
    m = mount(COUNTER)
    button, many, few = find(m, "inc"), find(m, "many"), find(m, "few")
    assert (many.property("visible"), few.property("visible")) == (False, True)
    assert few.property("text") == "Pocos: 2"
    for _ in range(3):
        click(button)
    assert (many.property("visible"), few.property("visible")) == (True, False)
    assert button.property("enabled") is False


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


def test_checkbox_two_way(mount):
    m = mount(
        """<script>
from fluxui import state
done = state(False)
</script>
<Column>
  <Checkbox id="c" bind:checked={done}>Hecho</Checkbox>
  <Text id="out">{"sí" if done else "no"}</Text>
</Column>"""
    )
    box = find(m, "c")
    box.setProperty("checked", True)
    assert QMetaObject.invokeMethod(box, "toggled")
    assert m.instance.namespace["done"].value is True
    assert find(m, "out").property("text") == "sí"


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


def test_qt_rejection_is_mapped_to_flux_location(flux_app, monkeypatch):
    c = compile_source("<Window>\n  <Column>\n    <Text>x</Text>\n  </Column>\n</Window>", "Bad.flux")
    # Simular un fallo de Qt corrompiendo el QML del Label.
    c.qml = c.qml.replace("Label {", "Label { noExiste: 1;")
    with pytest.raises(FluxError) as info:
        flux_app.mount(c)
    d = info.value.first
    assert "Qt rechazó el QML generado" in d.message
    assert d.location is not None and d.location.line == 3
