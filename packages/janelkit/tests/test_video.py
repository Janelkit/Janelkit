"""<video> y Frames: fotogramas de cualquier hilo, el último gana, capa sobre la imagen."""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from janelkit import Frames
from janelkit.inspect import mount
from janelkit.qt_backend.video_surface import JkVideoSurface


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


def surfaces(app) -> list[JkVideoSurface]:
    return app.window.findChildren(JkVideoSurface)


def shown(app, i: int = 0) -> QImage:
    return surfaces(app)[i].image()


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
<column>
  <video source={frames} width={400} height={400} label="Cámara">
    <flex class="caja" label="caja" />
  </video>
  <text>{frames.size}</text>
</column>
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


def test_the_frame_is_drawn_only_where_the_image_is(app_from):
    app = app_from('<script>\nfrom janelkit import Frames\nframes = Frames()\n</script>\n'
                   '<video source={frames} width={400} height={400} />')
    frames = app.namespace["frames"]
    behind = app.screenshot().pixelColor(200, 40).name()  # el fondo de la ventana
    frames.push(image(640, 360, b"\xff\x00\x00"))  # rojo, 16:9: bandas arriba y abajo
    app.wait(0.05)
    shot = app.screenshot()
    assert shot.pixelColor(200, 200).name() == "#ff0000"
    assert shot.pixelColor(200, 40).name() == behind  # banda
    frames.push(image(640, 360, b"\x00\x00\xff"))
    app.wait(0.05)
    assert app.screenshot().pixelColor(200, 200).name() == "#0000ff"  # el nuevo fotograma sustituye al anterior
    frames.clear()
    app.wait(0.05)
    assert app.screenshot().pixelColor(200, 200).name() != "#0000ff"


def test_transparent_frames_show_what_is_behind(app_from):
    app = app_from('<script>\nfrom janelkit import Frames\nframes = Frames(color="rgba")\n</script>\n'
                   '<video source={frames} width={400} height={400} />')
    frames = app.namespace["frames"]
    behind = app.screenshot().pixelColor(200, 200).name()  # el fondo de la ventana
    frames.push(image(4, 4, b"\xff\x00\x00\x00"))  # rojo del todo transparente
    app.wait(0.05)
    assert app.screenshot().pixelColor(200, 200).name() == behind != "#ff0000"
    frames.push(image(4, 4, b"\xff\x00\x00\xff"))  # rojo opaco
    app.wait(0.05)
    assert app.screenshot().pixelColor(200, 200).name() == "#ff0000"


def test_fit_cover_crops_and_the_overlay_follows(app_from):
    app = app_from(APP.replace("<video source={frames}", '<video source={frames} fit="cover"'))
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
    frames._hub._idle.setInterval(300)  # más que una pausa del ejecutor de la CI
    parar = threading.Event()

    def emitir():
        while not parar.is_set():
            frames.push(image(16, 16))
            parar.wait(0.01)

    t = threading.Thread(target=emitir)
    t.start()
    try:
        app.wait(until=lambda: frames.fps > 10, timeout=5)
    finally:
        parar.set()
        t.join()
    app.wait(until=lambda: frames.fps == 0, timeout=2)
    frames.clear()
    app.wait(0.02)
    assert frames.size is None and frames.latest() is None
    assert shown(app).isNull()


STALL = """<script>
from janelkit import Frames
frames = Frames(stall_after=0.3)
</script>
<column>
  <video source={frames} width={400} height={400} />
  {#if frames.stalled}<text>Sin señal</text>{/if}
</column>
"""


def test_stalled_after_stall_after_without_frames_and_back_with_the_next(app_from):
    app = app_from(STALL)
    frames = app.namespace["frames"]
    app.wait(0.4)
    assert frames.stalled is False  # antes del primer fotograma no hay fuente que se haya parado
    frames.push(image(8, 8))
    app.wait(0.02)
    assert frames.stalled is False and "Sin señal" not in app.texts()
    app.wait(until=lambda: frames.stalled, timeout=3)
    assert frames.fps == 0 and "Sin señal" in app.texts()  # fps baja a la vez, con el mismo umbral
    assert repr(frames) == "Frames(color='rgb', size=(8, 8), stalled=True)"
    frames.push(image(8, 8))
    app.wait(0.02)
    assert frames.stalled is False and "Sin señal" not in app.texts()


def test_clear_resets_stalled_and_fps_and_stops_watching(app_from):
    app = app_from(STALL)
    frames = app.namespace["frames"]
    frames.push(image(8, 8))
    app.wait(until=lambda: frames.stalled, timeout=3)
    frames.clear()
    assert (frames.stalled, frames.fps, frames.size) == (False, 0, None)
    app.wait(0.5)  # más que stall_after: sin fotograma, no vuelve a «sin señal»
    assert frames.stalled is False


def test_stall_after_must_be_positive():
    assert Frames(stall_after=2).stalled is False
    for wrong in (0, -1, True, "1"):
        with pytest.raises(ValueError, match="stall_after"):
            Frames(stall_after=wrong)


CLICKS = """<script>
from janelkit import Frames, state
frames = Frames()
eventos = []
parar = state(True)

def anotar(e):
    eventos.append((e.type, e.image_x, e.image_y))

def caja(e):
    eventos.append(("caja", e.image_x, e.image_y))
    if parar.value:
        e.stop()
</script>
<column>
  <video source={frames} width={400} height={400} label="Cámara" on:click={anotar} on:dblclick={anotar}
         on:contextmenu={anotar} on:pointerdown={anotar} on:pointerup={anotar} on:pointermove={anotar}
         on:pointerenter={anotar}>
    <flex class="caja" label="caja" on:click={caja} />
  </video>
</column>
<style>
.caja { width: 100px; height: 100px }
</style>
"""


def last(app, kind: str) -> tuple:
    return [e for e in app.namespace["eventos"] if e[0] == kind][-1]


def test_click_on_a_video_gives_the_pixel_of_the_image_and_none_in_the_bands(app_from):
    app = app_from(CLICKS)
    video = app.find(label="Cámara")
    video.click(x=100, y=200)
    assert last(app, "click") == ("click", None, None)  # sin fotograma
    app.namespace["frames"].push(image(640, 360))  # 16:9 en 400 × 400: la imagen va de y=87,5 a 312,5
    app.wait(0.05)
    video.click(x=100, y=200)
    assert last(app, "click") == ("click", pytest.approx(160), pytest.approx(180))
    assert last(app, "pointerdown") == ("pointerdown", pytest.approx(160), pytest.approx(180))
    video.click(x=100, y=40)  # en la banda de arriba: el evento llega, sin píxel
    assert last(app, "click") == ("click", None, None)


def test_image_pixels_with_fit_cover_and_fill(app_from):
    app = app_from(CLICKS.replace("<video source={frames}", '<video source={frames} fit="cover"'))
    app.namespace["frames"].push(image(800, 400))  # recortada: se ve x de 200 a 600 de la imagen
    app.wait(0.05)
    app.find(label="Cámara").click(x=100, y=200)
    assert last(app, "click") == ("click", pytest.approx(300), pytest.approx(200))

    app = app_from(CLICKS.replace("<video source={frames}", '<video source={frames} fit="fill"'))
    app.namespace["frames"].push(image(800, 200))  # estirada: cada eje con su escala
    app.wait(0.05)
    app.find(label="Cámara").click(x=100, y=200)
    assert last(app, "click") == ("click", pytest.approx(200), pytest.approx(100))


def test_pointer_move_double_and_right_click_on_a_video(app_from):
    app = app_from(CLICKS)
    app.namespace["frames"].push(image(800, 800))  # escala 2
    app.wait(0.05)
    video = app.find(label="Cámara")
    video.hover(x=150, y=160)  # entra por (151, 161) y se mueve a (150, 160)
    assert last(app, "pointerenter") == ("pointerenter", pytest.approx(302), pytest.approx(322))
    assert last(app, "pointermove") == ("pointermove", pytest.approx(300), pytest.approx(320))
    video.double_click(x=110, y=220)
    assert last(app, "dblclick") == ("dblclick", pytest.approx(220), pytest.approx(440))
    video.right_click(x=130, y=240)
    assert last(app, "contextmenu") == ("contextmenu", pytest.approx(260), pytest.approx(480))


def test_a_child_gets_the_click_first_and_can_stop_it(app_from):
    app = app_from(CLICKS)
    app.namespace["frames"].push(image(400, 400))
    app.wait(0.05)
    video = app.find(label="Cámara")
    eventos = app.namespace["eventos"]
    video.click(x=50, y=50)  # sobre la caja, que para el clic
    clicks = [e for e in eventos if e[0] in ("caja", "click")]
    assert clicks == [("caja", None, None)]  # los demás elementos no tienen píxel de la imagen
    app.namespace["parar"].value = False
    eventos.clear()
    video.click(x=50, y=50)
    assert [e for e in eventos if e[0] in ("caja", "click")] == [("caja", None, None), ("click", pytest.approx(50), pytest.approx(50))]


def test_the_click_of_an_absolute_child_stays_in_it_like_in_flex(app_from):
    # Una caja absolute no deja pasar el puntero (estilos.md): su on:click no sube, como en <flex>;
    # on:pointerdown sí llega al <video>, con el píxel de la imagen.
    app = app_from(CLICKS.replace("width: 100px; height: 100px", "position: absolute; left: 50%; top: 0; width: 25%; height: 100%"))
    app.namespace["frames"].push(image(400, 400))
    app.wait(0.05)
    app.namespace["parar"].value = False
    app.find(label="Cámara").click(x=250, y=200)
    eventos = app.namespace["eventos"]
    assert [e for e in eventos if e[0] in ("caja", "click")] == [("caja", None, None)]
    assert last(app, "pointerdown") == ("pointerdown", pytest.approx(250), pytest.approx(200))


def test_a_click_without_position_is_like_the_keyboard(app_from):
    app = app_from(CLICKS)
    app.namespace["frames"].push(image(400, 400))
    app.wait(0.05)
    app.find(label="Cámara").click()
    assert last(app, "click") == ("click", None, None)


def test_video_only_has_pointer_events():
    from janelkit.compiler import compile_source
    from janelkit.diagnostics import JanelError

    head = "<script>\nfrom janelkit import Frames\nframes = Frames()\ndef f(e): pass\n</script>\n"
    compile_source(head + "<video source={frames} on:pointerenter={f} on:pointerleave={f} />", "App.janel")
    with pytest.raises(JanelError, match="evento desconocido 'on:keydown' en <video>"):
        compile_source(head + "<video source={frames} on:keydown={f} />", "App.janel")


def test_a_video_that_goes_away_lets_go_of_its_surface(app_from):
    app = app_from("""<script>
from janelkit import Frames, state
frames = Frames()
ver = state(True)
</script>
<column>
  {#if ver}<video source={frames} />{/if}
</column>""")
    frames = app.namespace["frames"]
    assert len(frames._hub._sinks) == 1
    app.namespace["ver"].value = False
    app.wait(0.05)
    assert frames._hub._sinks == []
    frames.push(image(4, 4, b"\x00\x00\x00"))  # sin vistas: no falla
    app.namespace["ver"].value = True
    app.wait(0.05)
    assert len(frames._hub._sinks) == 1
    assert not frames._hub._sinks[0].image().isNull()  # muestra el último al engancharse


def test_the_documented_example_runs(app_from):
    app = app_from("""<script>
from janelkit import Frames, state
frames = Frames(color="bgr")
caras = state([])

def pct(valor, eje):              # de píxeles de la imagen a % de la capa
    tamaño = frames.size or (1, 1)
    return f"{100 * valor / tamaño[eje]}%"
</script>
<column>
  <video source={frames} width={400} height={400} label="Cámara">
    {#each caras as c}
      <flex class="cara" label="cara" style={{"left": pct(c[0], 0), "top": pct(c[1], 1), "width": pct(c[2], 0), "height": pct(c[3], 1)}} />
    {/each}
  </video>
  <text>{frames.fps:.0f} fps</text>
</column>
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
