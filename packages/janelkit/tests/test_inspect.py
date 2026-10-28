"""API pública de inspección (janelkit.inspect): montar sin ventana, buscar, actuar y esperar."""
import sys
from pathlib import Path

import pytest

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
        plus = app.find("Button", text="Clicks: 0")
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
        assert app.find("Checkbox", text="Comprar pan").value is False
        app.find("Checkbox", text="Comprar pan").check()
        assert app.get("todos")[-1]["done"] is True
        app.find("Button", text="Pendientes").click()
        app.wait(0.2)  # las filas del ejemplo salen con transition:fade
        assert app.find_all("Checkbox", text="Comprar pan") == []
        with pytest.raises(InspectError, match="hay 0"):
            app.find(text="no existe")


def test_disabled_controls_cannot_be_used():
    with mount(EXAMPLES / "todo" / "src" / "App.janel") as app:
        add = app.find("Button", text="Añadir")
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
<Column>
  <Button on:click={load.run("hola")}>Cargar</Button>
  <Select id="color" options={["rojo", {"label": "Verde", "value": "g"}]} />
  <RadioGroup id="size" options={["S", "M"]} />
  <Tabs id="tabs" options={["uno", "dos"]} />
  <Slider id="vol" />
  {#if load.loading}<Text>Cargando…</Text>{:else}<Text>{load.value}</Text>{/if}
</Column>
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
    app_file.write_text('<Select id="s" options={["a"]} />', encoding="utf-8")
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
        app.find("Checkbox", text="Pan").check()
        assert "Pendientes: 1" in app.texts()
        app.find_all("Button", text="Quitar")[1].click()
        app.wait(until=lambda: not app.get("save").loading)
        assert json.loads(file.read_text(encoding="utf-8")) == [{"id": 1, "name": "Pan", "done": True}]
    with mount(EXAMPLES / "compra" / "src" / "App.janel") as app:  # vuelve a cargar lo guardado
        app.wait(until=lambda: app.get("loaded"))
        assert app.find("Checkbox", text="Pan").value is True


def test_apps_with_modules_of_the_same_name_do_not_mix(tmp_path):
    for name in ("una", "otra"):
        (tmp_path / name / "services").mkdir(parents=True)
        (tmp_path / name / "services" / "datos.py").write_text(f"NOMBRE = {name!r}\n", encoding="utf-8")
        (tmp_path / name / "App.janel").write_text(
            '<script lang="python">\nfrom services.datos import NOMBRE\n</script>\n<Window><Text>{NOMBRE}</Text></Window>\n',
            encoding="utf-8",
        )
    for name in ("una", "otra", "una"):
        with mount(tmp_path / name / "App.janel") as app:
            assert app.texts() == [name]
