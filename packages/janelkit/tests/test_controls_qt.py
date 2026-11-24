"""Controles: Switch, Slider, Select, RadioGroup, Tabs, Image, ProgressBar,
Shortcut y on:input en TextArea (los diálogos nativos están en janelkit-desktop)."""

from janelkit.testing import find, texts, visual_items
from PySide6.QtCore import QCoreApplication, QMetaObject, QUrl, Q_ARG


FORM = """<script>
from janelkit import state
on = state(False)
volume = state(30)
color = state("verde")
size = state(2)
tab = state("general")
typed = state([])
notes = state("hola")
saved = state(0)
progress = state(0.25)
SIZES = [{"label": "Pequeño", "value": 1}, {"label": "Mediano", "value": 2}, {"label": "Grande", "value": 3}]
</script>
<column>
  <switch id="sw" bind:checked={on}>Activado</switch>
  <slider id="sl" bind:value={volume} min={0} max={100} step={10} />
  <select id="sel" bind:value={color} options={["rojo", "verde", "azul"]} />
  <select id="empty" options={["a"]} placeholder="Elige…" />
  <radiogroup id="rg" bind:value={size} options={SIZES} horizontal />
  <tabs id="tabs" bind:value={tab} options={["general", "avanzado"]} />
  {#if tab == "general"}
    <text>Panel general</text>
  {:else}
    <text>Panel avanzado</text>
  {/if}
  <textarea id="ta" bind:value={notes} on:input={typed.append(event)} />
  <progressbar id="pb" value={progress} />
  <shortcut id="sc" keys="Ctrl+S" on:activate={saved += 1} />
  <image id="img" src="logo.png" width={32} height={32} />
</column>
"""


def ns(m):
    return m.instance.namespace


def test_controls_mount_without_qml_warnings(mount, caplog, tmp_path):
    app = tmp_path / "App.janel"
    app.write_text(FORM.replace('src="logo.png"', 'src=""'), encoding="utf-8")
    mount(app)
    assert caplog.text == ""


def test_switch_two_way(mount):
    m = mount(FORM)
    sw = find(m, "sw")
    assert sw.property("checked") is False and sw.property("text") == "Activado"
    assert QMetaObject.invokeMethod(sw, "toggle") and QMetaObject.invokeMethod(sw, "toggled")
    assert ns(m)["on"].value is True
    ns(m)["on"].value = False
    assert sw.property("checked") is False


def test_slider_two_way(mount):
    m = mount(FORM)
    sl = find(m, "sl")
    assert sl.property("value") == 30 and sl.property("to") == 100 and sl.property("stepSize") == 10
    sl.setProperty("value", 70)
    assert QMetaObject.invokeMethod(sl, "moved")
    assert ns(m)["volume"].value == 70
    ns(m)["volume"].value = 10
    assert sl.property("value") == 10


def test_select_follows_python_and_reports_user_choice(mount):
    m = mount(FORM)
    sel = find(m, "sel")
    assert sel.property("currentIndex") == 1 and sel.property("displayText") == "verde"
    ns(m)["color"].value = "azul"
    assert sel.property("currentIndex") == 2
    sel.setProperty("currentIndex", 0)  # el usuario elige "rojo"
    assert QMetaObject.invokeMethod(sel, "activated", Q_ARG(int, 0))
    assert ns(m)["color"].value == "rojo"
    assert find(m, "empty").property("displayText") == "Elige…"


def test_radio_group_with_label_value_options(mount):
    m = mount(FORM)
    rg = find(m, "rg")
    radios = [c for c in rg.childItems() if c.property("text") in ("Pequeño", "Mediano", "Grande")]
    assert [r.property("text") for r in radios] == ["Pequeño", "Mediano", "Grande"]
    assert [r.property("checked") for r in radios] == [False, True, False]
    assert QMetaObject.invokeMethod(radios[2], "clicked")
    assert ns(m)["size"].value == 3
    assert [r.property("checked") for r in radios] == [False, False, True]
    ns(m)["size"].value = 1
    assert [r.property("checked") for r in radios] == [True, False, False]


def test_tabs_switch_content(mount):
    m = mount(FORM)
    tabs = find(m, "tabs")
    assert tabs.property("currentIndex") == 0 and "Panel general" in texts(m)
    second = next(b for b in visual_items(m) if b.inherits("QQuickTabButton") and b.property("text") == "avanzado")
    assert QMetaObject.invokeMethod(second, "clicked")
    assert ns(m)["tab"].value == "avanzado" and "Panel avanzado" in texts(m)


def test_text_area_input_only_reports_user_edits(mount):
    m = mount(FORM)
    ta = find(m, "ta")
    assert ta.property("text") == "hola"
    ns(m)["notes"].value = "desde Python"
    assert ta.property("text") == "desde Python" and ns(m)["typed"].value == []
    ta.setProperty("text", "escrito")
    assert ns(m)["notes"].value == "escrito" and ns(m)["typed"].value == ["escrito"]


def test_progress_bar(mount):
    m = mount(FORM)
    pb = find(m, "pb")
    assert pb.property("value") == 0.25 and pb.property("to") == 1
    ns(m)["progress"].value = 0.75
    assert pb.property("value") == 0.75


def test_shortcut_activates(mount):
    m = mount(FORM)
    sc = find(m, "sc")
    assert sc.property("visible") is False and sc.property("keys") == "Ctrl+S"
    assert QMetaObject.invokeMethod(sc, "activated")
    assert ns(m)["saved"].value == 1


def test_image_resolves_relative_paths_from_the_janel_folder(mount, tmp_path):
    from PySide6.QtGui import QColor, QImage

    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    image.save(str(tmp_path / "logo.png"))
    app = tmp_path / "App.janel"
    app.write_text(FORM, encoding="utf-8")
    m = mount(app)
    img = find(m, "img")
    assert img.property("source") == QUrl.fromLocalFile(str(tmp_path / "logo.png"))
    assert img.property("progress") == 1.0 and img.property("implicitWidth") == 4  # cargada


def test_image_url_forms(mount):
    m = mount(
        "<script>\nfrom janelkit import state\nsrc = state('C:\\\\fotos\\\\a.png')\n</script>\n"
        '<image id="img" src={src} fit="cover" />'
    )
    img = find(m, "img")
    assert img.property("source").toString() == "file:///C:/fotos/a.png"
    m.instance.namespace["src"].value = "https://example.com/a.png"
    assert img.property("source").toString() == "https://example.com/a.png"
    assert img.property("clip") is True  # fit="cover" recorta


ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
    '<rect width="16" height="16" fill="#ff0000"/></svg>'
)


def _icon_of(button):
    from PySide6.QtQuick import QQuickItem

    images = [i for i in button.findChildren(QQuickItem) if i.inherits("QQuickImage")]
    return images[0] if images else None


def test_button_with_an_icon_draws_it_beside_the_text(mount, tmp_path, caplog):
    from janelkit.compiler import compile_file

    (tmp_path / "iconos").mkdir()
    (tmp_path / "iconos" / "borrar.svg").write_text(ICON_SVG, encoding="utf-8")
    app = tmp_path / "App.janel"
    app.write_text(
        "<script>\nfrom janelkit import state\nruta = state('iconos/borrar.svg')\n</script>\n"
        '<row><button id="texto">Borrar</button>'
        '<button id="ambos" icon="iconos/borrar.svg">Borrar</button>'
        '<button id="solo" icon={ruta} title="Borrar la toma" variant="ghost" /></row>',
        encoding="utf-8",
    )
    assert compile_file(app).warnings == []
    m = mount(app)
    texto, ambos, solo = (find(m, id) for id in ("texto", "ambos", "solo"))
    assert caplog.text == ""

    icon = _icon_of(ambos)
    assert icon is not None and icon.isVisible()
    assert icon.property("progress") == 1.0 and icon.property("paintedWidth") > 0  # la ruta es relativa al .janel
    assert icon.width() > 0 and ambos.width() > texto.width() + icon.width()  # el icono va además del texto
    assert _icon_of(texto) is None or not _icon_of(texto).isVisible()

    only = _icon_of(solo)
    assert only.isVisible() and solo.width() < texto.width()  # solo el icono: un botón estrecho
    from PySide6.QtGui import QAccessible
    iface = QAccessible.queryAccessibleInterface(solo)
    assert iface.text(QAccessible.Text.Name) == "Borrar la toma"  # sin texto ni label, el title lo nombra

    ns(m)["ruta"].value = ""  # sin icono vuelve a ser un botón normal
    QCoreApplication.processEvents()
    assert not only.isVisible()


def test_an_icon_only_button_without_a_name_warns(tmp_path):
    from janelkit.compiler import compile_source

    c = compile_source('<column><button icon="x.svg" /></column>', str(tmp_path / "App.janel"))
    assert len(c.warnings) == 1 and "un lector de pantalla no sabría qué es" in c.warnings[0].message
    for named in ('<button icon="x.svg" label="Cerrar" />', '<button icon="x.svg" title="Cerrar" />',
                  '<button icon="x.svg">Cerrar</button>'):
        assert compile_source(f"<column>{named}</column>", str(tmp_path / "App.janel")).warnings == []
