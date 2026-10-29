"""Fotogramas a tiempo real: `Frames` y el elemento `<Video>`.

    frames = Frames(color="bgr")          # el orden de OpenCV; por defecto "rgb"

    def capturar():                       # en un hilo propio
        while abierta:
            ok, img = camara.read()
            frames.push(img)

    async def procesar():
        async for img in frames:          # el más reciente; se saltan los que no dio tiempo
            detecciones.value = await background(modelo, img)

    <Video source={frames} />

Los fotogramas no pasan por la reactividad: `push()` (desde cualquier hilo)
convierte la imagen a un `QVideoFrame` en el hilo que llama y avisa al de la
interfaz, que entrega a cada `<Video>` el más reciente. Si llegan más deprisa de
lo que se entregan, se saltan: nunca se encolan. Lo reactivo es `size` y `fps`.

Sin numpy como dependencia: la imagen se lee con `memoryview` (alto × ancho de
bytes en gris, × 3 o × 4 con color).
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoFrame

from .reactivity import State, batch
from .reactivity.effects import check_thread

_FORMATS = {
    "rgb": QImage.Format.Format_RGB888,
    "bgr": QImage.Format.Format_BGR888,
    "rgba": QImage.Format.Format_RGBA8888,
    "bgra": QImage.Format.Format_ARGB32,  # B, G, R, A en memoria (little-endian)
}
_CHANNELS = {"rgb": 3, "bgr": 3, "rgba": 4, "bgra": 4}


def _to_frame(image: Any, color: str) -> QVideoFrame:
    """Copia `image` a un `QVideoFrame` en un formato que Qt muestra sin convertir."""
    if isinstance(image, QImage):
        qimage = image
    else:
        try:
            view = memoryview(image)
        except TypeError:
            raise TypeError(f"Frames.push: se esperaba un array (numpy), un objeto con búfer o un QImage, no {type(image).__name__}") from None
        if view.itemsize != 1 or view.ndim not in (2, 3):
            raise TypeError(f"Frames.push: se esperaban bytes de forma alto × ancho (× canales), no {view.format!r} con forma {view.shape}")
        height, width = view.shape[0], view.shape[1]
        channels = 1 if view.ndim == 2 else view.shape[2]
        if channels == 1:
            fmt = QImage.Format.Format_Grayscale8
        elif channels == _CHANNELS[color]:
            fmt = _FORMATS[color]
        else:
            raise TypeError(f"Frames.push: la imagen tiene {channels} canales y el color es {color!r} ({_CHANNELS[color]})")
        if not view.c_contiguous:  # p. ej. un recorte de un array de numpy
            view = memoryview(view.tobytes()).cast("B", view.shape)
        qimage = QImage(view, width, height, width * channels, fmt)
    has_alpha = qimage.hasAlphaChannel()
    # convertToFormat copia (también cuando el formato ya es el bueno): el búfer se puede reutilizar.
    target = QImage.Format.Format_RGBA8888 if has_alpha else QImage.Format.Format_RGBX8888
    qimage = qimage.convertToFormat(target) if qimage.format() != target else qimage.copy()
    return QVideoFrame(qimage)


class _Hub(QObject):
    """La parte Qt de un `Frames`: vive en el hilo de la interfaz y entrega a los `<Video>`."""

    _ready = Signal()

    def __init__(self, frames: "Frames"):
        super().__init__()
        self._frames = frames
        self._sinks: list[QObject] = []
        self._ready.connect(self._deliver)  # desde otro hilo llega en cola; desde este, al momento
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(1500)
        self._idle.timeout.connect(frames._stalled)

    @Slot(QObject)
    def attach(self, sink: QObject) -> None:
        if sink is not None and sink not in self._sinks:
            self._sinks.append(sink)
            frame = self._frames._shown
            if frame is not None:
                sink.setVideoFrame(frame)

    @Slot(QObject)
    def detach(self, sink: QObject) -> None:
        if sink in self._sinks:
            self._sinks.remove(sink)

    @Slot()
    def _deliver(self) -> None:
        self._frames._deliver()

    def show(self, frame: QVideoFrame) -> None:
        for sink in list(self._sinks):
            try:
                sink.setVideoFrame(frame)
            except RuntimeError:  # la vista ya no existe
                self._sinks.remove(sink)


class Frames:
    """Canal del último fotograma, para mostrarlo con `<Video source=…>` y procesarlo.

    - `push(imagen)` desde cualquier hilo. Copia la imagen.
    - `async for imagen in frames` o `await frames.next()`: el más reciente que llegue
      (el objeto que se pasó a `push`).
    - `size` (`(ancho, alto)` o `None`) y `fps` son reactivos.
    """

    def __init__(self, color: str = "rgb"):
        if color not in _FORMATS:
            raise ValueError(f"Frames: color debe ser uno de {', '.join(_FORMATS)}, no {color!r}")
        check_thread()
        self.color = color
        self._lock = threading.Lock()
        self._pending: tuple[Any, QVideoFrame] | None = None
        self._latest: Any = None
        self._shown: QVideoFrame | None = None
        self._shown_image: Any = None  # el objeto que se pasó a push() con el fotograma mostrado
        self._seq = 0
        self._waiters: list[asyncio.Future] = []
        self._size: State[tuple[int, int] | None] = State(None)
        self._fps: State[float] = State(0.0)
        self._count = 0
        self._since = time.perf_counter()
        self._hub = _Hub(self)

    # -- desde cualquier hilo -------------------------------------------------------
    def push(self, image: Any) -> None:
        """Muestra `image` en los `<Video>` y la entrega a quien espera. Desde cualquier hilo."""
        frame = _to_frame(image, self.color)
        with self._lock:
            idle = self._pending is None
            self._pending = (image, frame)
            self._latest = image
        if idle:  # si ya había uno pendiente, el aviso está en camino: lo sustituye
            self._hub._ready.emit()

    def latest(self) -> Any:
        """El último fotograma que se pasó a `push` (o `None`)."""
        with self._lock:
            return self._latest

    # -- en el hilo de la interfaz ------------------------------------------------------
    def _deliver(self) -> None:
        with self._lock:
            pending, self._pending = self._pending, None
        if pending is None:
            return
        image, frame = pending
        self._seq += 1
        self._shown, self._shown_image = frame, image
        self._hub.show(frame)
        self._count += 1
        now = time.perf_counter()
        with batch():
            size = frame.size()
            self._size.value = (size.width(), size.height())
            if now - self._since >= 1.0:
                self._fps.value = round(self._count / (now - self._since), 1)
                self._count, self._since = 0, now
        self._hub._idle.start()
        waiters, self._waiters = self._waiters, []
        for future in waiters:
            if not future.done():
                future.set_result(image)

    def _stalled(self) -> None:
        self._fps.value = 0.0
        self._count, self._since = 0, time.perf_counter()

    def clear(self) -> None:
        """Deja de mostrar el último fotograma."""
        check_thread()
        with self._lock:
            self._pending = None
            self._latest = None
        self._shown = self._shown_image = None
        self._hub.show(QVideoFrame())
        self._size.value = None

    def next(self) -> "asyncio.Future[Any]":
        """`await frames.next()`: el próximo fotograma que llegue."""
        future = asyncio.get_event_loop().create_future()
        self._waiters.append(future)
        return future

    def __aiter__(self) -> "_Iterator":
        return _Iterator(self)

    @property
    def size(self) -> tuple[int, int] | None:
        """`(ancho, alto)` del último fotograma, o `None`. Reactivo."""
        return self._size.value

    @property
    def fps(self) -> float:
        """Fotogramas por segundo recibidos (se actualiza cada segundo; 0 si dejan de llegar). Reactivo."""
        return self._fps.value

    def __jk_qml__(self) -> QObject:
        return self._hub

    def __repr__(self) -> str:
        return f"Frames(color={self.color!r}, size={self._size.peek()})"


class _Iterator:
    """`async for`: da el fotograma más reciente que este iterador no haya dado aún."""

    def __init__(self, frames: Frames):
        self._frames = frames
        self._seen = frames._seq

    def __aiter__(self) -> "_Iterator":
        return self

    async def __anext__(self) -> Any:
        frames = self._frames
        if frames._seq > self._seen and frames._shown is not None:
            self._seen = frames._seq
            return frames._shown_image
        image = await frames.next()
        self._seen = frames._seq
        return image
