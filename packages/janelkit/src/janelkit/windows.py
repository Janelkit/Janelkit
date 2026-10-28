"""Ventanas secundarias: abrir otro componente `.janel` en su propia ventana.

    from janelkit import open_window
    from components.Settings import Settings     # un .janel con <Window> (o sin ella)

    def ajustes():
        open_window(Settings, user=usuario, on_saved=guardar, modal=True)

- Las palabras clave son las props del componente; las que empiezan por `on_`,
  sus eventos (`on_saved` -> `saved = event()`). Un `state` pasado como prop
  se mantiene reactivo.
- La ventana hereda el contexto (`inject`) del componente que la abre y se
  cierra sola cuando ese componente se desmonta.
- `theme="dark"` le da un tema propio, independiente del de la aplicación.
"""
from __future__ import annotations

from typing import Any

from .reactivity import State


class Window:
    """Una ventana abierta con `open_window`."""

    def __init__(self, app: Any, mounted: Any):
        self._app = app
        self._mounted = mounted
        self._open = State(True)

    @property
    def is_open(self) -> bool:
        """Reactivo: pasa a False cuando la ventana se cierra (por el usuario o con `close()`)."""
        return self._open.value

    @property
    def instance(self) -> Any:
        """Instancia del componente de la ventana (su `namespace` tiene las variables del script)."""
        return self._mounted.instance

    def close(self) -> None:
        if not self._open.peek():
            return
        self._open.value = False
        if self._mounted in self._app.mounted:
            self._app.unmount(self._mounted)

    def focus(self) -> None:
        """Trae la ventana al frente."""
        from shiboken6 import Shiboken

        root = self._mounted.root
        if self._open.peek() and Shiboken.isValid(root):
            root.raise_()
            root.requestActivate()

    def __repr__(self) -> str:
        state = "abierta" if self._open.peek() else "cerrada"
        return f"<ventana {self._mounted.compiled.ir.file} ({state})>"


class _CloseOnDispose:
    def __init__(self, window: Window):
        self.window = window

    def dispose(self) -> None:
        self.window.close()


def open_window(component: Any, *, modal: bool = False, theme: str | None = None, **kwargs: Any) -> Window:
    """Abre `component` (importado de un `.janel`) en una ventana nueva."""
    from PySide6.QtCore import QTimer, Qt

    from .compiler import compile_file
    from .pages import split_component_kwargs
    from .runtime.component import ComponentRef

    if not isinstance(component, ComponentRef) or component.owner is None:
        raise TypeError(
            "open_window() espera un componente importado en el script: "
            "from components.Ajustes import Ajustes; open_window(Ajustes)"
        )
    owner = component.owner
    app = owner.require_host()
    compiled = owner.compiled.cache.get(("window", component.path))
    if compiled is None:
        compiled = owner.compiled.cache[("window", component.path)] = compile_file(
            component.path, owner.compiled.roots or None, as_window=True
        )

    props, events = split_component_kwargs(component.name, compiled, kwargs)

    mounted = app.mount(compiled, props=props, events=events, parent=owner, theme_name=theme)
    window = Window(app, mounted)
    root = mounted.root
    opener = owner_window(app, owner)
    if root.isWindowType():
        if opener is not None:
            root.setTransientParent(opener)
        if modal:
            root.setModality(Qt.WindowModality.WindowModal if opener is not None else Qt.WindowModality.ApplicationModal)

        def on_visible(visible: bool) -> None:
            if not visible and window.is_open:
                QTimer.singleShot(0, window.close)  # cerrar desde fuera de la señal de Qt

        root.visibleChanged.connect(on_visible)
    owner.scope.add(_CloseOnDispose(window))
    return window


def owner_window(app: Any, instance: Any) -> Any:
    """Ventana en la que se muestra `instance`: la del antecesor más cercano que es una vista montada."""
    node = instance
    while node is not None:
        for mounted in app.mounted:
            if mounted.instance is node and mounted.root.isWindowType():
                return mounted.root
        node = node.parent
    return app.main_window()
