"""Experiencia de desarrollo: recarga al guardar, `janel dev` y `janel build`."""
import os
import subprocess
import sys

from conftest import texts

from janelkit.cli.build import build_project
from janelkit.cli.main import main
from janelkit.cli.scaffolding import create_project
from janelkit.compiler import compile_file


def test_reload_replaces_view_and_keeps_last_good_version_on_error(tmp_path, janel_app, capsys):
    from janelkit.qt_backend.application import DevReloader

    app = tmp_path / "App.janel"
    child = tmp_path / "Saludo.janel"
    child.write_text("<Text>hola</Text>", encoding="utf-8")
    app.write_text("<script>\nfrom Saludo import Saludo\n</script>\n<Column><Text>v1</Text><Saludo /></Column>", encoding="utf-8")
    compiled = compile_file(app)
    mounted = janel_app.mount(compiled)
    reloader = DevReloader(janel_app, app, mounted, compiled.files)
    assert str(child.resolve()) in reloader.watcher.files()
    try:
        assert texts(mounted) == ["v1", "hola"]
        mounted.root.setGeometry(40, 50, 333, 222)

        app.write_text(app.read_text(encoding="utf-8").replace("v1", "v2"), encoding="utf-8")
        reloader.reload()
        new = reloader.mounted
        assert new is not mounted and mounted not in janel_app.mounted
        assert texts(new) == ["v2", "hola"]
        assert new.root.geometry().width() == 333  # conserva el tamaño de la ventana

        child.write_text("<Text>{sin_definir}</Text>", encoding="utf-8")
        reloader.reload()
        assert reloader.mounted is new  # la versión correcta sigue montada
        assert reloader._error_window.property("visible") is True
        assert "sin_definir" in reloader._error_window.property("message")

        child.write_text("<Text>adiós</Text>", encoding="utf-8")
        reloader.reload()
        assert texts(reloader.mounted) == ["v2", "adiós"]
        assert reloader._error_window.property("visible") is False
    finally:
        if reloader.mounted in janel_app.mounted:
            janel_app.unmount(reloader.mounted)
        reloader.hide_error()
    assert "[janel dev]" in capsys.readouterr().err


def test_janel_dev_runs_main_and_returns_its_exit_code(tmp_path):
    root = create_project("dev-app", tmp_path).root
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "JANELKIT_EXIT_AFTER_MS": "400"}
    proc = subprocess.run(
        [sys.executable, "-m", "janelkit.cli.main", "dev", str(root)],
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stderr
    assert "observando cambios" in proc.stderr


def test_dev_mode_starts_even_with_compile_errors(tmp_path):
    root = create_project("roto", tmp_path).root
    app = root / "src" / "App.janel"
    app.write_text(app.read_text(encoding="utf-8").replace("{/if}", ""), encoding="utf-8")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "JANELKIT_EXIT_AFTER_MS": "400", "JANELKIT_DEV": "1"}
    proc = subprocess.run([sys.executable, "main.py"], cwd=root, capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0
    assert "{#if}" in proc.stderr and "observando cambios" in proc.stderr


def test_dev_requires_a_project(tmp_path, capsys):
    assert main(["dev", str(tmp_path)]) == 1
    assert "main.py" in capsys.readouterr().err


def test_build_writes_qml_for_all_components(tmp_path, capsys):
    root = create_project("b", tmp_path).root
    (root / "src" / "components" / "Suelto.janel").write_text("<Text>sin usar</Text>", encoding="utf-8")
    assert main(["build", str(root)]) == 0
    out = root / "build" / "qml"
    assert (out / "App.qml").is_file()
    assert (out / "components" / "Suelto.qml").is_file()
    assert "no crea un ejecutable" in capsys.readouterr().out


def test_build_reports_errors_in_unused_components(tmp_path):
    root = create_project("b2", tmp_path).root
    (root / "src" / "components" / "Roto.janel").write_text("<Text>{nada}</Text>", encoding="utf-8")
    result = build_project(root)
    assert not result.ok
    assert len(result.errors) == 1 and result.errors[0].location.file.endswith("Roto.janel")


def test_build_accepts_window_components_opened_with_open_window(tmp_path):
    root = create_project("b3", tmp_path).root
    (root / "src" / "components" / "Ventana.janel").write_text('<Window title="otra"><Text>hola</Text></Window>', encoding="utf-8")
    result = build_project(root)
    assert result.ok, [d.format() for d in result.errors]


def test_qml_files_restart_the_process_instead_of_reloading(tmp_path, janel_app):
    """Un .qml propio no se recarga en el proceso (Qt < 6.12 no lo vuelve a leer): lo reinicia el supervisor."""
    from janelkit.cli.dev import restart_files
    from janelkit.qt_backend.application import DevReloader

    widget = tmp_path / "widgets" / "Box.qml"
    widget.parent.mkdir()
    widget.write_text('import QtQuick\nRectangle { objectName: "box"; property real size: 1; width: 10 }', encoding="utf-8")
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    app = tmp_path / "App.janel"
    app.write_text("<script>\nfrom widgets.Box import Box\n</script>\n<Column><Box size={3} /></Column>", encoding="utf-8")
    compiled = compile_file(app)
    assert str(widget) in compiled.files
    reloader = DevReloader(janel_app, app, janel_app.mount(compiled), compiled.files)
    try:
        watched = set(reloader.watcher.files())
        assert str(app.resolve()) in watched and str(widget.resolve()) not in watched
        assert set(restart_files(tmp_path)) == {str(tmp_path / "main.py"), str(widget)}
    finally:
        if reloader.mounted in janel_app.mounted:
            janel_app.unmount(reloader.mounted)


def test_reload_keeps_state_unless_the_script_changed(tmp_path, janel_app, capsys):
    from janelkit.qt_backend.application import DevReloader

    child = tmp_path / "components" / "Counter.janel"
    child.parent.mkdir()
    child.write_text(
        "<script>\nfrom janelkit import state\nclicks = state(0)\n</script>\n<Text>clicks {clicks}</Text>", encoding="utf-8"
    )
    app = tmp_path / "App.janel"
    app.write_text(
        "<script>\nfrom janelkit import state\nfrom components.Counter import Counter\nname = state('')\nrows = state(['a', 'b'])\n</script>\n"
        "<Column><TextField bind:value={name} /><Counter />{#each rows as r (r)}<Counter />{/each}</Column>\n"
        "<style></style>",
        encoding="utf-8",
    )
    compiled = compile_file(app)
    reloader = DevReloader(janel_app, app, janel_app.mount(compiled), compiled.files)

    def counters():
        return [c.namespace["clicks"] for c in reloader.mounted.instance.children]

    try:
        ns = reloader.mounted.instance.namespace
        ns["name"].value = "Ana"
        ns["rows"].value.reverse()  # b, a: cada fila conserva su contador por clave
        for state, value in zip(counters(), [1, 20, 10]):
            state.value = value  # Counter fijo, fila "a" (creada primero), fila "b"
        before = {c.hmr_path: c.namespace["clicks"].value for c in reloader.mounted.instance.children}

        # Cambiar solo estilo y plantilla del raíz: se conserva todo.
        app.write_text(app.read_text(encoding="utf-8").replace("<style></style>", "<style>.x { gap: 4px; }</style>")
                       .replace("<Column>", "<Column>\n  <Text>nuevo</Text>"), encoding="utf-8")  # fmt: skip
        reloader.reload()
        ns = reloader.mounted.instance.namespace
        assert ns["name"].value == "Ana" and list(ns["rows"].value) == ["b", "a"]
        after = {c.hmr_path: c.namespace["clicks"].value for c in reloader.mounted.instance.children}
        assert after == before
        assert "estado conservado en 4 componente(s)" in capsys.readouterr().err

        # Cambiar el script del hijo: el hijo vuelve a empezar; el raíz conserva lo suyo.
        child.write_text(child.read_text(encoding="utf-8").replace("state(0)", "state(100)"), encoding="utf-8")
        reloader.reload()
        assert reloader.mounted.instance.namespace["name"].value == "Ana"
        assert [c.value for c in counters()] == [100, 100, 100]
        assert "script cambiado, estado reiniciado: Counter.janel" in capsys.readouterr().err
    finally:
        if reloader.mounted in janel_app.mounted:
            janel_app.unmount(reloader.mounted)
