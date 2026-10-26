"""Experiencia de desarrollo: recarga al guardar, `flux dev` y `flux build`."""
import os
import subprocess
import sys

from conftest import texts

from fluxui.cli.build import build_project
from fluxui.cli.main import main
from fluxui.cli.scaffolding import create_project
from fluxui.compiler import compile_file


def test_reload_replaces_view_and_keeps_last_good_version_on_error(tmp_path, flux_app, capsys):
    from fluxui.qt_backend.application import DevReloader

    app = tmp_path / "App.flux"
    child = tmp_path / "Saludo.flux"
    child.write_text("<Text>hola</Text>", encoding="utf-8")
    app.write_text("<script>\nfrom Saludo import Saludo\n</script>\n<Column><Text>v1</Text><Saludo /></Column>", encoding="utf-8")
    compiled = compile_file(app)
    mounted = flux_app.mount(compiled)
    reloader = DevReloader(flux_app, app, mounted, compiled.files)
    assert str(child.resolve()) in reloader.watcher.files()
    try:
        assert texts(mounted) == ["v1", "hola"]
        mounted.root.setGeometry(40, 50, 333, 222)

        app.write_text(app.read_text(encoding="utf-8").replace("v1", "v2"), encoding="utf-8")
        reloader.reload()
        new = reloader.mounted
        assert new is not mounted and mounted not in flux_app.mounted
        assert texts(new) == ["v2", "hola"]
        assert new.root.geometry().width() == 333  # conserva el tamaño de la ventana

        child.write_text("<Text>{sin_definir}</Text>", encoding="utf-8")
        os.utime(child, (1, 1))  # forzar una marca de tiempo distinta
        reloader.reload()
        assert reloader.mounted is new  # la versión correcta sigue montada
        assert reloader._error_window.property("visible") is True
        assert "sin_definir" in reloader._error_window.property("message")

        child.write_text("<Text>adiós</Text>", encoding="utf-8")
        reloader.reload()
        assert texts(reloader.mounted) == ["v2", "adiós"]
        assert reloader._error_window.property("visible") is False
    finally:
        if reloader.mounted in flux_app.mounted:
            flux_app.unmount(reloader.mounted)
        reloader.hide_error()
    assert "[flux dev]" in capsys.readouterr().err


def test_flux_dev_runs_main_and_returns_its_exit_code(tmp_path):
    root = create_project("dev-app", tmp_path).root
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "FLUXUI_EXIT_AFTER_MS": "400"}
    proc = subprocess.run(
        [sys.executable, "-m", "fluxui.cli.main", "dev", str(root)],
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stderr
    assert "observando cambios" in proc.stderr


def test_dev_mode_starts_even_with_compile_errors(tmp_path):
    root = create_project("roto", tmp_path).root
    app = root / "src" / "App.flux"
    app.write_text(app.read_text(encoding="utf-8").replace("{/if}", ""), encoding="utf-8")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "FLUXUI_EXIT_AFTER_MS": "400", "FLUXUI_DEV": "1"}
    proc = subprocess.run([sys.executable, "main.py"], cwd=root, capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0
    assert "{#if}" in proc.stderr and "observando cambios" in proc.stderr


def test_dev_requires_a_project(tmp_path, capsys):
    assert main(["dev", str(tmp_path)]) == 1
    assert "main.py" in capsys.readouterr().err


def test_build_writes_qml_for_all_components(tmp_path, capsys):
    root = create_project("b", tmp_path).root
    (root / "src" / "components" / "Suelto.flux").write_text("<Text>sin usar</Text>", encoding="utf-8")
    assert main(["build", str(root)]) == 0
    out = root / "build" / "qml"
    assert (out / "App.qml").is_file()
    assert (out / "components" / "Suelto.qml").is_file()
    assert "no crea un ejecutable" in capsys.readouterr().out


def test_build_reports_errors_in_unused_components(tmp_path):
    root = create_project("b2", tmp_path).root
    (root / "src" / "components" / "Roto.flux").write_text("<Text>{nada}</Text>", encoding="utf-8")
    result = build_project(root)
    assert not result.ok
    assert len(result.errors) == 1 and result.errors[0].location.file.endswith("Roto.flux")
