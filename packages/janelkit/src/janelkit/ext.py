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
from .session import Session
from .reactivity.effects import Gate, Scope
from .reactivity.writes import on_write, own

__all__ = [
    "Child", "Container", "Gate", "Host", "Scope", "Session", "app", "ask_to_leave", "inspector", "is_component",
    "on_write", "own", "session",
]  # fmt: skip


def app() -> Any:
    """La aplicación en marcha, o None si aún no hay ninguna.

    Públicos: `.engine` (el `QQmlEngine`), `.qt_app` (la `QGuiApplication`) y
    `.main_window()` (la ventana de la vista montada más reciente, o None).
    """
    from .qt_backend.application import Application

    return Application.current


def session() -> Session | None:
    """La sesión de la aplicación en marcha (una por `run()` y por cada `inspect.mount()`), o None.

    `.data_dir` (carpeta de datos), `.data` (un diccionario para los paquetes: usa una
    clave propia), `.on_end(fn)` (al cerrar la aplicación o desmontarla), `.name`.
    """
    from . import session as _session

    return _session.current()


def inspector(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador: `fn(app, *args, **kwargs)` pasa a ser el método `MountedApp.<name>` de `janelkit.inspect`."""
    from .inspect import add_inspector

    def register(fn: Callable[..., Any]) -> Callable[..., Any]:
        add_inspector(name, fn)
        return fn

    return register
