"""API pública de inspección (fluxui.inspect): montar sin ventana, buscar, actuar y esperar."""
import sys
from pathlib import Path

import pytest

from fluxui.inspect import InspectError, mount

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture(autouse=True)
def _isolate_modules(monkeypatch, flux_app):
    """Cada ejemplo trae sus propios `services`/`components`: no compartirlos entre pruebas."""
    before = set(sys.modules)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in set(sys.modules) - before:
        if name.split(".")[0] in ("services", "components", "widgets"):
            del sys.modules[name]


def test_counter_like_a_user():
    with mount(EXAMPLES / "counter" / "src" / "App.flux") as app:
        assert app.texts()[0] == "Hola, invitado"
        app.find(placeholder="Tu nombre").type("Ana")
        assert app.texts()[0] == "Hola, Ana"
        plus = app.find("Button", text="Clicks: 0")
        for _ in range(5):
            plus.click()
        assert app.get("count") == 5 and plus.text == "Clicks: 5"
        assert "Has llegado a cinco clicks." in app.texts()
        assert app.find(text="−").enabled
        meter = app.find("Meter")
        assert meter.prop("value") == 5


def test_todo_flow():
    with mount(EXAMPLES / "todo" / "src" / "App.flux") as app:
        field = app.find(placeholder="¿Qué hay que hacer?")
        field.type("Comprar pan").submit()
        assert app.find("Checkbox", text="Comprar pan").value is False
        app.find("Checkbox", text="Comprar pan").check()
        assert app.get("todos")[-1]["done"] is True
        app.find("Button", text="Pendientes").click()
        app.wait(0.2)  # las filas del ejemplo salen con transition:fade
        assert app.find_all("Checkbox", text="Comprar pan") == []
        with pytest.raises(InspectError, match="hay 0"):
            app.find(text="no existe")


def test_disabled_controls_cannot_be_used():
    with mount(EXAMPLES / "todo" / "src" / "App.flux") as app:
        add = app.find("Button", text="Añadir")
        assert not add.enabled
        with pytest.raises(InspectError, match="desactivado"):
            add.click()


def test_async_example_with_wait(tmp_path):
    app_file = tmp_path / "App.flux"
    app_file.write_text(
        """<script>
import asyncio
from fluxui import state, task, dialogs

@task
async def load(q):
    await asyncio.sleep(0.02)
    return q.upper()

chosen = state(None)

async def pick():
    chosen.value = await dialogs.open_file()
</script>
<Column>
  <Button on:click={load.run("hola")}>Cargar</Button>
  <Button on:click={pick}>Abrir</Button>
  <Select id="color" options={["rojo", {"label": "Verde", "value": "g"}]} />
  <RadioGroup id="size" options={["S", "M"]} />
  <Tabs id="tabs" options={["uno", "dos"]} />
  <Slider id="vol" />
  {#if load.loading}<Text>Cargando…</Text>{:else}<Text>{load.value}</Text>{/if}
</Column>
""",
        encoding="utf-8",
    )
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    with mount(app_file) as app:
        app.find(text="Cargar").click()
        assert "Cargando…" in app.texts()
        app.wait(until=lambda: not app.get("load").loading)
        assert "HOLA" in app.texts()

        app.find(text="Abrir").click()
        app.wait(0.02)
        assert len(app.dialogs()) == 1
        app.answer_dialog(target)
        assert app.get("chosen") == target

        assert app.find(id="color").choose("Verde").value == "g"
        assert app.find(id="size").choose("M").value == "M"
        assert app.find(id="tabs").choose("dos").value == "dos"
        assert app.find(id="vol").slide(40).value == 40


def test_unknown_option_is_reported(tmp_path):
    app_file = tmp_path / "App.flux"
    app_file.write_text('<Select id="s" options={["a"]} />', encoding="utf-8")
    with mount(app_file) as app:
        with pytest.raises(InspectError, match="no tiene la opción 'z'"):
            app.find(id="s").choose("z")


def test_files_example_validation_app(tmp_path, monkeypatch):
    """Aplicación de validación: carpetas, filtro, orden, vista previa, contexto, atajos y diálogos."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guia.md").write_text("# Guía\nHola", encoding="utf-8")
    (tmp_path / "b.txt").write_text("contenido de b" * 100, encoding="utf-8")  # 1400 bytes
    (tmp_path / "a.py").write_text("print('a')", encoding="utf-8")
    (tmp_path / ".oculto").write_text("x", encoding="utf-8")
    (tmp_path / "foto.png").write_bytes(b"\x89PNG")
    monkeypatch.setenv("FLUX_FILES_START", str(tmp_path))

    with mount(EXAMPLES / "files" / "src" / "App.flux") as app:
        app.wait(until=lambda: app.get("listing").value is not None)
        names = lambda: [e["name"] for e in app.get("visible")]  # noqa: E731
        assert names() == ["docs", "a.py", "b.txt", "foto.png"]  # carpetas primero, sin ocultos

        app.find("Switch", text="Ocultos").check()
        app.wait(until=lambda: ".oculto" in names())
        app.find("Switch", text="Ocultos").check(False)
        app.wait(until=lambda: ".oculto" not in names())

        app.find("Select").choose("Tamaño")
        assert names()[1] == "b.txt"  # el archivo más grande, tras las carpetas
        app.find(placeholder="Filtrar por nombre (Ctrl+F)").type(".py")
        assert names() == ["a.py"]
        app.find(placeholder="Filtrar por nombre (Ctrl+F)").type("")

        app.find("Text", text="b.txt").click()  # el clic llega a la fila (FileRow)
        app.wait(until=lambda: not app.get("preview").loading)
        assert any(t.startswith("contenido de b") for t in app.texts())
        assert app.find("Text", text="1.4 KB").visible
        app.find("Switch", text="Tamaños exactos").check()  # llega a cada FileRow por provide/inject
        assert app.find("Text", text="1.400 B").visible
        app.find("Text", text="foto.png").click()
        app.wait(until=lambda: not app.get("preview").loading)
        assert "Sin vista previa para archivos .png." in app.texts()

        app.find("Text", text="docs").click()  # entrar en la carpeta
        app.wait(until=lambda: names() == ["guia.md"])
        assert app.get("selected") is None
        app.find("Button", text="↑ Subir").click()
        app.wait(until=lambda: "docs" in names())

        app.find("Button", text="Abrir carpeta…").click()
        app.wait(0.02)
        app.answer_dialog(tmp_path / "docs")
        app.wait(until=lambda: names() == ["guia.md"])


def test_tutorial_app(tmp_path, monkeypatch):
    """La aplicación de docs/tutorial.md (examples/compra) funciona como dice el tutorial."""
    import json

    file = tmp_path / "lista.json"
    monkeypatch.setenv("COMPRA_FILE", str(file))
    with mount(EXAMPLES / "compra" / "src" / "App.flux") as app:
        app.wait(until=lambda: app.get("loaded"))
        assert "La lista está vacía." in app.texts()
        app.find(placeholder="¿Qué falta?").type("Pan").submit()
        app.find(placeholder="¿Qué falta?").type("Leche").submit()
        assert app.find("Card").visible and "Pendientes: 2" in app.texts()
        app.find("Checkbox", text="Pan").check()
        assert "Pendientes: 1" in app.texts()
        app.find_all("Button", text="Quitar")[1].click()
        app.wait(until=lambda: not app.get("save").loading)
        assert json.loads(file.read_text(encoding="utf-8")) == [{"id": 1, "name": "Pan", "done": True}]
    with mount(EXAMPLES / "compra" / "src" / "App.flux") as app:  # vuelve a cargar lo guardado
        app.wait(until=lambda: app.get("loaded"))
        assert app.find("Checkbox", text="Pan").value is True


def test_answer_dialog_accepts_or_cancels_a_confirm(tmp_path):
    app_file = tmp_path / "App.flux"
    app_file.write_text(
        """<script lang="python">
from fluxui import dialogs, state
answers = state([])

async def ask():
    answers.value = answers.value + [await dialogs.confirm("¿Seguro?")]
</script>
<Window><Button text="Preguntar" on:click={ask()} /></Window>
""",
        encoding="utf-8",
    )
    with mount(app_file) as app:
        for result in (True, False):
            app.find(text="Preguntar").click()
            app.wait(0.02)
            app.answer_dialog(result)
        assert list(app.get("answers")) == [True, False]


def test_apps_with_modules_of_the_same_name_do_not_mix(tmp_path):
    for name in ("una", "otra"):
        (tmp_path / name / "services").mkdir(parents=True)
        (tmp_path / name / "services" / "datos.py").write_text(f"NOMBRE = {name!r}\n", encoding="utf-8")
        (tmp_path / name / "App.flux").write_text(
            '<script lang="python">\nfrom services.datos import NOMBRE\n</script>\n<Window><Text>{NOMBRE}</Text></Window>\n',
            encoding="utf-8",
        )
    for name in ("una", "otra", "una"):
        with mount(tmp_path / name / "App.flux") as app:
            assert app.texts() == [name]
