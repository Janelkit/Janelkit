"""Portapapeles del sistema (texto).

    from janelkit import clipboard

    clipboard.copy(enlace)                  # copia un texto
    texto = clipboard.paste()               # el texto que hay ("" si no hay)

`paste()` es reactivo: un binding o un `computed` que lo lee se actualiza cuando el
portapapeles cambia, también desde otra aplicación. Por ejemplo, un botón «Pegar» que
solo se activa si hay algo que pegar: `<Button enabled={bool(clipboard.paste())} …>`.

Necesita la aplicación en marcha (el script de un componente, o después de `run()`).
Los campos de texto ya copian y pegan solos con Ctrl+C y Ctrl+V; esto es para lo demás
(copiar un enlace, una celda, el contenido de una tarjeta).
"""
from __future__ import annotations

from typing import Any

from janelkit import State

_text: State[str] = State("")
_board: Any = None  # QClipboard vigilado (se avisa a _text cuando cambia)


def copy(text: str) -> None:
    """Pone `text` en el portapapeles."""
    board = _clipboard()
    board.setText(str(text))
    _text.value = board.text()


def paste() -> str:
    """El texto del portapapeles ("" si no hay texto). Reactivo."""
    _clipboard()
    return _text.value


def clear() -> None:
    """Vacía el portapapeles."""
    _clipboard().clear()
    _text.value = ""


def _clipboard() -> Any:
    global _board
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("el portapapeles necesita la aplicación en marcha: úsalo en el script de un componente o después de run()")
    board = QGuiApplication.clipboard()
    if board is not _board:
        _board = board
        board.dataChanged.connect(_changed)
        _text.value = board.text()
    return board


def _changed() -> None:
    if _board is not None:
        _text.value = _board.text()
