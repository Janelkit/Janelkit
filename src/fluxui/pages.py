"""Navegación entre pantallas: una pila de páginas.

    from fluxui import pages
    from pages.Inicio import Inicio
    from pages.Detalle import Detalle

    nav = pages(Inicio)                       # la primera página

    def abrir(item):
        nav.push(Detalle, item=item, on_borrado=borrar)

En la plantilla, `<Pages stack={nav} />` muestra la página de arriba. Las de
debajo siguen vivas (al volver con `nav.pop()` conservan su estado); las que se
descartan con `pop`, `replace` o `reset` se liberan.
"""
from __future__ import annotations

from typing import Any

from .reactivity import State


class PageStack:
    """Pila de páginas. Cada entrada es un componente importado y sus props/eventos."""

    def __init__(self, first: Any, owner: Any, **kwargs: Any):
        self._owner = owner  # componente que declara la pila
        self._entries: list[tuple[Any, dict[str, Any]]] = []
        self._pages: list[tuple[Any, Any, Any]] = []  # (instancia, item QML, contexto) por entrada
        self._container: Any = None
        self._template: Any = None
        self._depth = State(0)
        self._current = State("")
        self._push_entry(first, kwargs)

    # -- estado reactivo --------------------------------------------------------
    @property
    def depth(self) -> int:
        return self._depth.value

    @property
    def current(self) -> str:
        """Nombre del componente de la página visible (p. ej. "Detalle")."""
        return self._current.value

    @property
    def can_go_back(self) -> bool:
        return self._depth.value > 1

    @property
    def page(self) -> Any:
        """Instancia de la página visible (su `namespace` tiene las variables del script), o None."""
        return self._pages[-1][0] if self._pages else None

    # -- navegación ---------------------------------------------------------------
    def push(self, component: Any, **kwargs: Any) -> None:
        """Muestra `component` encima de la página actual, que se conserva."""
        self._push_entry(component, kwargs)

    def pop(self) -> None:
        """Vuelve a la página anterior y libera la actual. No hace nada en la primera."""
        if len(self._entries) <= 1:
            return
        self._entries.pop()
        self._destroy_top()
        self._sync()

    def replace(self, component: Any, **kwargs: Any) -> None:
        """Sustituye la página actual por `component`."""
        self._entries.pop()
        self._destroy_top()
        self._push_entry(component, kwargs)

    def reset(self, component: Any, **kwargs: Any) -> None:
        """Vacía la pila y empieza de nuevo con `component`."""
        while self._entries:
            self._entries.pop()
            self._destroy_top()
        self._push_entry(component, kwargs)

    # -- internos -----------------------------------------------------------------
    def _push_entry(self, component: Any, kwargs: dict[str, Any]) -> None:
        from .runtime.component import ComponentRef

        if not isinstance(component, ComponentRef):
            raise TypeError("pages()/push() esperan un componente importado: from pages.Inicio import Inicio")
        self._entries.append((component, kwargs))
        if self._container is not None:
            self._create(component, kwargs)
        self._sync()

    def _sync(self) -> None:
        self._depth.value = len(self._entries)
        self._current.value = self._entries[-1][0].name if self._entries else ""
        if self._container is not None:
            from shiboken6 import Shiboken

            if Shiboken.isValid(self._container):
                self._container.setProperty("currentIndex", len(self._pages) - 1)

    def _attach(self, container: Any, template: Any) -> None:
        """La plantilla montó `<Pages stack={...}>`: crear las páginas de la pila."""
        self._detach_all()
        self._container, self._template = container, template
        for component, kwargs in self._entries:
            self._create(component, kwargs)
        self._sync()

    def _detach(self, container: Any) -> None:
        if container is self._container:
            self._detach_all()

    def _detach_all(self) -> None:
        while self._pages:
            self._destroy_top()
        self._container = self._template = None

    def _create(self, component: Any, kwargs: dict[str, Any]) -> None:
        from PySide6.QtQml import QQmlContext, QQmlEngine

        from .compiler import compile_file
        from .compiler.qml_generator import BRIDGE_NAME
        from .runtime.component import ComponentInstance

        owner = self._owner
        host = owner.require_host()
        key = ("page", component.path)
        compiled = owner.compiled.cache.get(key)
        if compiled is None:
            compiled = owner.compiled.cache[key] = compile_file(component.path, owner.compiled.roots or None, as_window=False)
        props, events = split_component_kwargs(component.name, compiled, kwargs)
        instance = ComponentInstance(compiled, host, props, events, parent=owner)
        owner.scope.add(instance.scope)
        parent_context = QQmlEngine.contextForObject(self._container) or host.engine.rootContext()
        context = QQmlContext(parent_context, self._container)
        context.setContextProperty(BRIDGE_NAME, instance.bridge)
        item = host.delegate_for(compiled).create(context)
        if item is None:
            instance.dispose()
            raise RuntimeError(f"no se pudo crear la página {component.name}")
        item.setParentItem(self._container)
        self._pages.append((instance, item, context))

    def _destroy_top(self) -> None:
        if not self._pages:
            return
        from PySide6.QtCore import QCoreApplication, QEvent
        from shiboken6 import Shiboken

        instance, item, context = self._pages.pop()
        instance.dispose()
        self._owner.scope.discard(instance.scope)
        if Shiboken.isValid(item):
            item.setVisible(False)
            item.deleteLater()
        if Shiboken.isValid(context):
            context.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def __repr__(self) -> str:
        return f"<páginas {' > '.join(c.name for c, _ in self._entries)}>"


def split_component_kwargs(name: str, compiled: Any, kwargs: dict[str, Any]) -> tuple[dict[str, State], dict[str, Any]]:
    info = compiled.ir.script_info
    declared_props = set(info.props) if info else set()
    declared_events = set(info.events) if info else set()
    props: dict[str, State] = {}
    events: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key.startswith("on_") and key[3:] in declared_events:
            events[key[3:]] = value
        elif key in declared_props:
            props[key] = value if isinstance(value, State) else State(value)
        else:
            what = f"el evento '{key[3:]}'" if key.startswith("on_") else f"la prop '{key}'"
            raise TypeError(
                f"{name} no declara {what}; props: {', '.join(sorted(declared_props)) or 'ninguna'}; "
                f"eventos: {', '.join('on_' + e for e in sorted(declared_events)) or 'ninguno'}"
            )
    return props, events


def pages(first: Any, **kwargs: Any) -> PageStack:
    """Crea una pila de páginas que empieza en `first`. Se usa en el script de un componente."""
    from .lifecycle import _current

    owner = _current("pages")
    return PageStack(first, owner, **kwargs)
