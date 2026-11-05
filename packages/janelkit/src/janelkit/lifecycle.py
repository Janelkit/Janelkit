"""Ciclo de vida, contexto y referencias de los componentes.

Estas funciones se llaman desde el `<script>` de un componente mientras se
ejecuta (su *preparación*):

    from janelkit import on_mount, on_destroy, provide, inject, ref

    campo = ref()                      # <textfield ref={campo} />

    @on_mount
    def enfocar():
        campo.focus()
        temporizador = iniciar()
        return temporizador.stop       # opcional: se llama al desmontar

    on_destroy(lambda: print("adiós"))

    provide("sesion", sesion)          # visible para todos los descendientes
    tema = inject("tema", "claro")     # lo que provee un antecesor (o el defecto)

No importa Qt: el runtime registra el componente activo con `_setup`.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, Protocol, TypeVar

from .reactivity import Computed, State

F = TypeVar("F", bound=Callable[..., Any])
_MISSING: Any = object()


class _Setup(Protocol):
    def add_mount(self, fn: Callable[[], Any]) -> None: ...
    def add_destroy(self, fn: Callable[[], Any]) -> None: ...
    def add_leave(self, fn: Callable[[], Any]) -> None: ...
    def provide(self, key: Any, value: Any) -> None: ...
    def inject(self, key: Any) -> Any: ...
    gate: Any  # compuerta de visibilidad del sitio donde se montó (reactivity.Gate) o None


_stack: list[_Setup] = []


@contextmanager
def _setup(component: _Setup) -> Iterator[None]:
    """Marca `component` como el que se está preparando (lo usa el runtime)."""
    _stack.append(component)
    try:
        yield
    finally:
        _stack.pop()


def _current(fn_name: str) -> _Setup:
    if not _stack:
        raise RuntimeError(
            f"{fn_name}() solo puede llamarse mientras se ejecuta el <script> de un componente "
            "(en el nivel superior o en funciones llamadas desde él), no más tarde desde un evento"
        )
    return _stack[-1]


def on_mount(fn: F) -> F:
    """Ejecuta `fn` cuando la vista del componente ya existe. Si devuelve una función, se llama al desmontar.

    Se puede usar como decorador.
    """
    _current("on_mount").add_mount(fn)
    return fn


def on_destroy(fn: F) -> F:
    """Ejecuta `fn` al desmontar el componente. Se puede usar como decorador."""
    _current("on_destroy").add_destroy(fn)
    return fn


def before_leave(fn: F) -> F:
    """Pregunta antes de salir: `fn()` se llama al cerrar con la X la ventana que muestra este
    componente y cuando un anfitrión lo va a descartar (`ask_to_leave`; p. ej. `pop` en una
    pila de janelkit-router). Si devuelve False, no se sale. Puede ser `async`
    (p. ej. `await dialogs.confirm(...)`). Se puede usar como decorador."""
    _current("before_leave").add_leave(fn)
    return fn


def provide(key: Any, value: Any) -> None:
    """Pone `value` a disposición de todos los descendientes de este componente bajo `key`."""
    _current("provide").provide(key, value)


def inject(key: Any, default: Any = _MISSING) -> Any:
    """Valor que un componente antecesor proveyó con `provide(key, ...)`, o `default`."""
    try:
        return _current("inject").inject(key)
    except LookupError:
        if default is _MISSING:
            raise LookupError(
                f"ningún componente antecesor provee {key!r}; llama a provide({key!r}, valor) en uno de ellos "
                f"o pasa un valor por defecto: inject({key!r}, defecto)"
            ) from None
        return default


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
    sale) y `proceed` se llama cuando todos han respondido que sí. Si todos responden
    al momento, `proceed` se llama antes de volver y devuelve True."""
    import inspect

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


class Ref:
    """Referencia a un elemento de la plantilla: `campo = ref()` y `<textfield ref={campo} />`.

    `.value` es reactivo: vale `None` hasta que el elemento existe y vuelve a
    `None` cuando se destruye. Los métodos no hacen nada si el elemento no existe.
    """

    __slots__ = ("_item",)

    def __init__(self) -> None:
        self._item: State[Any] = State(None)

    @property
    def value(self) -> Any:
        """El objeto Qt Quick del elemento (`QQuickItem`), o `None`. Interfaz de Qt: úsalo como último recurso."""
        return self._item.value

    @property
    def exists(self) -> bool:
        return self._item.value is not None

    def _attach(self, item: Any) -> None:
        self._item.value = item

    def _detach(self, item: Any) -> None:
        if self._item.peek() is item:
            self._item.value = None

    def _live(self) -> Any:
        item = self._item.peek()
        if item is None:
            return None
        from shiboken6 import Shiboken

        return item if Shiboken.isValid(item) else None

    @property
    def focused(self) -> bool:
        """¿Tiene el elemento (o algo dentro de él) el foco del teclado? No es reactivo: léelo en un manejador."""
        item = self._live()
        if item is None:
            return False
        focus = item.window().activeFocusItem() if item.window() is not None else None
        while focus is not None:
            if focus is item:
                return True
            focus = focus.parentItem()
        return False

    def focus(self) -> None:
        """Da el foco del teclado al elemento."""
        item = self._live()
        if item is not None:
            item.forceActiveFocus()

    def blur(self) -> None:
        """Quita el foco del teclado al elemento."""
        item = self._live()
        if item is not None:
            item.setFocus(False)

    def select_all(self) -> None:
        """Selecciona todo el texto (<textfield>, <textarea>)."""
        self._call("selectAll")

    def scroll_to_start(self) -> None:
        """Lleva una `<list>` o un `<scroll>` al principio."""
        self._call("scrollToStart")

    def scroll_to_end(self) -> None:
        """Lleva una `<list>` o un `<scroll>` al final (con `follow`, vuelve a seguir lo nuevo)."""
        self._call("scrollToEnd")

    def scroll_to(self, target: "int | Ref") -> None:
        """Desplaza lo justo para que se vea: en una `<list>`, la fila `target` (un índice);
        en un `<scroll>`, el elemento de dentro cuyo `ref` es `target`."""
        item = self._live()
        if item is None:
            return
        if isinstance(target, Ref):
            if not item.inherits("QQuickScrollView"):
                raise TypeError("scroll_to(ref) es para <scroll>; en una <list>, pasa el índice de la fila")
            inner = target._live()
            if inner is None:
                return
            if not item.isAncestorOf(inner):
                raise ValueError("scroll_to(): el elemento no está dentro de este <scroll>")
            target = inner
        elif item.inherits("QQuickScrollView"):
            raise TypeError("scroll_to() de un <scroll> recibe el ref de un elemento de dentro")
        self._call("scrollTo", target)

    def _call(self, method: str, *args: Any) -> None:
        item = self._live()
        if item is None:
            return
        from PySide6.QtCore import Q_ARG, QMetaObject

        if not QMetaObject.invokeMethod(item, method, *(Q_ARG("QVariant", a) for a in args)):
            raise TypeError(f"este elemento no admite {method}")

    def __repr__(self) -> str:
        item = self._item.peek()
        return f"ref({type(item).__name__ if item is not None else 'sin elemento'})"


def is_visible() -> Computed[bool]:
    """Reactivo: si el componente se ve ahora mismo.

    Es False mientras está en una página de debajo de la pila, en una sección que no es la
    actual, dentro de un `{#hidden}` que lo oculta o en una fila de `<list>` fuera de la vista.
    Lo que muestra la plantilla ya se aplaza solo; esto sirve para parar a propósito lo que
    hace el script (un muestreo, una cámara):

        visible = is_visible()

        @interval(33, when=visible)
        def refrescar(): ...
    """
    gate = _current("is_visible").gate
    if gate is None:  # la raíz de una ventana
        return Computed(lambda: True)
    return Computed(lambda: gate.visible)


def ref() -> Ref:
    """Crea una referencia para `ref={...}` en la plantilla."""
    return Ref()
