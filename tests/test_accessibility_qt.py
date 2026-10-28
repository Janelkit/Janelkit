"""Accesibilidad básica: navegación con teclado, foco visible y nombres accesibles."""
from conftest import find
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QAccessible, QKeyEvent

APP = """<script>
from janelkit import state
opened = state(0)
</script>
<Column>
  <TextField id="field" placeholder="Nombre" label="Nombre completo" />
  <Row id="card" on:click={opened += 1} label="Abrir la nota"><Text>Nota</Text></Row>
  <Row id="plain"><Text>Sin clic</Text></Row>
  <Button id="ok">Aceptar</Button>
  <Image id="logo" src="" alt="Logotipo" />
</Column>
"""


def press(item, key):
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(item, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))


def accessible_name(item) -> str:
    iface = QAccessible.queryAccessibleInterface(item)
    return iface.text(QAccessible.Text.Name) if iface is not None else ""


def test_clickable_boxes_are_in_the_tab_order(mount):
    m = mount(APP)
    field, card, plain, ok = (find(m, n) for n in ("field", "card", "plain", "ok"))
    assert card.property("activeFocusOnTab") is True
    assert plain.property("activeFocusOnTab") is False
    assert field.nextItemInFocusChain(True) is card  # Tab: campo -> tarjeta -> botón
    assert card.nextItemInFocusChain(True) is ok


def test_space_and_enter_activate_a_clickable_box(mount):
    m = mount(APP)
    card = find(m, "card")
    press(card, Qt.Key.Key_Space)
    press(card, Qt.Key.Key_Return)
    assert m.instance.namespace["opened"].value == 2


def test_focus_is_visible_on_clickable_boxes(mount):
    m = mount(APP)
    card = find(m, "card")
    card.forceActiveFocus()
    if card.hasActiveFocus():  # sin ventana activa (offscreen) el foco puede no llegar
        assert card.property("jkKeyFocus") is True
    assert card.property("activeFocusOnTab") is True


def test_accessible_names(mount):
    m = mount(APP)
    assert accessible_name(find(m, "field")) == "Nombre completo"
    assert accessible_name(find(m, "card")) == "Abrir la nota"
    assert accessible_name(find(m, "ok")) == "Aceptar"
    assert accessible_name(find(m, "logo")) == "Logotipo"
