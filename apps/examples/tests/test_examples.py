"""Los ejemplos del repositorio deben compilar sin advertencias y montarse como lo hace run()."""
import sys
from pathlib import Path

import pytest

from janelkit.compiler import compile_file

EXAMPLES = sorted((Path(__file__).resolve().parents[1]).glob("*/src/App.janel"))


@pytest.fixture
def app_path(monkeypatch):
    """Reproduce run(): la carpeta src/ del ejemplo entra en sys.path; sus módulos no se comparten."""
    before = set(sys.modules)

    def use(app: Path) -> Path:
        monkeypatch.syspath_prepend(str(app.parent))
        return app

    yield use
    for name in set(sys.modules) - before:
        if name.split(".")[0] in ("services", "components", "pages"):
            del sys.modules[name]


@pytest.mark.parametrize("app", EXAMPLES, ids=lambda p: p.parent.parent.name)
def test_example_compiles_without_warnings(app):
    compiled = compile_file(app)
    assert compiled.all_warnings == []


@pytest.mark.parametrize("app", EXAMPLES, ids=lambda p: p.parent.parent.name)
def test_example_mounts(app, janel_app, app_path, caplog):
    compiled = compile_file(app_path(app))
    assert janel_app.check_tokens(compiled) == []
    m = janel_app.mount(compiled)
    janel_app.qt_app.processEvents()
    janel_app.unmount(m)
    assert "error" not in caplog.text.lower()


def test_there_are_examples():
    names = {p.parent.parent.name for p in EXAMPLES}
    assert {"counter", "todo", "todo-components"} <= names


def test_notes_example_flow(janel_app, app_path):
    """Recorrido de la app de notas: seleccionar, editar, guardar, crear, borrar y cambiar de tema."""
    from janelkit.testing import texts, visual_items
    from PySide6.QtCore import QMetaObject

    from janelkit import theme

    app = next(p for p in EXAMPLES if p.parent.parent.name == "notes")
    m = janel_app.mount(compile_file(app_path(app)))
    janel_app.qt_app.processEvents()
    ns = m.instance.namespace

    def items(kind):
        return [i for i in visual_items(m) if kind in i.metaObject().className() and i.isVisible()]

    def button(text):
        return next(b for b in items("JkButton") if b.property("text") == text)

    def press(item, method="click"):
        from janelkit.testing import click

        if method == "click":
            click(item)
        else:
            assert QMetaObject.invokeMethod(item, method)
        janel_app.qt_app.processEvents()

    try:
        cards = items("NoteCard")
        assert len(cards) == 3
        press(cards[1], "clicked")  # seleccionar la segunda tarjeta
        assert ns["current"].value["title"] == "Componentes"
        title_field = next(f for f in items("JkTextField") if f.property("text") == "Componentes")

        assert button("Guardar").property("enabled") is False
        title_field.setProperty("text", "Componentes .janel")
        assert QMetaObject.invokeMethod(title_field, "textEdited")
        assert "Cambios sin guardar" in texts(m)
        press(button("Guardar"))
        assert ns["notes"].value[0]["title"] == "Componentes .janel"  # la editada sube
        assert "Componentes .janel" in texts(m)
        assert "Cambios sin guardar" not in texts(m)

        press(button("Nueva"))
        assert len(ns["notes"].value) == 4 and ns["current"].value["title"] == ""
        press(button("Eliminar"))
        assert len(ns["notes"].value) == 3

        search = next(f for f in items("JkTextField") if f.property("placeholderText") == "Buscar en las notas")
        search.setProperty("text", "tokens")
        assert QMetaObject.invokeMethod(search, "textEdited")
        assert len(items("NoteCard")) == 1 and "1 de 3 notas" in texts(m)
        search.setProperty("text", "zzz")
        assert QMetaObject.invokeMethod(search, "textEdited")
        assert items("NoteCard") == [] and "Sin resultados para «zzz»" in texts(m)

        press(button("Tema oscuro"))
        assert theme.name == "dark" and button("Tema claro")
    finally:
        janel_app.unmount(m)


@pytest.mark.parametrize("app", EXAMPLES, ids=lambda p: p.parent.parent.name)
def test_example_runs_with_python_main(app):
    """`python main.py` arranca el ejemplo y termina limpio, sin errores ni avisos de QML."""
    import os
    import subprocess

    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "JANELKIT_EXIT_AFTER_MS": "500"}
    proc = subprocess.run(
        [sys.executable, "main.py"], cwd=app.parent.parent, env=env, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    # qt.qpa: plataforma offscreen; qt.multimedia: aceleración opcional de vídeo (VA-API, PipeWire) ausente en la CI.
    noise = [line for line in proc.stderr.splitlines() if line.strip() and not line.startswith(("qt.qpa", "qt.multimedia"))]
    assert noise == []


def test_books_example_flow_without_network(janel_app, app_path):
    """Búsqueda asíncrona: cargando, resultados, error y reintento (búsqueda simulada, sin red)."""
    import asyncio
    import time

    from janelkit.testing import click, texts, visual_items

    app = next(p for p in EXAMPLES if p.parent.parent.name == "books")
    m = janel_app.mount(compile_file(app_path(app)))
    calls = []

    def fake_search(q):
        calls.append(q)
        time.sleep(0.05)  # bloquea, pero en otro hilo
        if q == "mal":
            raise OSError("sin conexión")
        return [{"key": f"/w/{i}", "title": f"{q} {i}", "author": "Ana", "year": 2000 + i} for i in range(2)]

    m.instance.namespace["search"] = fake_search  # el script la importó de services.books
    ns = m.instance.namespace

    def search(q):
        ns["query"].value = q
        button = next(b for b in visual_items(m) if b.property("text") == "Buscar")
        click(button)

    try:
        assert texts(m)[-1] == "Escribe algo y pulsa Intro."
        search("dune")
        assert "Buscando «dune»…" in texts(m)
        janel_app.run_until(asyncio.sleep(0.3))
        assert "dune 0" in texts(m) and "Ana · 2001" in texts(m)
        search("mal")
        janel_app.run_until(asyncio.sleep(0.3))
        assert "No se pudo completar la búsqueda" in texts(m) and "sin conexión" in texts(m)
        assert calls == ["dune", "mal"]
    finally:
        janel_app.unmount(m)
