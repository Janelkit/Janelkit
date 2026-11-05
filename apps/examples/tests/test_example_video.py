"""apps/examples/video: vídeo generado, un modelo lento en otro hilo, cajas sobre la imagen y
un punto marcado con el clic en píxeles de la imagen."""
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


def test_a_click_on_the_image_marks_a_point_in_its_pixels():
    with mount(VIDEO / "src" / "App.janel") as app:
        app.window.resize(960, 640)
        app.wait(1, until=lambda: app.namespace["frames"].size is not None)
        video = app.find(label="Vídeo")
        w, h = video.item.width(), video.item.height()
        s = min(w / 1280, h / 720)  # fit="contain": la imagen, centrada y con bandas
        ox, oy = (w - 1280 * s) / 2, (h - 720 * s) / 2
        video.click(x=ox + 40 * s, y=oy + 360 * s)  # x = 40 de la imagen: ahí no pasan los cuadrados
        px, py = app.get("punto")
        assert abs(px - 40) <= 2 and abs(py - 360) <= 2
        assert f"Punto: {px}, {py}" in app.texts()
