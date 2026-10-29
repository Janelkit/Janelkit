"""Un vídeo generado (sin cámara) y un «modelo» que encuentra sus objetos.

La escena: un degradado con tres cuadrados de colores puros que se mueven. El modelo
los busca por su color, como haría un detector de verdad, y tarda lo que se le pida.
"""
from __future__ import annotations

import math
import time

import numpy as np

COLORES = {"rojo": (255, 0, 0), "verde": (0, 255, 0), "azul": (0, 0, 255)}


class Escena:
    def __init__(self, ancho: int = 1280, alto: int = 720):
        self.ancho, self.alto = ancho, alto
        x = np.linspace(40, 90, ancho, dtype=np.float32)
        y = np.linspace(30, 70, alto, dtype=np.float32)[:, None]
        gris = (x + y).astype(np.uint8)
        self._fondo = np.dstack([gris, gris, gris])
        self._lado = alto // 6

    def fotograma(self, t: float) -> np.ndarray:
        img = self._fondo.copy()
        lado = self._lado
        for i, color in enumerate(COLORES.values()):
            cx = (0.5 + 0.38 * math.sin(t * (0.7 + 0.3 * i) + i * 2.1)) * (self.ancho - lado)
            cy = (0.5 + 0.38 * math.cos(t * (0.5 + 0.2 * i) + i)) * (self.alto - lado)
            x, y = int(cx), int(cy)
            img[y : y + lado, x : x + lado] = color
        return img


def detectar(img: np.ndarray, retardo_ms: float) -> list[tuple[int, int, int, int, str]]:
    """Cajas `(x, y, ancho, alto, etiqueta)` de cada color puro. En otro hilo: no toca el estado."""
    inicio = time.perf_counter()
    pequeña = img[::4, ::4]  # basta con un cuarto de resolución para encontrarlos
    cajas = []
    for nombre, color in COLORES.items():
        ys, xs = np.nonzero(np.all(pequeña == color, axis=2))
        if len(xs):
            x0, y0 = int(xs.min()) * 4, int(ys.min()) * 4
            cajas.append((x0, y0, int(xs.max()) * 4 + 4 - x0, int(ys.max()) * 4 + 4 - y0, nombre))
    resto = retardo_ms / 1000 - (time.perf_counter() - inicio)
    if resto > 0:
        time.sleep(resto)  # un modelo lento de verdad
    return cajas
