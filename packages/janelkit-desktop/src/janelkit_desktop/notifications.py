"""Notificaciones del sistema (el globo o aviso del área de notificaciones).

    from janelkit_desktop import notify

    def al_recibir(mensaje):
        if not ventana_activa.value:
            notify(mensaje["autor"], mensaje["texto"], on_click=abrir_conversacion)

La primera notificación muestra el icono de la aplicación en la bandeja del
sistema; pulsar la notificación trae la ventana principal al frente (y llama a
`on_click`, si se pasa). Donde la plataforma no tiene bandeja, `notify` no hace
nada visible, pero la notificación queda registrada (`sent()`, para pruebas).

Usa la bandeja nativa de Qt (Qt.labs.platform): no necesita QtWidgets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from janelkit.ext import app as running_app, inspector

_sent: list[dict[str, str]] = []  # notificaciones enviadas en este proceso (ver `sent`)
_tray: Any = None
_on_click: Callable[[], Any] | None = None

_ICON = Path(__file__).parent / "icon.png"


def notify(title: str, message: str = "", *, on_click: Callable[[], Any] | None = None) -> None:
    """Muestra una notificación del sistema con `title` y `message`."""
    global _on_click
    _sent.append({"title": str(title), "message": str(message)})
    _on_click = on_click
    tray = _tray_icon()
    if tray is not None and tray.property("available") and tray.property("supportsMessages"):
        tray.setProperty("visible", True)
        from PySide6.QtCore import Q_ARG, QMetaObject

        QMetaObject.invokeMethod(tray, "showMessage", Q_ARG("QString", str(title)), Q_ARG("QString", str(message)))


def sent() -> list[dict[str, str]]:
    """Notificaciones enviadas hasta ahora, de la más antigua a la más reciente (para pruebas)."""
    return list(_sent)


def _tray_icon() -> Any:
    global _tray
    from shiboken6 import Shiboken

    app = running_app()
    if app is None:
        return None
    if _tray is not None and Shiboken.isValid(_tray) and _tray.parent() is app.engine:
        return _tray
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent

    component = QQmlComponent(app.engine)
    component.setData(
        (
            "import QtQuick\nimport Qt.labs.platform as P\n"
            "P.SystemTrayIcon {\n"
            f'    icon.source: "{QUrl.fromLocalFile(str(_ICON)).toString()}"\n'
            "    signal clicked()\n"
            "    onMessageClicked: clicked()\n"
            "    onActivated: clicked()\n"
            "}\n"
        ).encode(),
        QUrl(),
    )
    tray = component.create()
    if tray is None:  # sin Qt.labs.platform: se registran pero no se muestran
        import logging

        logging.getLogger("janelkit").warning("notificaciones no disponibles: %s", "; ".join(e.toString() for e in component.errors()))
        return None
    tray.setParent(app.engine)
    component.setParent(tray)
    tray.clicked.connect(_clicked)
    app.qt_app.aboutToQuit.connect(lambda: tray.setProperty("visible", False))
    _tray = tray
    return tray


def _clicked() -> None:
    app = running_app()
    window = app.main_window() if app is not None else None
    if window is not None:
        window.show()
        window.raise_()
        window.requestActivate()
    if _on_click is not None:
        _on_click()


@inspector("notifications")
def _inspect_sent(app: Any) -> list[dict[str, str]]:
    """Notificaciones enviadas con `notify` (`{"title", "message"}`), de la más antigua a la más reciente."""
    return sent()
