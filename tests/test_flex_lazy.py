"""Cajas y textos ligeros: cada pieza se crea solo si se usa (JkHover, JkTap, JkRole,
JkTranslate, JkTextBox, JkTextLinks). Ver "Vía rápida" en docs/flex.md."""
from conftest import find
from janelkit.compiler import compile_source
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QAccessible, QKeyEvent

APP = """<script>
from janelkit import state
papel = state("")
x = state(0)
</script>
<Column>
  <flex id="quieta"><Text id="plano">hola</Text></flex>
  <flex id="pulsable" on:click={print}><Text>clic</Text></flex>
  <flex id="encima" class="encima"><Text>hover</Text></flex>
  <flex id="etiqueta" label="Solo una etiqueta"><Text>x</Text></flex>
  <flex id="dinamica" as={papel}><Text>papel</Text></flex>
  <flex id="movida" style={{"padding": x}} class="movida"><Text>t</Text></flex>
  <Text id="fondo" class="fondo">con fondo</Text>
  <Text id="enlaces" format="markdown">[web](https://example.com)</Text>
</Column>
<style>
.encima:hover { background: #eeeeee; }
.movida { transform: translate(4px, 0); }
.fondo { background: #ffeeee; border-radius: 4px; }
</style>
"""


def parts(item):
    return {k: item.property(k) is not None for k in ("jkHover", "jkTap", "jkRoleItem", "jkTranslate")}


def test_a_plain_box_creates_nothing_extra(mount):
    m = mount(APP)
    assert parts(find(m, "quieta")) == {"jkHover": False, "jkTap": False, "jkRoleItem": False, "jkTranslate": False}
    plano = find(m, "plano")
    assert plano.property("jkBack") is None and plano.property("jkLinks") is None


def test_each_part_appears_when_used(mount):
    m = mount(APP)
    assert parts(find(m, "pulsable")) == {"jkHover": True, "jkTap": True, "jkRoleItem": True, "jkTranslate": False}
    assert parts(find(m, "encima")) == {"jkHover": True, "jkTap": False, "jkRoleItem": False, "jkTranslate": False}
    movida = find(m, "movida")
    assert movida.property("jkTranslate") is not None and movida.mapToScene(movida.position() * 0).x() == 4
    assert find(m, "fondo").property("jkBack") is not None
    assert find(m, "enlaces").property("jkLinks") is not None


def test_role_is_created_when_it_changes_and_works_with_the_keyboard(mount):
    m = mount(APP)
    caja = find(m, "dinamica")
    assert caja.property("jkRoleItem") is None
    m.instance.namespace["papel"].set("button")
    QCoreApplication.processEvents()
    assert caja.property("jkRoleItem") is not None
    iface = QAccessible.queryAccessibleInterface(caja)
    assert iface is not None and iface.role() == QAccessible.Role.Button
    # Espacio la pulsa (lo lleva JkRole): sube :pressed mientras se mantiene.
    QCoreApplication.sendEvent(caja, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier))
    assert caja.property("jkPressed") is True
    QCoreApplication.sendEvent(caja, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier))
    assert caja.property("jkPressed") is False


def test_label_on_a_box_without_role_stays_hidden_from_screen_readers(mount):
    qml = compile_source(APP).qml
    i = qml.index('objectName: "etiqueta"')
    block = qml[i:qml.index("JkText {", i)]
    assert 'Accessible.ignored: ' in block and '.jkAs === "box"' in block  # como antes de JkRole
    m = mount(APP)
    pulsable = QAccessible.queryAccessibleInterface(find(m, "pulsable"))
    assert pulsable is not None and pulsable.role() == QAccessible.Role.Button


def test_unset_side_padding_and_gap_follow_the_general_ones(mount):
    m = mount("""<Column><flex id="c" class="c"><flex id="a" class="cuadro" /><flex id="b" class="cuadro" /></flex></Column>
<style>
.c { padding: 6px; padding-left: 20px; gap: 5px; border: 1px solid #000000; }
.cuadro { width: 10px; height: 10px; }
</style>""")
    for _ in range(3):
        QCoreApplication.processEvents()
    c, a, b = find(m, "c"), find(m, "a"), find(m, "b")
    assert (a.x(), a.y()) == (21, 7)  # padding-left 20 + borde, padding 6 + borde
    assert b.x() - a.x() == 15  # 10 de ancho + gap 5
    assert c.implicitWidth() == 1 + 20 + 25 + 6 + 1 and c.height() == 1 + 6 + 10 + 6 + 1
