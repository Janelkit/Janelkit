"""Enganche de escrituras: por dónde se observa qué estado cambia.

`State` y las colecciones reactivas avisan a `listener`, si hay uno, justo antes de
cada escritura: `listener.state(estado, valor_de_antes)` al asignar un `State`, y
`listener.collection(coleccion)` antes de modificar en el sitio una lista, un
diccionario o un conjunto reactivo. Sin nadie escuchando cuesta una comprobación de
`None`.
"""
from __future__ import annotations

from typing import Any

listener: Any = None
