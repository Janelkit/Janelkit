"""Un state que es atributo de un objeto (`hub.status`) se muestra y se actualiza en la plantilla.

Antes solo se desenvolvían los nombres: `{hub.status}` mostraba `state('cerrada')` y no se
actualizaba. Caso del primer usuario externo (servicios compartidos con state como atributos).
"""
from janelkit.testing import find, texts

from janelkit import computed, state

HUB_APP = """<script>
from janelkit import state, computed

class Hub:
    def __init__(self):
        self.status = state("cerrada")
        self.ready = state(False)
        self.items = state(["a"])
        self.count = computed(lambda: len(self.items.value))

hub = Hub()
status = hub.status
</script>
<Column>
  <Text id="attr">{f"atributo: {hub.status}"}</Text>
  <Text id="name">{f"nombre: {status}"}</Text>
  <Text id="plain">{hub.status}</Text>
  <Text id="value">{hub.status.value.upper()}</Text>
  <Text id="count">{hub.count:03d}</Text>
  {#if hub.ready}
    <Text>lista</Text>
  {/if}
  {#each hub.items as item}
    <Text>item {item}</Text>
  {/each}
</Column>
"""


def test_state_attribute_is_unwrapped_and_reactive(mount, janel_app):
    m = mount(HUB_APP)
    hub = m.instance.namespace["hub"]
    text = lambda id: find(m, id).property("text")  # noqa: E731
    assert text("attr") == "atributo: cerrada"
    assert text("name") == "nombre: cerrada"
    assert text("plain") == "cerrada"
    assert text("value") == "CERRADA"  # .value explícito sigue funcionando
    assert text("count") == "001"
    assert "lista" not in texts(m) and "item a" in texts(m)

    hub.status.value = "abierta"
    hub.ready.value = True
    hub.items.value = ["a", "b"]
    janel_app.process_events()
    assert text("attr") == "atributo: abierta" and text("plain") == "abierta"
    assert text("count") == "002"
    assert "lista" in texts(m) and "item b" in texts(m)


def test_str_and_format_show_the_value_but_repr_says_what_it_is():
    s = state(3.14159)
    assert str(s) == "3.14159" and f"{s:.2f}" == "3.14"
    assert repr(s) == "state(3.14159)"
    c = computed(lambda: s.value * 2)
    assert f"{c:.1f}" == "6.3"
