import os
import subprocess
import sys
from pathlib import Path

import pytest

from fluxui import __version__
from fluxui.cli.main import main
from fluxui.cli.scaffolding import ScaffoldError, create_project
from fluxui.compiler import compile_file

EXPECTED_FILES = {
    "main.py",
    "src/App.flux",
    "src/services/users.py",
    "src/components/.gitkeep",
    "src/pages/.gitkeep",
    "assets/.gitkeep",
    "pyproject.toml",
    "README.md",
    ".gitignore",
}


def test_new_creates_expected_structure(tmp_path):
    result = create_project("mi-app", tmp_path)
    files = {p.relative_to(result.root).as_posix() for p in result.root.rglob("*") if p.is_file()}
    assert files == EXPECTED_FILES
    assert 'name = "mi-app"' in (result.root / "pyproject.toml").read_text(encoding="utf-8")
    assert f"fluxui>={__version__}" in (result.root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'title="mi-app"' in (result.root / "src" / "App.flux").read_text(encoding="utf-8")
    assert '"src" / "App.flux"' in (result.root / "main.py").read_text(encoding="utf-8")


def test_generated_app_compiles_without_warnings(tmp_path):
    root = create_project("demo", tmp_path).root
    compiled = compile_file(root / "src" / "App.flux")
    assert compiled.warnings == []


def test_new_refuses_non_empty_directory(tmp_path):
    target = tmp_path / "demo"
    target.mkdir()
    (target / "notas.txt").write_text("mío")
    with pytest.raises(ScaffoldError, match="no está vacío"):
        create_project("demo", tmp_path)
    assert (target / "notas.txt").read_text() == "mío"
    assert not (target / "main.py").exists()


def test_new_accepts_existing_empty_directory(tmp_path):
    (tmp_path / "demo").mkdir()
    assert (create_project("demo", tmp_path).root / "main.py").exists()


@pytest.mark.parametrize("bad", ["", "-x", "con espacio", "../fuera"])
def test_new_rejects_invalid_names(tmp_path, bad):
    with pytest.raises(ScaffoldError):
        create_project(bad, tmp_path)


def test_cli_new_reports_conflict_with_exit_code(tmp_path, capsys):
    assert main(["new", "demo", "--path", str(tmp_path)]) == 0
    assert "python main.py" in capsys.readouterr().out
    assert main(["new", "demo", "--path", str(tmp_path)]) == 1
    assert "no está vacío" in capsys.readouterr().err


def test_cli_parse_and_compile(tmp_path, capsys):
    app = tmp_path / "App.flux"
    app.write_text("<Window title=\"x\">\n  <Text>{1 + 1}</Text>\n</Window>\n", encoding="utf-8")
    assert main(["parse", str(app)]) == 0
    assert "<Window title=\"x\"> @1:1" in capsys.readouterr().out
    assert main(["compile", str(app)]) == 0
    assert "ApplicationWindow {" in capsys.readouterr().out


def test_cli_parse_error_exit_code(tmp_path, capsys):
    app = tmp_path / "App.flux"
    app.write_text("<Window>\n  <Column>\n</Window>\n", encoding="utf-8")
    assert main(["parse", str(app)]) == 1
    assert "App.flux:3:1: error" in capsys.readouterr().err


def test_cli_without_command_prints_help(capsys):
    assert main([]) == 2
    assert "new" in capsys.readouterr().out


def _run_main(project: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "FLUXUI_EXIT_AFTER_MS": "300"}
    return subprocess.run(
        [sys.executable, "main.py"], cwd=project, env=env, capture_output=True, text=True, timeout=60
    )


def test_generated_project_starts_with_python_main(tmp_path):
    """Recorrido `flux new` -> `python main.py` desde una carpeta fuera del repositorio."""
    root = create_project("arranque", tmp_path).root
    proc = _run_main(root)
    assert proc.returncode == 0, proc.stderr


def test_main_does_not_depend_on_working_directory(tmp_path):
    root = create_project("cwd", tmp_path).root
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "FLUXUI_EXIT_AFTER_MS": "300"}
    proc = subprocess.run(
        [sys.executable, str(root / "main.py")], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr


def test_compile_error_exits_with_flux_location(tmp_path):
    root = create_project("roto", tmp_path).root
    app = root / "src" / "App.flux"
    app.write_text(app.read_text(encoding="utf-8").replace("{/if}", ""), encoding="utf-8")
    proc = _run_main(root)
    assert proc.returncode == 1
    assert "App.flux:" in proc.stderr and "{#if}" in proc.stderr
