"""Experiencia de desarrollo: recarga al guardar, `janel dev` y `janel build`."""
import os
import subprocess
import sys

from janelkit.testing import texts

from janelkit.cli.build import build_project
from janelkit.cli.main import main
from janelkit.cli.scaffolding import create_project
from janelkit.compiler import compile_file


def test_reload_replaces_view_and_keeps_last_good_version_on_error(tmp_path, janel_app, capsys):
    from janelkit.qt_backend.application import DevReloader

    app = tmp_path / "App.janel"
    child = tmp_path / "Saludo.janel"
    child.write_text("<text>hola</text>", encoding="utf-8")
    app.write_text("<script>\nfrom Saludo import Saludo\n</script>\n<column><text>v1</text><Saludo /></column>", encoding="utf-8")
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

        child.write_text("<text>{sin_definir}</text>", encoding="utf-8")
        reloader.reload()
        assert reloader.mounted is new  # la versión correcta sigue montada
        assert reloader._error_window.property("visible") is True
        assert "sin_definir" in reloader._error_window.property("message")

        child.write_text("<text>adiós</text>", encoding="utf-8")
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
    (root / "src" / "components" / "Suelto.janel").write_text("<text>sin usar</text>", encoding="utf-8")
    assert main(["build", str(root)]) == 0
    out = root / "build" / "qml"
    assert (out / "App.qml").is_file()
    assert (out / "components" / "Suelto.qml").is_file()
    assert "no crea un ejecutable" in capsys.readouterr().out


def test_build_reports_errors_in_unused_components(tmp_path):
    root = create_project("b2", tmp_path).root
    (root / "src" / "components" / "Roto.janel").write_text("<text>{nada}</text>", encoding="utf-8")
    result = build_project(root)
    assert not result.ok
    assert len(result.errors) == 1 and result.errors[0].location.file.endswith("Roto.janel")


def test_build_accepts_window_components_opened_with_open_window(tmp_path):
    root = create_project("b3", tmp_path).root
    (root / "src" / "components" / "Ventana.janel").write_text('<window title="otra"><text>hola</text></window>', encoding="utf-8")
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
    app.write_text("<script>\nfrom widgets.Box import Box\n</script>\n<column><Box size={3} /></column>", encoding="utf-8")
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
        "<script>\nfrom janelkit import state\nclicks = state(0)\n</script>\n<text>clicks {clicks}</text>", encoding="utf-8"
    )
    app = tmp_path / "App.janel"
    app.write_text(
        "<script>\nfrom janelkit import state\nfrom components.Counter import Counter\nname = state('')\nrows = state(['a', 'b'])\n</script>\n"
        "<column><textfield bind:value={name} /><Counter />{#each rows as r (r)}<Counter />{/each}</column>\n"
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
                       .replace("<column>", "<column>\n  <text>nuevo</text>"), encoding="utf-8")  # fmt: skip
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


def test_state_survives_a_restart_through_the_state_file(tmp_path, janel_app, monkeypatch):
    """Lo que deja `save_state` lo recupera otro proceso: aquí, una segunda vista montada con lo leído del archivo."""
    from janelkit.qt_backend import application
    from janelkit.runtime import component as runtime

    app = tmp_path / "App.janel"
    child = tmp_path / "Campo.janel"
    child.write_text('<script>\nfrom janelkit import state\ntexto = state("")\nabierto = state(open)\n</script>\n<text>{texto}</text>', encoding="utf-8")
    app.write_text(
        "<script>\nfrom janelkit import state\nfrom Campo import Campo\nn = state(0)\nfilas = state([])\n</script>\n"
        "<column><text>n={n} filas={len(filas)}</text><Campo /></column>",
        encoding="utf-8",
    )
    state_file = tmp_path / "state.pickle"
    monkeypatch.setenv(application.DEV_STATE_ENV, str(state_file))
    compiled = compile_file(app)
    mounted = janel_app.mount(compiled)
    reloader = application.DevReloader(janel_app, app, mounted, compiled.files)
    try:
        mounted.instance.namespace["n"].value = 7
        mounted.instance.namespace["filas"].value = [{"id": 1}, {"id": 2}]
        mounted.instance.children[0].namespace["texto"].value = "escrito"
        mounted.root.setGeometry(40, 50, 333, 222)
        assert reloader.save_state() is True
    finally:
        reloader._request_timer.stop()
        janel_app.unmount(mounted)

    # El script de Campo cambia entre un proceso y otro: su estado empieza de cero, el de App se conserva.
    child.write_text(child.read_text(encoding="utf-8").replace('state("")', 'state("nuevo")'), encoding="utf-8")
    snapshot, geometry = application._load_dev_state()
    assert geometry == (40, 50, 333, 222)
    runtime.hot_reload = snapshot
    try:
        again = janel_app.mount(compile_file(app))
    finally:
        runtime.hot_reload = None
    try:
        janel_app.qt_app.processEvents()
        assert texts(again) == ["n=7 filas=2", "nuevo"]
        assert snapshot.restored == 1 and snapshot.reset_files == {"Campo.janel"}
    finally:
        janel_app.unmount(again)


def test_unpicklable_state_is_left_out_without_losing_the_rest(tmp_path, janel_app):
    from janelkit.runtime.component import HotReload

    app = tmp_path / "App.janel"
    app.write_text("<script>\nfrom janelkit import state\nn = state(3)\nfn = state(lambda: 1)\n</script>\n<text>{n}</text>", encoding="utf-8")
    mounted = janel_app.mount(compile_file(app))
    try:
        loaded = HotReload.load(HotReload(mounted.instance).dump())
    finally:
        janel_app.unmount(mounted)
    (script, values), = loaded.saved.values()
    assert values == {"n": 3}


def test_janel_dev_keeps_state_when_a_py_file_changes(tmp_path):
    """De punta a punta: cambia un .py, el supervisor reinicia y el proceso nuevo sigue con el estado del anterior."""
    import time

    root = create_project("estado", tmp_path).root
    log = root / "ticks.txt"
    service = root / "src" / "services" / "users.py"
    (root / "src" / "App.janel").write_text(
        "<script>\nimport os\nfrom janelkit import state, interval\nn = state(0)\n\n@interval(50)\ndef tick():\n    n.value += 1\n"
        f"    with open({str(log)!r}, 'a') as f:\n        print(os.getpid(), n.value, file=f)\n</script>\n"
        '<window title="t"><text>{n}</text></window>',
        encoding="utf-8",
    )
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "JANELKIT_EXIT_AFTER_MS": "6000"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "janelkit.cli.main", "dev", str(root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
    )
    try:
        deadline = time.monotonic() + 30
        while not (log.is_file() and len(log.read_text().splitlines()) >= 5):
            assert time.monotonic() < deadline and proc.poll() is None, "la aplicación no llegó a arrancar"
            time.sleep(0.05)
        service.write_text(service.read_text(encoding="utf-8") + "\n# cambio\n", encoding="utf-8")
        out, err = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, err
    ticks = [tuple(map(int, line.split())) for line in log.read_text().splitlines()]
    first_pid = ticks[0][0]
    before = [n for pid, n in ticks if pid == first_pid]
    after = [n for pid, n in ticks if pid != first_pid]
    assert after, err
    # Sigue donde iba (un tic puede colarse entre guardar y salir), no desde cero.
    assert before[-1] <= after[0] <= before[-1] + 1 and after[0] > 4, (before[-3:], after[:3])
    assert "estado conservado en 1 componente(s)" in err
