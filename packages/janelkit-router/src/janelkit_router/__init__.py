"""Navegación entre pantallas para JanelKit: pilas de páginas y secciones.

    from janelkit_router import pages, Pages
    from pages.Inicio import Inicio
    from pages.Detalle import Detalle

    nav = pages(Inicio)                       # la primera página

    def abrir(item):
        nav.push(Detalle, item=item, on_borrado=borrar)

En la plantilla, `<Pages stack={nav} />` muestra la página de arriba. Las de
debajo siguen vivas (al volver con `nav.pop()` conservan su estado); las que se
descartan con `pop`, `replace` o `reset` se liberan.

Dentro de una página, `navigation()` da su pila; `await nav.push(Elegir)` espera a
que esa página vuelva con `nav.back(valor)`. `sections(a=A, b=B)` y
`<Sections of={...} />` son secciones paralelas, cada una con su pila, que se
conservan al cambiar de una a otra. `before_leave` (del núcleo) puede impedir salir.

Solo usa la API pública de JanelKit: `<Pages>` y `<Sections>` son elementos `.qml` de
este paquete con raíz `JkDeck` y una propiedad `JkHost`, y las pilas son anfitriones
(`janelkit.ext.Host`) que montan las páginas con `Container.mount`.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from janelkit import State, inject
from janelkit.ext import Child, Container, Gate, Host, app, ask_to_leave, is_component

__version__ = "0.2.0.0"
__all__ = ["PageStack", "SectionSet", "__version__", "navigation", "pages", "sections"]

_NAV = object()  # clave de contexto: la pila de la página (la lee navigation())
_PAGES_QML = Path(__file__).with_name("Pages.qml")


class _Result:
    """Lo que devuelve `push`: se puede ignorar, o esperar (`await`) el valor de `back(valor)`."""

    __slots__ = ("done", "value", "_future")

    def __init__(self) -> None:
        self.done = False
        self.value: Any = None
        self._future: Any = None

    def resolve(self, value: Any) -> None:
        if self.done:
            return
        self.done, self.value = True, value
        if self._future is not None and not self._future.done():
            self._future.set_result(value)

    def __await__(self):
        if self.done:
            return self.value
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return (yield from self._future.__await__())


class PageStack(Host):
    """Pila de páginas. Cada entrada es un componente importado y sus props/eventos."""

    def __init__(self, first: Any, **kwargs: Any):
        self._entries: list[tuple[Any, dict[str, Any]]] = []
        self._results: list[_Result] = []  # uno por entrada: lo que espera quien la abrió
        self._pages: list[Child] = []  # una por entrada, mientras <Pages> existe
        # Compuerta de la pila: cerrada si su sección no se ve. Cada página tiene la suya
        # (cerradas las de debajo): lo que no se ve se pone al día al verse.
        self._gate = Gate()
        self._container: Container | None = None
        self._depth = State(0)
        self._current = State("")
        self._shown: tuple[Any, int] | None = None  # (página visible, profundidad): para animar la que entra
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
        return self._pages[-1].instance if self._pages else None

    # -- navegación ---------------------------------------------------------------
    def push(self, component: Any, **kwargs: Any) -> _Result:
        """Muestra `component` encima de la página actual, que se conserva.

        `await nav.push(...)` espera a que la página vuelva con `back(valor)` (None si
        se descarta de otra forma)."""
        return self._push_entry(component, kwargs)

    # pop, back, replace y reset se pueden esperar: `if await nav.reset(Inicio): ...` da True
    # si se salió y False si un before_leave lo impidió (la respuesta puede llegar más tarde).
    def pop(self) -> _Result:
        """Vuelve a la página anterior y libera la actual. No hace nada en la primera."""
        return self.back()

    def back(self, value: Any = None) -> _Result:
        """Como `pop`, y quien abrió esta página con `await nav.push(...)` recibe `value`."""
        if len(self._entries) <= 1:
            done = _Result()
            done.resolve(False)
            return done
        return self._leave(1, lambda: self._discard(1, value))

    def replace(self, component: Any, **kwargs: Any) -> _Result:
        """Sustituye la página actual por `component`."""
        return self._leave(1, lambda: (self._discard(1), self._push_entry(component, kwargs)))

    def reset(self, component: Any, **kwargs: Any) -> _Result:
        """Vacía la pila y empieza de nuevo con `component`."""
        return self._leave(len(self._entries), lambda: (self._discard(len(self._entries)), self._push_entry(component, kwargs)))

    def _leave(self, count: int, proceed: Callable[[], Any]) -> _Result:
        """Descarta las `count` páginas de arriba si sus `before_leave` lo permiten."""
        done = _Result()
        guards = [g for page in self._pages[-count:] for g in page.leave_guards()] if count else []
        ask_to_leave(guards, lambda: (proceed(), done.resolve(True)), lambda: done.resolve(False))
        return done

    def _discard(self, count: int, value: Any = None) -> None:
        for _ in range(count):
            self._entries.pop()
            self._results.pop().resolve(value)
            if self._pages:
                self._pages.pop().dispose()
        if count:
            self._sync()

    # -- internos -----------------------------------------------------------------
    def _push_entry(self, component: Any, kwargs: dict[str, Any]) -> _Result:
        if not is_component(component):
            raise TypeError("pages()/push() esperan un componente importado: from pages.Inicio import Inicio")
        result = _Result()
        self._entries.append((component, kwargs))
        self._results.append(result)
        if self._container is not None:
            self._create(component, kwargs)
        self._sync()
        return result

    def _sync(self) -> None:
        self._depth.value = len(self._entries)
        self._current.value = self._entries[-1][0].name if self._entries else ""
        container = self._container
        if container is None:
            return
        from shiboken6 import Shiboken

        if not Shiboken.isValid(container.item):
            return
        for i, page in enumerate(self._pages):
            page.visibility.set_open(i == len(self._pages) - 1)
        item = container.item
        item.setProperty("currentIndex", len(self._pages) - 1)
        item.setProperty("jkCanGoBack", len(self._entries) > 1)
        top = self._pages[-1] if self._pages else None
        if self._shown is not None and top is not self._shown[0]:  # transition: en <Pages>
            depth = len(self._pages)
            item.setProperty("jkDirection", (depth > self._shown[1]) - (depth < self._shown[1]))
            item.setProperty("jkShown", item.property("jkShown") + 1)
        self._shown = (top, len(self._pages))

    def attach(self, container: Container) -> None:
        """La plantilla montó `<Pages stack={...}>`: crear las páginas de la pila."""
        self._detach_all()
        self._container = container
        self._gate.parent = container.visibility  # p. ej. <Pages> dentro de un {#hidden}
        self._shown = None  # la primera página no se anima
        container.item.jkBack.connect(self.pop)  # Alt+←, el botón «atrás» del ratón (Pages.qml)
        for component, kwargs in self._entries:
            self._create(component, kwargs)
        self._sync()

    def detach(self, container: Container) -> None:
        if self._container is not None and container.item is self._container.item:
            self._detach_all()

    def _detach_all(self) -> None:
        while self._pages:
            self._pages.pop().dispose()
        if self._container is not None:
            from shiboken6 import Shiboken

            if Shiboken.isValid(self._container.item):
                self._container.item.jkBack.disconnect(self.pop)
        self._container = None

    def _create(self, component: Any, kwargs: dict[str, Any]) -> None:
        assert self._container is not None
        page = self._container.mount(component, visibility=self._gate, context={_NAV: self}, **kwargs)
        self._pages.append(page)

    def __repr__(self) -> str:
        return f"<páginas {' > '.join(c.name for c, _ in self._entries)}>"


def pages(first: Any, **kwargs: Any) -> PageStack:
    """Crea una pila de páginas que empieza en `first` (un componente importado)."""
    return PageStack(first, **kwargs)


def navigation() -> PageStack:
    """La pila de la página en la que está este componente (de `pages()` o de una sección)."""
    try:
        return inject(_NAV)
    except LookupError:
        raise LookupError(
            "navigation() solo funciona dentro de una página de pages() o de sections(); "
            "en el componente que declara la pila, usa esa variable (nav = pages(Inicio))"
        ) from None


class SectionSet(Host):
    """Secciones paralelas, cada una con su pila de páginas: `sections(proyectos=Proyectos, ...)`.

    `<Sections of={secciones} />` muestra la actual. Una sección se crea la primera vez
    que se muestra y después se conserva entera al cambiar de sección."""

    def __init__(self, first: dict[str, Any]):
        if not first:
            raise TypeError("sections() necesita al menos una sección: sections(inicio=Inicio)")
        self._stacks = {name: PageStack(component) for name, component in first.items()}
        self._current = State(next(iter(first)))
        self._container: Container | None = None
        self._items: dict[str, Any] = {}  # <Pages> de cada sección ya creada

    @property
    def current(self) -> str:
        """Nombre de la sección visible. Reactivo."""
        return self._current.value

    @property
    def names(self) -> list[str]:
        return list(self._stacks)

    @property
    def stack(self) -> PageStack:
        """La pila de la sección visible."""
        return self._stacks[self._current.value]

    def __getitem__(self, name: str) -> PageStack:
        return self._stacks[name]

    def show(self, name: str) -> None:
        """Muestra la sección `name`, tal como se dejó."""
        if name not in self._stacks:
            raise KeyError(f"no hay una sección {name!r}; hay: {', '.join(self._stacks)}")
        self._current.value = name
        self._sync()

    def _sync(self) -> None:
        if self._container is None:
            return
        from shiboken6 import Shiboken

        outer = self._container.item
        if not Shiboken.isValid(outer):
            return
        name = self._current.peek()
        for other, stack in self._stacks.items():  # lo que muestran las otras secciones espera
            stack._gate.set_open(other == name)
        first = not self._items
        if name not in self._items:
            self._items[name] = item = self._new_pages()
            self._stacks[name].attach(self._container.nested(item))
        index = list(self._items).index(name)
        if index != outer.property("currentIndex"):
            outer.setProperty("currentIndex", index)
            if not first:  # <Sections transition:fade>: anima la sección que entra
                outer.setProperty("jkDirection", 0)
                outer.setProperty("jkShown", outer.property("jkShown") + 1)

    def _new_pages(self) -> Any:
        """Un <Pages> para la sección, dentro de <Sections>."""
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent, QQmlEngine

        assert self._container is not None
        outer = self._container.item
        engine = app().engine
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(_PAGES_QML)))
        context = QQmlEngine.contextForObject(outer) or engine.rootContext()
        item = component.create(context)
        if item is None:
            raise RuntimeError(f"no se pudo crear la sección: {component.errorString()}")
        item.setParentItem(outer)
        item.setParent(outer)
        for prop in ("jkTransition", "jkTransitionMs"):  # las páginas de cada sección, igual
            item.setProperty(prop, outer.property(prop))
        return item

    def attach(self, container: Container) -> None:
        self._detach_all()
        self._container = container
        self._sync()

    def detach(self, container: Container) -> None:
        if self._container is not None and container.item is self._container.item:
            self._detach_all()

    def _detach_all(self) -> None:
        from shiboken6 import Shiboken

        for name, item in self._items.items():
            stack = self._stacks[name]
            if stack._container is not None:
                stack.detach(stack._container)
            if Shiboken.isValid(item):
                item.setVisible(False)
                item.deleteLater()
        self._items = {}
        self._container = None

    def __repr__(self) -> str:
        return f"<secciones {', '.join(self._stacks)}; visible {self._current.peek()}>"


def sections(**components: Any) -> SectionSet:
    """Crea secciones paralelas (`sections(proyectos=Proyectos, personas=Personas)`), cada una con su pila."""
    return SectionSet(components)
