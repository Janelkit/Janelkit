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
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGSimpleTextureNode, QSGTexture

_OPAQUE = QQuickWindow.CreateTextureOption.TextureIsOpaque


class JkVideoSurface(QQuickItem):
    sourceSizeChanged = Signal()

    def __init__(self, parent: QQuickItem | None = None):
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self._image = QImage()
        self._opaque = True
        self._dirty = False

    @Slot(QImage)
    @Slot(QImage, bool)
    def setImage(self, image: QImage, opaque: bool = True) -> None:
        """Muestra `image` (un `QImage` nulo deja la superficie vacía). En el hilo de la interfaz.

        `opaque`: la imagen no tiene transparencias (se dibuja sin mezclar con lo de detrás)."""
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
        if node is None:
            if image.isNull():
                return None
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
            node.setTexture(self.window().createTextureFromImage(image, options))
        node.setRect(QRectF() if self._image.isNull() else self.boundingRect())
        return node
