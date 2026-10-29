"""apps/examples/video: vídeo generado, un modelo lento en otro hilo y cajas sobre la imagen."""
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from janelkit.inspect import mount  # noqa: E402

VIDEO = Path(__file__).resolve().parents[1] / "video"


def test_a_slow_model_does_not_slow_the_video_and_its_boxes_are_clickable():
    with mount(VIDEO / "src" / "App.janel") as app:
        app.window.resize(960, 640)
        app.namespace["retardo"].value = 200
        app.wait(1.6, until=lambda: app.namespace["frames"].fps > 0 and app.get("fps_modelo") > 0)
        frames = app.namespace["frames"]
        assert frames.size == (1280, 720)
        assert 2 < app.get("fps_modelo") < 6
        # La vista no espera al modelo. Relativo y no una cifra fija: generar 1280×720 cuesta
        # distinto en cada máquina (12 fps en un ejecutor de Windows de la CI).
        assert frames.fps > 2 * app.get("fps_modelo")
        assert sorted(o[4] for o in app.get("objetos")) == ["azul", "rojo", "verde"]
        app.find(label="verde").click()
        assert app.get("elegido") == "verde"
