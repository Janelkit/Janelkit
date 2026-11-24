"""API pública de inspección (janelkit.inspect): montar sin ventana, buscar, actuar y esperar."""
import sys
from pathlib import Path

import pytest

from janelkit.compiler import compile_file
from janelkit.inspect import InspectError, mount

EXAMPLES = Path(__file__).resolve().parents[3] / "apps" / "examples"


@pytest.fixture(autouse=True)
def _isolate_modules(monkeypatch, janel_app):
    """Cada ejemplo trae sus propios `services`/`components`: no compartirlos entre pruebas."""
    before = set(sys.modules)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in set(sys.modules) - before:
        if name.split(".")[0] in ("services", "components", "widgets"):
            del sys.modules[name]


def test_counter_like_a_user():
    with mount(EXAMPLES / "counter" / "src" / "App.janel") as app:
        assert app.texts()[0] == "Hola, invitado"
        app.find(placeholder="Tu nombre").type("Ana")
        assert app.texts()[0] == "Hola, Ana"
        plus = app.find("button", text="Clicks: 0")
        for _ in range(5):
            plus.click()
        assert app.get("count") == 5 and plus.text == "Clicks: 5"
        assert "Has llegado a cinco clicks." in app.texts()
        assert app.find(text="−").enabled
        meter = app.find("Meter")
        assert meter.prop("value") == 5


def test_todo_flow():
    with mount(EXAMPLES / "todo" / "src" / "App.janel") as app:
        field = app.find(placeholder="¿Qué hay que hacer?")
        field.type("Comprar pan").submit()
        assert app.find("checkbox", text="Comprar pan").value is False
        app.find("checkbox", text="Comprar pan").check()
        assert app.get("todos")[-1]["done"] is True
        app.find("button", text="Pendientes").click()
        app.wait(0.2)  # las filas del ejemplo salen con transition:fade
        assert app.find_all("checkbox", text="Comprar pan") == []
        with pytest.raises(InspectError, match="hay 0"):
            app.find(text="no existe")


def test_disabled_controls_cannot_be_used():
    with mount(EXAMPLES / "todo" / "src" / "App.janel") as app:
        add = app.find("button", text="Añadir")
        assert not add.enabled
        with pytest.raises(InspectError, match="desactivado"):
            add.click()


def test_async_example_with_wait(tmp_path):
    app_file = tmp_path / "App.janel"
    app_file.write_text(
        """<script>
import asyncio
from janelkit import state, task

@task
async def load(q):
    await asyncio.sleep(0.02)
    return q.upper()

</script>
<column>
  <button on:click={load.run("hola")}>Cargar</button>
  <select id="color" options={["rojo", {"label": "Verde", "value": "g"}]} />
  <radiogroup id="size" options={["S", "M"]} />
  <tabs id="tabs" options={["uno", "dos"]} />
  <slider id="vol" />
  {#if load.loading}<text>Cargando…</text>{:else}<text>{load.value}</text>{/if}
</column>
""",
        encoding="utf-8",
    )
    with mount(app_file) as app:
        app.find(text="Cargar").click()
        assert "Cargando…" in app.texts()
        app.wait(until=lambda: not app.get("load").loading)
        assert "HOLA" in app.texts()

        assert app.find(id="color").choose("Verde").value == "g"
        assert app.find(id="size").choose("M").value == "M"
        assert app.find(id="tabs").choose("dos").value == "dos"
        assert app.find(id="vol").slide(40).value == 40


def test_unknown_option_is_reported(tmp_path):
    app_file = tmp_path / "App.janel"
    app_file.write_text('<select id="s" options={["a"]} />', encoding="utf-8")
    with mount(app_file) as app:
        with pytest.raises(InspectError, match="no tiene la opción 'z'"):
            app.find(id="s").choose("z")


def test_tutorial_app(tmp_path, monkeypatch):
    """La aplicación de docs/tutorial.md (apps/examples/compra) funciona como dice el tutorial."""
    import json

    file = tmp_path / "lista.json"
    monkeypatch.setenv("COMPRA_FILE", str(file))
    with mount(EXAMPLES / "compra" / "src" / "App.janel") as app:
        app.wait(until=lambda: app.get("loaded"))
        assert "La lista está vacía." in app.texts()
        app.find(placeholder="¿Qué falta?").type("Pan").submit()
        app.find(placeholder="¿Qué falta?").type("Leche").submit()
        assert app.find("Card").visible and "Pendientes: 2" in app.texts()
        app.find("checkbox", text="Pan").check()
        assert "Pendientes: 1" in app.texts()
        app.find_all("button", text="Quitar")[1].click()
        app.wait(until=lambda: not app.get("save").loading)
        assert json.loads(file.read_text(encoding="utf-8")) == [{"id": 1, "name": "Pan", "done": True}]
    with mount(EXAMPLES / "compra" / "src" / "App.janel") as app:  # vuelve a cargar lo guardado
        app.wait(until=lambda: app.get("loaded"))
        assert app.find("checkbox", text="Pan").value is True


def test_apps_with_modules_of_the_same_name_do_not_mix(tmp_path):
    for name in ("una", "otra"):
        (tmp_path / name / "services").mkdir(parents=True)
        (tmp_path / name / "services" / "datos.py").write_text(f"NOMBRE = {name!r}\n", encoding="utf-8")
        (tmp_path / name / "App.janel").write_text(
            '<script lang="python">\nfrom services.datos import NOMBRE\n</script>\n<window><text>{NOMBRE}</text></window>\n',
            encoding="utf-8",
        )
    for name in ("una", "otra", "una"):
        with mount(tmp_path / name / "App.janel") as app:
            assert app.texts() == [name]


SHOT_APP = """<window title="captura" width={200} height={120} background="#00ff00">
  <column class="page">
    <text id="t">hola</text>
    <flex id="box" class="box"></flex>
  </column>
</window>
<style>
.page { padding: 10px; }
.box { width: 40px; height: 30px; background: #ff0000; }
</style>
"""


def test_screenshot_of_window_and_element(tmp_path):
    entry = tmp_path / "App.janel"
    entry.write_text(SHOT_APP, encoding="utf-8")
    with mount(entry) as app:
        image = app.screenshot(tmp_path / "ventana.png")
        assert (tmp_path / "ventana.png").stat().st_size > 0
        ratio = image.devicePixelRatio()
        assert (image.width(), image.height()) == (round(200 * ratio), round(120 * ratio))
        assert image.pixelColor(image.width() - 2, image.height() - 2).name() == "#00ff00"
        box = app.find(id="box").screenshot()
        assert (box.width(), box.height()) == (round(40 * ratio), round(30 * ratio))
        assert box.pixelColor(box.width() // 2, box.height() // 2).name() == "#ff0000"


def test_component_whose_root_is_a_builtin_is_found_by_both_names(tmp_path):
    (tmp_path / "Otra.janel").write_text("<text>otra</text>\n", encoding="utf-8")
    (tmp_path / "Boton.janel").write_text(
        "<script>\nfrom janelkit import state\nn = state(0)\n</script>\n"
        "<button on:click={n += 1}>pulsado {n}</button>\n", encoding="utf-8")
    (tmp_path / "App.janel").write_text("""<script>
from Otra import Otra
</script>
<window><Otra /></window>
""", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        assert app.texts() == ["otra"]
        assert app.find("Otra").text == "otra" and app.find("text").text == "otra"

    (tmp_path / "App.janel").write_text("<script>\nfrom Boton import Boton\n</script>\n<window><Boton /></window>\n",
                                        encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        app.find("button").click()
        assert app.find("Boton").text == "pulsado 1"


def test_fields_have_a_value_not_a_text(tmp_path):
    (tmp_path / "App.janel").write_text("""<script>
from janelkit import state
nombre = state("Pan")
</script>
<window><column>
  <textfield bind:value={nombre} placeholder="Nombre" />
  <text>Pan</text>
</column></window>
""", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        field = app.find(placeholder="Nombre")
        assert field.value == "Pan" and field.text is None
        assert app.find(text="Pan").tag == "text"  # el campo no cuenta como texto
        assert app.texts() == ["Pan"]


def test_an_unknown_method_points_to_the_extensions(tmp_path):
    (tmp_path / "App.janel").write_text("<text>hola</text>", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        with pytest.raises(AttributeError, match=r"no tiene 'notifications'; si lo añade una extensión \(como dialogs\(\) de janelkit-desktop"):
            app.notifications()
        with pytest.raises(AttributeError, match=r"no tiene '_privado'$"):
            app._privado


def test_a_tab_or_a_radio_option_found_by_its_text_can_be_clicked(tmp_path):
    """Lo natural es buscar la pestaña por lo que pone y pulsarla, sin pasar por choose()."""
    app_file = tmp_path / "App.janel"
    app_file.write_text(
        '<script>\nfrom janelkit import state\ntab = state("Detalle")\nsize = state("S")\n</script>\n'
        '<column>\n  <tabs bind:value={tab} options={["Detalle", "Totales"]} />\n'
        '  <radiogroup bind:value={size} options={["S", "M"]} />\n'
        "  {#if tab == 'Totales'}<text>suma</text>{/if}\n</column>",
        encoding="utf-8",
    )
    with mount(app_file) as app:
        app.find(text="Totales").click()
        assert app.get("tab") == "Totales" and "suma" in app.texts()
        app.find(text="M").click()
        assert app.get("size") == "M"


def test_button_takes_title_and_disabled(tmp_path):
    app_file = tmp_path / "App.janel"
    app_file.write_text(
        "<script>\nfrom janelkit import state\nbusy = state(True)\nn = state(0)\n</script>\n"
        '<column><button title="Guarda el archivo" disabled={busy} on:click={n += 1}>Guardar</button></column>',
        encoding="utf-8",
    )
    with mount(app_file) as app:
        button = app.find("button", text="Guardar")
        assert not button.enabled
        qml = compile_file(app_file).qml
        assert 'ToolTip.text: "Guarda el archivo"' in qml and "ToolTip.visible" in qml
        with pytest.raises(InspectError):
            button.click()
        app.namespace["busy"].value = False
        app.process()
        button.click()
        assert button.enabled and app.get("n") == 1


def test_headless_tests_use_the_system_fonts_on_windows(monkeypatch, tmp_path):
    from janelkit import inspect as jk_inspect

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("QT_QPA_FONTDIR", raising=False)
    (tmp_path / "Fonts").mkdir()
    monkeypatch.setenv("WINDIR", str(tmp_path))
    jk_inspect._use_system_fonts()
    assert Path(jk_inspect.os.environ["QT_QPA_FONTDIR"]) == tmp_path / "Fonts"
    monkeypatch.setenv("QT_QPA_FONTDIR", "otra")  # lo que fije quien prueba se respeta
    jk_inspect._use_system_fonts()
    assert jk_inspect.os.environ["QT_QPA_FONTDIR"] == "otra"


def test_real_pointer_and_key_events_start_async_handlers_inside_the_loop(tmp_path):
    """click(x, y), double_click, right_click y key usan eventos reales (QTest). El primer paso
    de un manejador async arranca mientras se procesa el evento: debe ver el bucle activo
    (asyncio.get_running_loop(), un Future, un diálogo que se espera), como con click()."""
    app_file = tmp_path / "App.janel"
    app_file.write_text(
        "<script>\nimport asyncio\nfrom janelkit import state\nlog = state([])\n\n"
        "async def pedir(que):\n"
        "    loop = asyncio.get_running_loop()  # fallaba: no running event loop\n"
        "    hecho = loop.create_future()\n"
        "    loop.call_soon(hecho.set_result, que)\n"
        "    log.value = log.value + [await hecho]\n</script>\n"
        "<column>\n"
        '  <button on:click={pedir("click")}>Nuevo</button>\n'
        '  <flex label="caja" on:dblclick={pedir("dblclick")} on:contextmenu={pedir("contextmenu")}><text>caja</text></flex>\n'
        '  <shortcut keys="Ctrl+N" on:activate={pedir("key")} />\n'
        "</column>",
        encoding="utf-8",
    )
    with mount(app_file) as app:
        app.find("button", text="Nuevo").click(x=5, y=5)
        app.find(label="caja").double_click()
        app.find(label="caja").right_click()
        app.key("Ctrl+N")
        app.wait(until=lambda: len(app.get("log")) >= 4, timeout=2)
        assert sorted(app.get("log")) == ["click", "contextmenu", "dblclick", "key"]
