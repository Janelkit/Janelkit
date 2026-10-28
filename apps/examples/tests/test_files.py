"""apps/examples/files: aplicación de validación del explorador de archivos (usa janelkit-desktop)."""
import sys
from pathlib import Path

import pytest

from janelkit.inspect import mount

EXAMPLES = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolate_modules(monkeypatch, janel_app):
    """Cada ejemplo trae sus propios `services`/`components`: no compartirlos entre pruebas."""
    before = set(sys.modules)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in set(sys.modules) - before:
        if name.split(".")[0] in ("services", "components", "widgets"):
            del sys.modules[name]


def test_files_example_validation_app(tmp_path, monkeypatch):
    """Aplicación de validación: carpetas, filtro, orden, vista previa, contexto, atajos y diálogos."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guia.md").write_text("# Guía\nHola", encoding="utf-8")
    (tmp_path / "b.txt").write_text("contenido de b" * 100, encoding="utf-8")  # 1400 bytes
    (tmp_path / "a.py").write_text("print('a')", encoding="utf-8")
    (tmp_path / ".oculto").write_text("x", encoding="utf-8")
    (tmp_path / "foto.png").write_bytes(b"\x89PNG")
    monkeypatch.setenv("JANEL_FILES_START", str(tmp_path))

    with mount(EXAMPLES / "files" / "src" / "App.janel") as app:
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
