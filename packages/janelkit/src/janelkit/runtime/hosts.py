"""Anfitriones: objetos de Python que montan componentes dentro de un elemento de la plantilla.

Es la pieza con la que se construyen elementos como `<Pages>` de janelkit-router:

- Un paquete reparte un elemento `.qml` cuya raíz es `JkDeck` (un mazo: muestra uno de
  sus hijos, que ocupa todo el sitio) y que declara `property JkHost stack`.
- En la plantilla, `<Pages stack={nav} />` conecta ese elemento con `nav`, un `Host`: el
  runtime llama a `nav.attach(container)` cuando el elemento existe y a
  `nav.detach(container)` cuando se destruye.
- Con `container.mount(Componente, **props_y_on_eventos)` el anfitrión crea un componente
  hijo dentro del elemento: hijo del componente que tiene la plantilla (hereda su
  contexto, se libera con él) y con su propia compuerta de visibilidad (`Gate`): lo que
  muestra un hijo oculto espera y se pone al día al verse.

Se usa desde `janelkit.ext`. No importa Qt hasta que monta algo.
"""
from __future__ import annotations

from typing import Any, Callable

from ..lifecycle import leave_guards
from ..reactivity import State
from ..reactivity.effects import Gate


class Host:
    """Objeto del script que controla un elemento: lo recibe una propiedad `JkHost` de un `.qml`."""

    def attach(self, container: "Container") -> None:  # pragma: no cover - abstracto
        """El elemento ya existe: crear lo que deba mostrar con `container.mount(...)`."""
        raise NotImplementedError

    def detach(self, container: "Container") -> None:  # pragma: no cover - abstracto
        """El elemento se destruye: liberar los hijos montados en él (`Child.dispose()`)."""
        raise NotImplementedError


class Container:
    """Un elemento de la plantilla conectado a un `Host`. Lo crea el runtime."""

    __slots__ = ("item", "_template")

    def __init__(self, item: Any, template: Any):
        self.item = item  # el objeto Qt (QQuickItem) del elemento
        self._template = template

    @property
    def visibility(self) -> Gate | None:
        """Compuerta del sitio donde está el elemento (p. ej. dentro de un `{#hidden}`), o None."""
        return getattr(self._template, "gate", None)

    def nested(self, item: Any) -> "Container":
        """Otro elemento creado por el anfitrión dentro de este (p. ej. un mazo por sección), con el mismo dueño."""
        return Container(item, self._template)

    def mount(self, component: Any, *, visibility: Gate | None = None, context: dict[Any, Any] | None = None,
              **kwargs: Any) -> "Child":  # fmt: skip
        """Crea `component` (importado de un `.janel`) dentro del elemento, al final de sus hijos.

        Las palabras clave son sus props y, con `on_`, sus eventos, como en `open_window`.
        `visibility` es la compuerta de fuera de la suya (por defecto, la del elemento).
        `context`: valores que el hijo y sus descendientes leen con `inject` (el hijo
        también, mientras se ejecuta su script)."""
        from PySide6.QtQml import QQmlContext, QQmlEngine

        from ..compiler import compile_file
        from ..compiler.qml_generator import BRIDGE_NAME
        from .component import ComponentInstance, ComponentRef

        if not isinstance(component, ComponentRef):
            raise TypeError(f"mount() espera un componente importado de un .janel, no {type(component).__name__}")
        owner = self._template.component
        host = owner.require_host()
        key = ("mount", component.path)
        compiled = owner.compiled.cache.get(key)
        if compiled is None:
            compiled = owner.compiled.cache[key] = compile_file(component.path, owner.compiled.roots or None, as_window=False)
        props, events = split_component_kwargs(component.name, compiled, kwargs)
        gate = Gate(visibility if visibility is not None else self.visibility)
        instance = ComponentInstance(compiled, host, props, events, parent=owner, gate=gate, context=context)
        owner.scope.add(instance.scope)
        parent_context = QQmlEngine.contextForObject(self.item) or host.engine.rootContext()
        qml_context = QQmlContext(parent_context, self.item)
        qml_context.setContextProperty(BRIDGE_NAME, instance.bridge)
        item = host.delegate_for(compiled).create(qml_context)
        if item is None:
            instance.dispose()
            owner.scope.discard(instance.scope)
            raise RuntimeError(f"no se pudo crear {component.name}")
        item.setParentItem(self.item)
        return Child(component.name, instance, item, gate, qml_context, owner)


class Child:
    """Un componente montado con `Container.mount`."""

    __slots__ = ("name", "instance", "item", "visibility", "_context", "_owner")

    def __init__(self, name: str, instance: Any, item: Any, visibility: Gate, context: Any, owner: Any):
        self.name = name  # nombre del componente (p. ej. "Detalle")
        self.instance = instance  # su `namespace` tiene las variables del script
        self.item = item  # la raíz de su vista (QQuickItem)
        self.visibility = visibility  # su compuerta: .set_open(False) aplaza lo que muestra
        self._context = context
        self._owner = owner

    def leave_guards(self) -> list[Callable[[], Any]]:
        """Los `before_leave` del hijo y de sus descendientes, para `ask_to_leave`."""
        return leave_guards(self.instance)

    def dispose(self) -> None:
        """Libera el hijo (sus `on_destroy` se ejecutan) y quita su vista del elemento."""
        from PySide6.QtCore import QCoreApplication, QEvent, QTimer
        from shiboken6 import Shiboken

        self.instance.dispose()
        self._owner.scope.discard(self.instance.scope)
        if Shiboken.isValid(self.item):
            self.item.setVisible(False)
            self.item.setParentItem(None)  # fuera del elemento ya, aunque Qt lo borre después
            self.item.deleteLater()
        if Shiboken.isValid(self._context):
            self._context.deleteLater()
        # Borrarlo ya, pero no dentro del evento en curso: quien lo descarta puede venir de un
        # clic o una tecla del propio hijo, y Qt aún está entregándoselo.
        QTimer.singleShot(0, lambda: QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete))

    def __repr__(self) -> str:
        return f"<hijo {self.name}>"


def is_component(value: Any) -> bool:
    """¿Es `value` un componente importado de un `.janel` (lo que aceptan `mount` y `open_window`)?"""
    from .component import ComponentRef

    return isinstance(value, ComponentRef)


def split_component_kwargs(name: str, compiled: Any, kwargs: dict[str, Any]) -> tuple[dict[str, State], dict[str, Any]]:
    """Separa las palabras clave en props y eventos (`on_x`) del componente; error si no los declara."""
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
