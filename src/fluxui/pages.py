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

Dentro de una página, `navigation()` da su pila; `await nav.push(Elegir)` espera a
que esa página vuelva con `nav.back(valor)`. `sections(a=A, b=B)` y
`<Sections of={...} />` son secciones paralelas, cada una con su pila, que se
conservan al cambiar de una a otra. `before_leave` (en lifecycle) puede impedir salir.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from .reactivity import State
from .reactivity.effects import Gate

_creating: list["PageStack"] = []  # pilas que están creando una página (para navigation())


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
            from .tasks import _loop

            self._future = _loop().create_future()
        return (yield from self._future.__await__())


def leave_guards(instance: Any) -> list[Callable[[], Any]]:
    """Las funciones de `before_leave` de `instance` y de todos sus descendientes."""
    out = list(getattr(instance, "leave_guards", ()))
    for child in getattr(instance, "children", ()):
        out.extend(leave_guards(child))
    return out


def ask_to_leave(guards: list[Callable[[], Any]], proceed: Callable[[], Any], refuse: Callable[[], Any] | None = None) -> bool:
    """Consulta los `before_leave` en orden y llama a `proceed` si ninguno devuelve False
    (si alguno lo hace, a `refuse`).

    Si uno es asíncrono, la respuesta llega más tarde: devuelve False (todavía no se
    sale) y `proceed` se llama cuando todos han respondido que sí."""
    for i, guard in enumerate(guards):
        answer = guard()
        if inspect.isawaitable(answer):
            from .tasks import spawn

            async def later(answer: Any = answer, rest: list = guards[i + 1:]) -> None:
                if await answer is not False:
                    ask_to_leave(rest, proceed, refuse)
                elif refuse is not None:
                    refuse()

            spawn(later())
            return False
        if answer is False:
            if refuse is not None:
                refuse()
            return False
    proceed()
    return True


class PageStack:
    """Pila de páginas. Cada entrada es un componente importado y sus props/eventos."""

    def __init__(self, first: Any, owner: Any, **kwargs: Any):
        self._owner = owner  # componente que declara la pila
        self._entries: list[tuple[Any, dict[str, Any]]] = []
        self._results: list[_Result] = []  # uno por entrada: lo que espera quien la abrió
        self._pages: list[tuple[Any, Any, Any]] = []  # (instancia, item QML, contexto) por entrada
        # Compuertas de visibilidad (reactivity.Gate): la de la pila (cerrada si su sección no se
        # ve) y una por página (cerradas las de debajo). Lo que no se ve se pone al día al verse.
        self._gate = Gate()
        self._gates: list[Gate] = []
        self._container: Any = None
        self._template: Any = None
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
        return self._pages[-1][0] if self._pages else None

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
        guards = [g for instance, _, _ in self._pages[-count:] for g in leave_guards(instance)] if count else []
        ask_to_leave(guards, lambda: (proceed(), done.resolve(True)), lambda: done.resolve(False))
        return done

    def _discard(self, count: int, value: Any = None) -> None:
        for _ in range(count):
            self._entries.pop()
            self._results.pop().resolve(value)
            self._destroy_top()
        if count:
            self._sync()

    # -- internos -----------------------------------------------------------------
    def _push_entry(self, component: Any, kwargs: dict[str, Any]) -> _Result:
        from .runtime.component import ComponentRef

        if not isinstance(component, ComponentRef):
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
        if self._container is not None:
            from shiboken6 import Shiboken

            if Shiboken.isValid(self._container):
                for i, gate in enumerate(self._gates):
                    gate.set_open(i == len(self._gates) - 1)
                self._container.setProperty("currentIndex", len(self._pages) - 1)
                self._container.setProperty("fxCanGoBack", len(self._entries) > 1)
                top = self._pages[-1][0] if self._pages else None
                if self._shown is not None and top is not self._shown[0]:  # transition: en <Pages>
                    depth = len(self._pages)
                    self._container.setProperty("fxDirection", (depth > self._shown[1]) - (depth < self._shown[1]))
                    self._container.setProperty("fxShown", self._container.property("fxShown") + 1)
                self._shown = (top, len(self._pages))

    def _attach(self, container: Any, template: Any) -> None:
        """La plantilla montó `<Pages stack={...}>`: crear las páginas de la pila."""
        self._detach_all()
        self._container, self._template = container, template
        self._gate.parent = getattr(template, "gate", None)  # p. ej. <Pages> dentro de un {#hidden}
        self._shown = None  # la primera página no se anima
        container.fxBack.connect(self.pop)  # Alt+←, el botón «atrás» del ratón (FxPages.qml)
        for component, kwargs in self._entries:
            self._create(component, kwargs)
        self._sync()

    def _detach(self, container: Any) -> None:
        if container is self._container:
            self._detach_all()

    def _detach_all(self) -> None:
        while self._pages:
            self._destroy_top()
        if self._container is not None:
            from shiboken6 import Shiboken

            if Shiboken.isValid(self._container):
                self._container.fxBack.disconnect(self.pop)
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
        gate = Gate(self._gate)
        _creating.append(self)
        try:
            instance = ComponentInstance(compiled, host, props, events, parent=owner, gate=gate)
        finally:
            _creating.pop()
        instance.page_stack = self
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
        self._gates.append(gate)

    def _destroy_top(self) -> None:
        if not self._pages:
            return
        from PySide6.QtCore import QCoreApplication, QEvent, QTimer
        from shiboken6 import Shiboken

        instance, item, context = self._pages.pop()
        self._gates.pop()
        instance.dispose()
        self._owner.scope.discard(instance.scope)
        if Shiboken.isValid(item):
            item.setVisible(False)
            item.setParentItem(None)  # fuera del contenedor ya, aunque Qt la borre después
            item.deleteLater()
        if Shiboken.isValid(context):
            context.deleteLater()
        # Borrarlas ya, pero no dentro del evento en curso: back() puede venir de un clic
        # o una tecla de la propia página, y Qt aún está entregándoselo.
        QTimer.singleShot(0, lambda: QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete))

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


def navigation() -> PageStack:
    """La pila de la página en la que está este componente (de `pages()` o de una sección)."""
    from .lifecycle import _current

    node = _current("navigation")
    while node is not None:
        stack = getattr(node, "page_stack", None)
        if stack is not None:
            return stack
        node = node.parent
    if _creating:  # la página se está creando: aún no tiene `page_stack`
        return _creating[-1]
    raise LookupError(
        "navigation() solo funciona dentro de una página de pages() o de sections(); "
        "en el componente que declara la pila, usa esa variable (nav = pages(Inicio))"
    )


class Sections:
    """Secciones paralelas, cada una con su pila de páginas: `sections(proyectos=Proyectos, ...)`.

    `<Sections of={secciones} />` muestra la actual. Una sección se crea la primera vez
    que se muestra y después se conserva entera al cambiar de sección."""

    def __init__(self, owner: Any, first: dict[str, Any]):
        if not first:
            raise TypeError("sections() necesita al menos una sección: sections(inicio=Inicio)")
        self._stacks = {name: PageStack(component, owner) for name, component in first.items()}
        self._current = State(next(iter(first)))
        self._container: Any = None
        self._template: Any = None
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

        if not Shiboken.isValid(self._container):
            return
        name = self._current.peek()
        for other, stack in self._stacks.items():  # lo que muestran las otras secciones espera
            stack._gate.set_open(other == name)
        first = not self._items
        if name not in self._items:
            self._items[name] = item = self._new_pages()
            self._stacks[name]._attach(item, self._template)
        index = list(self._items).index(name)
        if index != self._container.property("currentIndex"):
            self._container.setProperty("currentIndex", index)
            if not first:  # <Sections transition:fade>: anima la sección que entra
                self._container.setProperty("fxDirection", 0)
                self._container.setProperty("fxShown", self._container.property("fxShown") + 1)

    def _new_pages(self) -> Any:
        from PySide6.QtQml import QQmlComponent, QQmlEngine

        host = self._stacks[self._current.peek()]._owner.require_host()
        component = QQmlComponent(host.engine)
        component.setData(b"import Flux\nFxPages {}\n", host._url_for(self._template.component.compiled, part="sections"))
        context = QQmlEngine.contextForObject(self._container) or host.engine.rootContext()
        item = component.create(context)
        if item is None:
            raise RuntimeError(f"no se pudo crear la sección: {component.errorString()}")
        item.setParentItem(self._container)
        item.setParent(self._container)
        for prop in ("fxTransition", "fxTransitionMs"):  # las páginas de cada sección, igual
            item.setProperty(prop, self._container.property(prop))
        return item

    def _attach(self, container: Any, template: Any) -> None:
        self._detach_all()
        self._container, self._template = container, template
        self._sync()

    def _detach(self, container: Any) -> None:
        if container is self._container:
            self._detach_all()

    def _detach_all(self) -> None:
        from shiboken6 import Shiboken

        for name, item in self._items.items():
            self._stacks[name]._detach(item)
            if Shiboken.isValid(item):
                item.setVisible(False)
                item.deleteLater()
        self._items = {}
        self._container = self._template = None

    def __repr__(self) -> str:
        return f"<secciones {', '.join(self._stacks)}; visible {self._current.peek()}>"


def sections(**components: Any) -> Sections:
    """Crea secciones paralelas (`sections(proyectos=Proyectos, personas=Personas)`), cada una con su pila."""
    from .lifecycle import _current

    return Sections(_current("sections"), components)
