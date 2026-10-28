"""Controles añadidos para el lanzamiento: Switch, Slider, Select, RadioGroup, Tabs, Image, ProgressBar,
Shortcut, on:input en TextArea y diálogos nativos."""
import asyncio

from conftest import find, texts, visual_items
from PySide6.QtCore import QMetaObject, QUrl, Q_ARG

from janelkit import dialogs

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
<Column>
  <Switch id="sw" bind:checked={on}>Activado</Switch>
  <Slider id="sl" bind:value={volume} min={0} max={100} step={10} />
  <Select id="sel" bind:value={color} options={["rojo", "verde", "azul"]} />
  <Select id="empty" options={["a"]} placeholder="Elige…" />
  <RadioGroup id="rg" bind:value={size} options={SIZES} horizontal />
  <Tabs id="tabs" bind:value={tab} options={["general", "avanzado"]} />
  {#if tab == "general"}
    <Text>Panel general</Text>
  {:else}
    <Text>Panel avanzado</Text>
  {/if}
  <TextArea id="ta" bind:value={notes} on:input={typed.append(event)} />
  <ProgressBar id="pb" value={progress} />
  <Shortcut id="sc" keys="Ctrl+S" on:activate={saved += 1} />
  <Image id="img" src="logo.png" width={32} height={32} />
</Column>
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
        '<Image id="img" src={src} fit="cover" />'
    )
    img = find(m, "img")
    assert img.property("source").toString() == "file:///C:/fotos/a.png"
    m.instance.namespace["src"].value = "https://example.com/a.png"
    assert img.property("source").toString() == "https://example.com/a.png"
    assert img.property("clip") is True  # fit="cover" recorta


# -- diálogos ------------------------------------------------------------------------
def test_open_file_dialog_returns_the_selected_path(janel_app, mount, tmp_path):
    mount("<Text>x</Text>")
    target = tmp_path / "nota.txt"
    target.write_text("x", encoding="utf-8")  # FileDialog solo acepta archivos que existen

    async def scenario():
        task = asyncio.ensure_future(dialogs.open_file("Abrir", filters=["Texto (*.txt)"], folder=tmp_path))
        await asyncio.sleep(0.05)
        (dialog,) = dialogs.pending()
        assert dialog.property("title") == "Abrir" and dialog.property("nameFilters") == ["Texto (*.txt)"]
        dialog.setProperty("selectedFile", QUrl.fromLocalFile(str(target)))
        QMetaObject.invokeMethod(dialog, "done", Q_ARG(int, 1))  # como si el usuario aceptara
        return await task

    assert janel_app.run_until(scenario()) == target
    assert dialogs.pending() == []


def test_cancelled_dialogs_return_none_or_false(janel_app, mount):
    mount("<Text>x</Text>")

    async def cancel_next(coro):
        task = asyncio.ensure_future(coro)
        await asyncio.sleep(0.05)
        QMetaObject.invokeMethod(dialogs.pending()[0], "reject")
        return await task

    assert janel_app.run_until(cancel_next(dialogs.save_file(name="a.txt"))) is None
    assert janel_app.run_until(cancel_next(dialogs.choose_folder())) is None
    assert janel_app.run_until(cancel_next(dialogs.confirm("¿Seguro?"))) is False
    assert janel_app.run_until(cancel_next(dialogs.open_files())) == []


def test_confirm_accepts(janel_app, mount):
    mount("<Text>x</Text>")

    async def scenario():
        task = asyncio.ensure_future(dialogs.confirm("¿Borrar?", title="Notas"))
        await asyncio.sleep(0.05)
        dialog = dialogs.pending()[0]
        assert dialog.property("text") == "¿Borrar?"
        QMetaObject.invokeMethod(dialog, "done", Q_ARG(int, 0x400))  # botón Aceptar
        return await task

    assert janel_app.run_until(scenario()) is True
