"""Superficie de `<video>`: muestra el último fotograma de un `Frames` como una textura.

Sustituye al `VideoOutput` de QtMultimedia, que está en PySide6-Addons: así `<video>` solo
necesita Qt Quick (PySide6-Essentials). El fotograma llega ya convertido a RGBA
premultiplicado (`Frames.push` lo hace en el hilo que llama); aquí solo se crea su textura
en `updatePaintNode`, una vez por fotograma nuevo, y la GPU lo escala al tamaño del
elemento. El nodo es dueño de la textura: la anterior se borra al poner la nueva.

JkVideo.qml coloca la superficie en el rectángulo que ocupa la imagen según `fit`
(`contain`, `cover`, `fill`), así que la textura siempre llena la superficie.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QRectF, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGSimpleTextureNode, QSGTexture

_OPAQUE = QQuickWindow.CreateTextureOption.TextureIsOpaque


def _window_of(item: QQuickItem) -> QQuickWindow | None:
    """La ventana de `item`, buscada entre las de la aplicación.

    No con `item.window()`: en un item cuya clase está definida en Python, PySide ata el
    envoltorio de la ventana que devuelve al del item, y al destruirse el item (un `{#if}` que
    pasa a falso) invalida también el de la ventana, aunque la ventana siga viva. Desde ahí,
    `app().main_window()` da `None` y todo lo que usa la ventana desde Python falla con
    «Internal C++ object (QQuickWindow) already deleted».
    """
    for window in QGuiApplication.topLevelWindows():
        if isinstance(window, QQuickWindow):
            content = window.contentItem()
            if content is not None and (content is item or content.isAncestorOf(item)):
                return window
    return None


class JkVideoSurface(QQuickItem):
    sourceSizeChanged = Signal()

    def __init__(self, parent: QQuickItem | None = None):
        super().__init__(parent)
        # Sin ItemHasContents hasta el primer fotograma (ver setImage).
        self._image = QImage()
        self._opaque = True
        self._dirty = False

    @Slot(QImage)
    @Slot(QImage, bool)
    def setImage(self, image: QImage, opaque: bool = True) -> None:
        """Muestra `image` (un `QImage` nulo deja la superficie vacía). En el hilo de la interfaz.

        `opaque`: la imagen no tiene transparencias (se dibuja sin mezclar con lo de detrás)."""
        if not image.isNull():
            # Solo desde aquí pide Qt Quick dibujarla. Con el dibujo en otro hilo (Direct3D,
            # OpenGL), una ventana que se hace visible espera a que ese hilo pinte, y si lo hace
            # dentro de una llamada desde Python (montarla con component.create) no suelta el
            # GIL: updatePaintNode, que es Python, se quedaba esperándolo y la ventana colgada.
            self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        resized = image.size() != self._image.size()
        self._image = image
        self._opaque = opaque
        self._dirty = True
        if resized:
            self.sourceSizeChanged.emit()
        self.update()

    def image(self) -> QImage:
        """El fotograma que se muestra (nulo si ninguno)."""
        return self._image

    def _source_width(self) -> int:
        return self._image.width()

    def _source_height(self) -> int:
        return self._image.height()

    sourceWidth = Property(int, _source_width, notify=sourceSizeChanged)
    sourceHeight = Property(int, _source_height, notify=sourceSizeChanged)

    def updatePaintNode(self, node: QSGSimpleTextureNode | None, _data: object) -> QSGSimpleTextureNode | None:
        # Hilo de dibujo, con el de la interfaz parado: se puede leer self._image.
        image = self._image
        if node is None and image.isNull():
            return None
        if node is None or self._dirty:
            window = _window_of(self)  # no self.window(): ver _window_of
            if window is None:
                return node
        if node is None:
            node = QSGSimpleTextureNode()
            node.setOwnsTexture(True)  # borra la textura anterior al cambiarla y al destruirse
            node.setFiltering(QSGTexture.Filtering.Linear)
            self._dirty = True
        if self._dirty:
            self._dirty = False
            opaque = self._opaque
            if image.isNull():  # sin fotograma: una textura mínima y nada que dibujar
                image = QImage(1, 1, QImage.Format.Format_RGBA8888_Premultiplied)
                image.fill(0)
                opaque = False
            options = _OPAQUE if opaque else QQuickWindow.CreateTextureOption(0)
            node.setTexture(window.createTextureFromImage(image, options))
        node.setRect(QRectF() if self._image.isNull() else self.boundingRect())
        return node
