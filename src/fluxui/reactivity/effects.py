"""Núcleo reactivo: seguimiento automático de dependencias, efectos y lotes.

Modelo:
- Una *fuente* (`State`, `Computed`) registra quién la lee mientras hay un
  observador activo.
- Un *observador* (`Effect`, `Computed`) se marca obsoleto cuando cambia una de
  sus fuentes. Los efectos se reejecutan al terminar el lote actual; los
  `Computed` solo se recalculan cuando alguien vuelve a leerlos.
- Un *ámbito* (`Scope`) agrupa lo creado por una instancia de componente para
  liberarlo de una vez al desmontarla.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

_observer_stack: list["Observer"] = []
_scope_stack: list["Scope"] = []
_batch_depth = 0
_flushing = False
_pending: dict["Effect", None] = {}  # conjunto ordenado
_settled: list[Callable[[], Any]] = []  # se ejecutan cuando ya no queda ningún efecto pendiente
_MAX_FLUSH_ITERATIONS = 10_000
# El sistema reactivo vive en un solo hilo (el de la interfaz). Desde otros hilos
# (p. ej. código de `background()`) leer no registra dependencias y escribir es un error.
_OWNER = threading.get_ident()
_get_ident = threading.get_ident


class ReactiveCycleError(RuntimeError):
    """Los efectos se reactivan entre sí indefinidamente."""


class WrongThreadError(RuntimeError):
    """Se modificó estado reactivo fuera del hilo de la interfaz."""


def check_thread() -> None:
    """Error si se intenta modificar estado fuera del hilo de la interfaz."""
    if _get_ident() != _OWNER:
        raise WrongThreadError(
            "el estado solo se puede modificar desde el hilo de la interfaz; en código de "
            "background() devuelve el valor y asígnalo tras el await: x.value = await background(f)"
        )


class Source:
    def __init__(self) -> None:
        self._subscribers: dict[Observer, None] = {}

    def _track(self) -> None:
        if _observer_stack and _get_ident() == _OWNER:
            observer = _observer_stack[-1]
            if observer is not None:
                observer._add_dependency(self)

    def _notify(self) -> None:
        check_thread()
        for observer in list(self._subscribers):
            observer._mark_stale()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


class Observer:
    def __init__(self) -> None:
        self._dependencies: dict[Source, None] = {}
        self.disposed = False
        if _scope_stack:
            _scope_stack[-1].add(self)

    def _add_dependency(self, source: Source) -> None:
        if source not in self._dependencies:
            self._dependencies[source] = None
            source._subscribers[self] = None

    def _clear_dependencies(self) -> None:
        for source in self._dependencies:
            source._subscribers.pop(self, None)
        self._dependencies.clear()

    def _collect(self, fn: Callable[[], Any]) -> Any:
        """Ejecuta `fn` registrando de nuevo las dependencias de este observador."""
        self._clear_dependencies()
        _observer_stack.append(self)
        try:
            return fn()
        finally:
            _observer_stack.pop()

    def _mark_stale(self) -> None:  # pragma: no cover - abstracto
        raise NotImplementedError

    def dispose(self) -> None:
        self.disposed = True
        self._clear_dependencies()
        _pending.pop(self, None)  # type: ignore[call-overload]


class Effect(Observer):
    """Ejecuta `fn` ahora y cada vez que cambie algo de lo que leyó.

    Si `fn` devuelve una función, es su *limpieza*: se llama antes de la
    siguiente ejecución y al liberar el efecto (p. ej. al desmontar el componente).
    """

    def __init__(self, fn: Callable[[], Any], on_error: Callable[[BaseException], None] | None = None):
        super().__init__()
        self._fn = fn
        self._on_error = on_error
        self._cleanup: Callable[[], Any] | None = None
        self.run()

    def run(self) -> None:
        if self.disposed:
            return
        try:
            self._run_cleanup()
            result = self._collect(self._fn)
            if callable(result):
                self._cleanup = result
        except Exception as exc:  # noqa: BLE001 - se delega al manejador
            if self._on_error is None:
                raise
            self._on_error(exc)

    def _run_cleanup(self) -> None:
        cleanup, self._cleanup = self._cleanup, None
        if cleanup is not None:
            with untracked():
                cleanup()

    def dispose(self) -> None:
        if self.disposed:
            return
        super().dispose()
        try:
            self._run_cleanup()
        except Exception as exc:  # noqa: BLE001
            if self._on_error is None:
                raise
            self._on_error(exc)

    def _mark_stale(self) -> None:
        if self.disposed:
            return
        _pending[self] = None
        if _batch_depth == 0:
            _flush()


class Scope:
    """Conjunto de observadores (y ámbitos hijos) que se liberan juntos."""

    def __init__(self) -> None:
        self._observers: dict[Observer | Scope, None] = {}
        self.disposed = False

    def add(self, observer: Observer | Scope) -> None:
        if self.disposed:
            observer.dispose()
        else:
            self._observers[observer] = None

    def discard(self, observer: Observer | Scope) -> None:
        self._observers.pop(observer, None)

    def __len__(self) -> int:
        return len(self._observers)

    @contextmanager
    def active(self) -> Iterator["Scope"]:
        _scope_stack.append(self)
        try:
            yield self
        finally:
            _scope_stack.pop()

    def dispose(self) -> None:
        self.disposed = True
        observers = list(self._observers)
        self._observers.clear()
        for observer in reversed(observers):  # lo creado después se libera antes
            observer.dispose()


def _flush() -> None:
    global _flushing
    if _flushing:  # un efecto cambió estado: el bucle en curso recogerá lo pendiente
        return
    _flushing = True
    try:
        iterations = 0
        while _pending or _settled:
            iterations += 1
            if iterations > _MAX_FLUSH_ITERATIONS:
                _pending.clear()
                _settled.clear()
                raise ReactiveCycleError("ciclo reactivo: los efectos se reactivan entre sí sin estabilizarse")
            if not _pending:
                _settled.pop(0)()
                continue
            effect = next(iter(_pending))
            del _pending[effect]
            effect.run()
    finally:
        _flushing = False


def when_settled(fn: Callable[[], Any]) -> None:
    """Llama a `fn` al terminar el cambio en curso (el lote y todos sus efectos), o ya si no hay ninguno."""
    if _flushing or _batch_depth:
        _settled.append(fn)
    else:
        fn()


@contextmanager
def batch() -> Iterator[None]:
    """Agrupa varios cambios de estado: los efectos se ejecutan una vez al final."""
    global _batch_depth
    _batch_depth += 1
    try:
        yield
    finally:
        _batch_depth -= 1
        if _batch_depth == 0:
            _flush()


@contextmanager
def untracked() -> Iterator[None]:
    """Lee estado sin registrar dependencias en el observador actual."""
    _observer_stack.append(None)  # type: ignore[arg-type]
    try:
        yield
    finally:
        _observer_stack.pop()


def current_scope() -> "Scope | None":
    """Ámbito activo (p. ej. el del componente que se está preparando), o None."""
    return _scope_stack[-1] if _scope_stack else None


def effect(fn: Callable[[], Any]) -> Effect:
    return Effect(fn)
