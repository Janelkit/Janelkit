"""Diálogos nativos del sistema: abrir y guardar archivos, elegir carpeta y mensajes.

Son funciones asíncronas: se usan con `await` desde un manejador `async def`
(la ventana sigue viva mientras el diálogo está abierto):

    from janelkit_desktop import dialogs

    async def abrir():
        ruta = await dialogs.open_file("Abrir nota", filters=["Texto (*.txt *.md)"])
        if ruta is not None:                 # None si el usuario cancela
            texto.value = ruta.read_text()

    async def borrar():
        if await dialogs.confirm("¿Borrar la nota?"):
            ...

Usan QtQuick.Dialogs: diálogos nativos cuando la plataforma los ofrece y,
si no, una versión QML equivalente. Necesitan una aplicación en marcha (`run`).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Sequence

from janelkit.ext import app as running_app, inspector

_open: list[Any] = []  # diálogos abiertos (para pruebas: ver `pending`)


def _app() -> Any:
    app = running_app()
    if app is None:
        raise RuntimeError("los diálogos necesitan una aplicación en marcha (janelkit.run)")
    return app


def _create(qml_type: str, props: dict[str, Any]) -> Any:
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent

    app = _app()
    component = QQmlComponent(app.engine)
    component.setData(f"import QtQuick\nimport QtQuick.Dialogs\n{qml_type} {{}}\n".encode(), QUrl())
    dialog = component.create()
    if dialog is None:
        raise RuntimeError("; ".join(e.toString() for e in component.errors()) or f"no se pudo crear {qml_type}")
    window = app.main_window()
    if window is not None:
        dialog.setProperty("parentWindow", window)
    for name, value in props.items():
        if value is not None:
            dialog.setProperty(name, value)
    # Propiedad explícita de Qt: con el motor como padre, ni Python ni el recolector de
    # QML lo borran antes de que el usuario responda (se borra en _run al terminar).
    dialog.setParent(app.engine)
    component.setParent(dialog)
    # El tipo, para `kind` (desde Python el diálogo puede llegar como un QObject genérico).
    dialog.setProperty("jkDialogType", qml_type)
    return dialog


async def _run(dialog: Any, on_accept, on_close=None) -> Any:
    """Abre el diálogo y espera. `on_close` (si se da) decide el resultado al cerrarse de cualquier forma."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()

    def done(result: Any) -> None:
        if not future.done():
            future.set_result(result)

    # Conexiones y llamadas por nombre: según la versión de PySide6, el diálogo llega
    # como su tipo QML o como un QObject genérico sin esos atributos en Python.
    from PySide6.QtCore import SIGNAL, QMetaObject, QObject

    if on_close is not None:
        QObject.connect(dialog, SIGNAL("accepted()"), lambda: done(on_close(dialog)))
        QObject.connect(dialog, SIGNAL("rejected()"), lambda: done(on_close(dialog)))
    else:
        QObject.connect(dialog, SIGNAL("accepted()"), lambda: done(on_accept(dialog)))
        QObject.connect(dialog, SIGNAL("rejected()"), lambda: done(None))
    _open.append(dialog)
    try:
        QMetaObject.invokeMethod(dialog, "open")
        return await future
    finally:
        _open.remove(dialog)
        if not future.done():  # cancelado (p. ej. al desmontar el componente)
            QMetaObject.invokeMethod(dialog, "close")
        dialog.deleteLater()


def _url(path: str | Path | None) -> Any:
    if path is None:
        return None
    from PySide6.QtCore import QUrl

    return QUrl.fromLocalFile(str(Path(path).resolve()))


def _path(url: Any) -> Path | None:
    local = url.toLocalFile() if hasattr(url, "toLocalFile") else str(url)
    return Path(local) if local else None


def _filters(filters: Sequence[str] | None) -> list[str] | None:
    return list(filters) if filters else None


async def open_file(
    title: str = "Abrir", filters: Sequence[str] | None = None, folder: str | Path | None = None
) -> Path | None:
    """Pide un archivo existente. `filters`: p. ej. `["Imágenes (*.png *.jpg)", "Todos (*)"]`. None si se cancela."""
    dialog = _create("FileDialog", {"title": title, "nameFilters": _filters(filters), "currentFolder": _url(folder)})
    dialog.setProperty("fileMode", 0)  # FileDialog.OpenFile
    return await _run(dialog, lambda d: _path(d.property("selectedFile")))


async def open_files(
    title: str = "Abrir", filters: Sequence[str] | None = None, folder: str | Path | None = None
) -> list[Path]:
    """Pide uno o varios archivos existentes. Lista vacía si se cancela."""
    dialog = _create("FileDialog", {"title": title, "nameFilters": _filters(filters), "currentFolder": _url(folder)})
    dialog.setProperty("fileMode", 1)  # FileDialog.OpenFiles
    result = await _run(dialog, lambda d: [p for p in map(_path, d.property("selectedFiles") or []) if p])
    return result or []


async def save_file(
    title: str = "Guardar",
    filters: Sequence[str] | None = None,
    folder: str | Path | None = None,
    name: str | None = None,
) -> Path | None:
    """Pide dónde guardar. `name`: nombre propuesto. None si se cancela."""
    props = {"title": title, "nameFilters": _filters(filters), "currentFolder": _url(folder)}
    if name:
        base = Path(folder) if folder else Path.cwd()
        props["selectedFile"] = _url(base / name)
    dialog = _create("FileDialog", props)
    dialog.setProperty("fileMode", 2)  # FileDialog.SaveFile
    return await _run(dialog, lambda d: _path(d.property("selectedFile")))


async def choose_folder(title: str = "Elegir carpeta", folder: str | Path | None = None) -> Path | None:
    """Pide una carpeta. None si se cancela."""
    dialog = _create("FolderDialog", {"title": title, "currentFolder": _url(folder)})
    return await _run(dialog, lambda d: _path(d.property("selectedFolder")))


_OK, _CANCEL = 0x00000400, 0x00400000  # MessageDialog.Ok, MessageDialog.Cancel
# En MessageDialog, `result` es el botón pulsado (no Accepted/Rejected).


async def message(text: str, title: str = "", details: str | None = None) -> None:
    """Muestra un mensaje con un botón Aceptar y espera a que se cierre."""
    dialog = _create("MessageDialog", {"title": title, "text": text, "informativeText": details, "buttons": _OK})
    await _run(dialog, None, on_close=lambda d: None)


async def confirm(text: str, title: str = "", details: str | None = None) -> bool:
    """Pregunta Aceptar / Cancelar. True si se acepta."""
    dialog = _create(
        "MessageDialog", {"title": title, "text": text, "informativeText": details, "buttons": _OK | _CANCEL}
    )
    return bool(await _run(dialog, None, on_close=lambda d: d.property("result") == _OK))


def pending() -> list[Any]:
    """Diálogos abiertos ahora mismo (objetos Qt). Útil en pruebas para aceptarlos o cancelarlos."""
    return list(_open)


def kind(dialog: Any) -> str:
    """El tipo QML de un diálogo abierto: "MessageDialog", "FileDialog" o "FolderDialog"."""
    return str(dialog.property("jkDialogType") or "")


# -- en pruebas: `app.dialogs()` y `app.answer_dialog(...)` de janelkit.inspect ----------
@inspector("dialogs")
def _inspect_pending(app: Any) -> list[Any]:
    """Diálogos abiertos, del más antiguo al más reciente."""
    return pending()


@inspector("answer_dialog")
def _inspect_answer(app: Any, result: Any = True) -> None:
    """Responde al diálogo abierto: una ruta (archivos), True/False (aceptar/cancelar)."""
    from PySide6.QtCore import Q_ARG, QMetaObject, QUrl

    from janelkit.inspect import InspectError

    def invoke(method: str, *args: Any) -> None:
        if not QMetaObject.invokeMethod(dialog, method, *args):
            raise InspectError(f"no se pudo invocar {method} en {dialog.metaObject().className()}")

    if not _open:
        raise InspectError("no hay ningún diálogo abierto")
    dialog = _open[-1]
    if result is False or result is None:
        invoke("reject")
    elif isinstance(result, (str, Path)):
        prop = "selectedFolder" if kind(dialog) == "FolderDialog" else "selectedFile"
        dialog.setProperty(prop, QUrl.fromLocalFile(str(Path(result).resolve())))
        invoke("done", Q_ARG(int, 1))
    elif kind(dialog) == "MessageDialog":
        invoke("done", Q_ARG(int, _OK))  # Aceptar
    else:
        invoke("done", Q_ARG(int, 1))
    app.wait(0.01)
