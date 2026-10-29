"""<Video> y Frames: fotogramas de cualquier hilo, el último gana, capa sobre la imagen."""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtGui import QImage

from janelkit import Frames
from janelkit.inspect import mount


@pytest.fixture
def app_from():
    apps = []

    def run(source: str, width=400, height=400):
        d = Path(tempfile.mkdtemp())
        (d / "App.janel").write_text(source, encoding="utf-8")
        ctx = mount(d / "App.janel")
        app = ctx.__enter__()
        apps.append(ctx)
        app.window.resize(width, height)
        app.wait(0.05)
        return app

    yield run
    for ctx in apps:
        ctx.__exit__(None, None, None)


def image(w: int, h: int, pixel: bytes = b"\x00\x00\x00") -> memoryview:
    """Una imagen de un solo color (alto × ancho × canales), sin numpy."""
    return memoryview(bytearray(pixel * (w * h))).cast("B", (h, w, len(pixel)))


def outputs(app) -> list[QObject]:
    return [o for o in app.window.findChildren(QObject) if o.metaObject().className() == "QQuickVideoOutput"]


def shown(app, i: int = 0) -> QImage:
    return outputs(app)[i].property("videoSink").videoFrame().toImage()


def box(app, label: str) -> tuple[float, float, float, float]:
    item = app.find(label=label).item
    p = item.mapToItem(None, 0, 0)
    return (p.x(), p.y(), item.width(), item.height())


APP = """<script>
import threading
from janelkit import Frames, spawn, state

frames = Frames(color="bgr")
recibidos = state([])

async def procesar():
    async for img in frames:
        recibidos.value.append(img)

spawn(procesar())

def emitir(imagenes):
    t = threading.Thread(target=lambda: [frames.push(i) for i in imagenes])
    t.start()
    t.join()
</script>
<Column>
  <Video source={frames} width={400} height={400} label="Cámara">
    <flex class="caja" label="caja" />
  </Video>
  <Text>{frames.size}</Text>
</Column>
<style>
.caja { position: absolute; left: 50%; top: 0; width: 25%; height: 100% }
</style>
"""


def test_frames_pushed_from_another_thread_reach_the_video():
    app_ctx = None
    with mount_source(APP) as app:
        app_ctx = app
        app.namespace["emitir"]([image(64, 36, b"\x00\x00\xff")])  # rojo, en BGR
        app.wait(0.05)
        img = shown(app)
        assert (img.width(), img.height()) == (64, 36)
        assert img.pixelColor(0, 0).name() == "#ff0000"
        assert app.texts()[-1] == "(64, 36)"
    assert app_ctx is not None


def test_the_latest_frame_wins_and_async_for_gets_it():
    with mount_source(APP) as app:
        imagenes = [image(8, 8) for _ in range(30)]
        app.namespace["emitir"](imagenes)  # todos antes de que la interfaz entregue ninguno
        app.wait(0.05)
        recibidos = app.get("recibidos")
        assert len(recibidos) == 1 and recibidos[0] is imagenes[-1]
        app.namespace["emitir"](imagenes[:1])
        app.wait(0.05)
        assert len(app.get("recibidos")) == 2


def test_the_overlay_covers_exactly_the_visible_image():
    with mount_source(APP) as app:
        app.namespace["emitir"]([image(640, 360)])  # 16:9 en 400 × 400: bandas arriba y abajo
        app.wait(0.05)
        assert box(app, "caja") == (200, 87.5, 100, 225)
        app.namespace["emitir"]([image(200, 400)])  # 1:2: bandas a los lados
        app.wait(0.05)
        assert box(app, "caja") == (200, 0, 50, 400)


def test_fit_cover_crops_and_the_overlay_follows(app_from):
    app = app_from(APP.replace("<Video source={frames}", '<Video source={frames} fit="cover"'))
    app.namespace["emitir"]([image(800, 400)])  # 2:1 recortada a 400 × 400: la imagen mide 800 × 400
    app.wait(0.05)
    assert box(app, "caja") == (200, 0, 200, 400)


def test_formats_and_errors():
    frames = Frames()  # rgb
    frames.push(image(2, 2, b"\xff\x00\x00"))
    frames.push(memoryview(bytearray(b"\x80" * 4)).cast("B", (2, 2)))  # gris
    with pytest.raises(TypeError, match="4 canales"):
        frames.push(image(2, 2, b"\x00\x00\x00\x00"))
    with pytest.raises(TypeError, match="un array"):
        frames.push([[0, 0], [0, 0]])
    with pytest.raises(TypeError, match="bytes"):
        frames.push(memoryview(bytearray(16)).cast("f", (2, 2)))
    with pytest.raises(ValueError, match="color"):
        Frames(color="yuv")
    rgba = Frames(color="rgba")
    rgba.push(image(2, 2, b"\x00\x00\xff\x80"))
    q = QImage(4, 2, QImage.Format.Format_RGB32)
    frames.push(q)
    assert frames.latest() is q


def test_a_non_contiguous_array_is_copied_right(app_from):
    np = pytest.importorskip("numpy")  # memoryview no recorta en varias dimensiones
    app = app_from(APP.replace('Frames(color="bgr")', "Frames()"))
    rows = np.array([[[255, 0, 0]] * 4, [[0, 0, 255]] * 4], dtype=np.uint8)  # 2 filas de 4: roja y azul
    app.namespace["emitir"]([rows[::2]])  # solo la fila roja, sin copiar
    app.wait(0.05)
    img = shown(app)
    assert (img.width(), img.height()) == (4, 1) and img.pixelColor(3, 0).name() == "#ff0000"


def test_size_fps_and_clear(app_from):
    app = app_from(APP)
    frames = app.namespace["frames"]
    frames._hub._idle.setInterval(100)
    parar = threading.Event()

    def emitir():
        while not parar.is_set():
            frames.push(image(16, 16))
            parar.wait(0.01)

    t = threading.Thread(target=emitir)
    t.start()
    try:
        app.wait(1.2)
        assert frames.fps > 10
    finally:
        parar.set()
        t.join()
    app.wait(0.3)
    assert frames.fps == 0
    frames.clear()
    app.wait(0.02)
    assert frames.size is None and frames.latest() is None
    assert not outputs(app)[0].property("videoSink").videoFrame().isValid()


def test_a_video_that_goes_away_lets_go_of_its_sink(app_from):
    app = app_from("""<script>
from janelkit import Frames, state
frames = Frames()
ver = state(True)
</script>
<Column>
  {#if ver}<Video source={frames} />{/if}
</Column>""")
    frames = app.namespace["frames"]
    assert len(frames._hub._sinks) == 1
    app.namespace["ver"].value = False
    app.wait(0.05)
    assert frames._hub._sinks == []
    frames.push(image(4, 4, b"\x00\x00\x00"))  # sin vistas: no falla
    app.namespace["ver"].value = True
    app.wait(0.05)
    assert len(frames._hub._sinks) == 1
    assert frames._hub._sinks[0].videoFrame().isValid()  # muestra el último al engancharse


def test_the_documented_example_runs(app_from):
    app = app_from("""<script>
from janelkit import Frames, state
frames = Frames(color="bgr")
caras = state([])

def pct(valor, eje):              # de píxeles de la imagen a % de la capa
    tamaño = frames.size or (1, 1)
    return f"{100 * valor / tamaño[eje]}%"
</script>
<Column>
  <Video source={frames} width={400} height={400} label="Cámara">
    {#each caras as c}
      <flex class="cara" label="cara" style={{"left": pct(c[0], 0), "top": pct(c[1], 1), "width": pct(c[2], 0), "height": pct(c[3], 1)}} />
    {/each}
  </Video>
  <Text>{frames.fps:.0f} fps</Text>
</Column>
<style>
.cara { position: absolute; border: 2px solid red }
</style>""")
    frames = app.namespace["frames"]
    frames.push(image(800, 800))
    app.wait(0.02)
    app.namespace["caras"].value = [(200, 400, 100, 200)]
    app.wait(0.05)
    assert box(app, "cara") == (100, 200, 50, 100)


def mount_source(source: str):
    d = Path(tempfile.mkdtemp())
    (d / "App.janel").write_text(source, encoding="utf-8")
    return _Resized(mount(d / "App.janel"))


class _Resized:
    def __init__(self, ctx):
        self.ctx = ctx

    def __enter__(self):
        app = self.ctx.__enter__()
        app.window.resize(400, 400)
        app.wait(0.05)
        return app

    def __exit__(self, *exc):
        return self.ctx.__exit__(*exc)
