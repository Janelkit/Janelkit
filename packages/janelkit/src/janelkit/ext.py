"""API para paquetes que extienden JanelKit (como janelkit-router o janelkit-i18n).

Un paquete de extensión solo usa la API pública: lo que se importa desde `janelkit`,
este módulo, `janelkit.inspect`, `janelkit.compiler` y `janelkit.diagnostics`. Para
añadir subcomandos a `janel`, declara un entry point en el grupo `janelkit.commands`
(ver docs/api.md).

Anfitriones (`Host`, `Container`, `Child`): montar componentes desde Python dentro de un
elemento `.qml` del paquete (así funciona `<Pages>` de janelkit-router; ver `runtime/hosts.py`).
"""
from __future__ import annotations

from typing import Any, Callable

from .runtime.hosts import Child, Container, Host, is_component
from .lifecycle import ask_to_leave
from .reactivity.effects import Gate

__all__ = ["Child", "Container", "Gate", "Host", "app", "ask_to_leave", "inspector", "is_component"]


def app() -> Any:
    """La aplicación en marcha, o None si aún no hay ninguna.

    Públicos: `.engine` (el `QQmlEngine`), `.qt_app` (la `QGuiApplication`) y
    `.main_window()` (la ventana de la vista montada más reciente, o None).
    """
    from .qt_backend.application import Application

    return Application.current


def inspector(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador: `fn(app, *args, **kwargs)` pasa a ser el método `MountedApp.<name>` de `janelkit.inspect`."""
    from .inspect import add_inspector

    def register(fn: Callable[..., Any]) -> Callable[..., Any]:
        add_inspector(name, fn)
        return fn

    return register
