"""Pantallas: `screens` reactivo y `<Window screen= fullscreen=>`.

Caso del primer usuario externo: una ventana de proyección a pantalla completa en otra
pantalla. Para probar varias pantallas, un proceso hijo arranca Qt con la plataforma
`offscreen` y un archivo de configuración con dos pantallas («Principal» y «Proyector»).
"""
import json
import os
import subprocess
import sys
import textwrap

from janelkit import Screen, screens

WINDOW_APP = """<script>
from janelkit import state, screens
target = state(1)
full = state(True)
</script>
<Window title="Proyección" width={400} height={300} screen={target} fullscreen={full}>
  <Column>
    {#each screens as s}<Text>{s.name} {s.width}x{s.height}</Text>{/each}
  </Column>
</Window>
"""

CHILD = textwrap.dedent("""
    import json, sys
    from pathlib import Path
    from janelkit import screens
    from janelkit.inspect import mount

    def where(app):
        w = app.window
        return {"screen": w.screen().name(), "fullscreen": w.visibility().name == "FullScreen",
                "x": w.x(), "y": w.y()}

    out = {}
    with mount(Path(sys.argv[1])) as app:
        app.wait(0.2)
        out["screens"] = [list(s) for s in screens.value]
        out["texts"] = app.texts()
        out["start"] = where(app)                       # screen=1, fullscreen=True
        app.namespace["target"].value = 0               # cambiar de pantalla estando a pantalla completa
        app.wait(0.2)
        out["moved"] = where(app)
        app.namespace["full"].value = False
        app.wait(0.2)
        out["windowed"] = where(app)
        app.namespace["target"].value = "Proyector"     # por nombre
        app.wait(0.2)
        out["by_name"] = where(app)
        app.namespace["target"].value = 7               # no existe: se queda donde está
        app.wait(0.2)
        out["missing"] = where(app)
    print(json.dumps(out))
""")

SCREENS = {"screens": [
    {"name": "Principal", "x": 0, "y": 0, "width": 1280, "height": 800, "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1},
    {"name": "Proyector", "x": 1280, "y": 0, "width": 1920, "height": 1080, "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1},
]}


def run_with_two_screens(tmp_path) -> dict:
    (tmp_path / "screens.json").write_text(json.dumps(SCREENS), encoding="utf-8")
    (tmp_path / "App.janel").write_text(WINDOW_APP, encoding="utf-8")
    (tmp_path / "child.py").write_text(CHILD, encoding="utf-8")
    # Ruta relativa: Qt separa los parámetros de la plataforma con ':', que una ruta de Windows lleva.
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen:configfile=screens.json"}
    result = subprocess.run([sys.executable, "child.py", "App.janel"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_window_moves_between_screens_and_goes_fullscreen(tmp_path):
    out = run_with_two_screens(tmp_path)
    assert out["screens"] == [
        [0, "Principal", 1280, 800, 0, 0, True, 1.0],
        [1, "Proyector", 1920, 1080, 1280, 0, False, 1.0],
    ]
    assert out["texts"] == ["Principal 1280x800", "Proyector 1920x1080"]
    assert out["start"]["screen"] == "Proyector" and out["start"]["fullscreen"]
    # A pantalla completa no se puede mover: sale, cambia de pantalla y vuelve a entrar.
    assert out["moved"]["screen"] == "Principal" and out["moved"]["fullscreen"]
    assert out["windowed"]["screen"] == "Principal" and not out["windowed"]["fullscreen"]
    assert 0 <= out["windowed"]["x"] < 1280 and 0 <= out["windowed"]["y"] < 800
    assert out["by_name"]["screen"] == "Proyector" and not out["by_name"]["fullscreen"]
    assert 1280 <= out["by_name"]["x"] < 1280 + 1920  # dentro del proyector (la posición exacta es del sistema)
    assert out["missing"] == out["by_name"]


def test_screens_is_filled_when_the_app_starts(janel_app):
    assert len(screens.value) >= 1
    first = screens.value[0]
    assert isinstance(first, Screen) and first.index == 0 and first.width > 0
    assert sum(s.primary for s in screens.value) == 1


def test_screens_is_read_only(janel_app):
    import pytest

    with pytest.raises(AttributeError):
        screens.value = []
