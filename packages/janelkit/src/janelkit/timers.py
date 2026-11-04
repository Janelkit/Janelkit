"""Temporizadores ligados al componente.

    from janelkit import interval, timeout

    @interval(250)                     # cada 250 ms mientras exista el componente
    def muestrear():
        cpu.value = leer_cpu()

    ocultar = timeout(3000, lambda: aviso.set(""))   # una vez, a los 3 s
    ocultar.restart()                  # vuelve a contar desde cero (p. ej. "escribiendo…")

- Creados en el script de un componente (o en algo que se ejecuta dentro de
  él, como `on_mount` o un manejador, también después de un `await`), se
  detienen solos al desmontarlo.
- Creados fuera de todo componente (p. ej. en un servicio), JanelKit los guarda
  mientras estén activos: no hace falta conservar la referencia para que se disparen.
- Cada ejecución agrupa sus cambios de estado (`batch`) y, si la función es
  `async def`, se lanza con `spawn` (y se cancela con el componente). Mientras
  una ejecución asíncrona no termina, los tics siguientes se saltan: un
  muestreo lento no se acumula.
- Un error en la función se registra en el logger `janelkit`; el temporizador sigue.
- `.active` es reactivo; `.stop()`, `.start()` y `.restart()` lo controlan.
- Métricas (no reactivas, para medir): `.runs` (ejecuciones), `.skipped` (tics saltados
  porque la anterior seguía en marcha) y `.last_duration` (segundos de la última
  ejecución completa, contando la parte async; None antes de la primera).
- `when=` lo condiciona a algo reactivo (un `state`, un `computed`, `is_visible()` o una
  función que los lea): mientras sea falso, el temporizador no cuenta; al volver a ser
  verdadero, cuenta de nuevo desde cero.

    visible = is_visible()

    @interval(33, when=visible)        # solo mientras el componente se ve
    def refrescar(): ...
"""
from __future__ import annotations

import inspect
import logging
import time
from contextlib import nullcontext
from typing import Any, Callable, overload

from .reactivity import Effect, State, batch, untracked
from .reactivity.effects import current_scope

log = logging.getLogger("janelkit")
Fn = Callable[[], Any]
When = Any  # State, Computed, Prop o una función sin argumentos que lea estado reactivo

# Temporizadores activos sin ámbito: sin esta referencia, Python los recolectaría
# (con su QTimer) antes de dispararse.
_unscoped: set["Timer"] = set()


class Timer:
    """Un temporizador de `interval` o `timeout`."""

    def __init__(self, ms: float, fn: Fn, repeat: bool, when: When = None):
        self.ms = max(0, int(ms))
        self.fn = fn
        self.repeat = repeat
        self._active = State(False)
        self._qt: Any = None
        self._running: Any = None  # tarea de la última ejecución, si fn es async
        self._wanted = False  # lo pidió start() y no lo ha parado stop()
        self._allowed = True  # lo que dice `when` (True si no hay)
        self._when: Effect | None = None
        self.runs = 0
        self.skipped = 0
        self.last_duration: float | None = None
        self._scope = current_scope()
        if self._scope is not None:
            self._scope.add(self)
        self.__name__ = getattr(fn, "__name__", "temporizador")
        if self._scope is None:
            log.debug("temporizador %s creado fuera de un componente: no se detendrá solo", self.__name__)
        if when is not None:
            read = _reader(when)
            # El efecto queda en el mismo ámbito que el temporizador (se libera con él).
            self._when = Effect(lambda: self._set_allowed(bool(read())))
        self.start()

    @property
    def active(self) -> bool:
        """Reactivo: True mientras el temporizador está contando."""
        return self._active.value

    def start(self) -> None:
        """Arranca (o vuelve a arrancar desde cero) el temporizador. Con `when=`, empieza a
        contar cuando la condición se cumpla."""
        if self._scope is not None and self._scope.disposed:
            return
        self._wanted = True
        self._run_qt()

    restart = start

    def stop(self) -> None:
        self._wanted = False
        self._stop_qt()

    def _set_allowed(self, allowed: bool) -> None:
        with untracked():
            if allowed == self._allowed:
                return
            self._allowed = allowed
            if not allowed:
                self._stop_qt()
            elif self._wanted:
                self._run_qt()

    def _run_qt(self) -> None:
        if not self._allowed:
            self._stop_qt()
            return
        if self._qt is None:
            from PySide6.QtCore import QCoreApplication, Qt, QTimer

            if QCoreApplication.instance() is None:
                raise RuntimeError("los temporizadores necesitan la aplicación en marcha: créalos en el script de un componente o después de run()")
            self._qt = QTimer()
            self._qt.setSingleShot(not self.repeat)
            # Por debajo de 1 s, Qt usa un temporizador grueso (±5 %) que en un panel se nota.
            if self.ms < 1000:
                self._qt.setTimerType(Qt.TimerType.PreciseTimer)
            self._qt.timeout.connect(self._tick)
        self._qt.start(self.ms)
        self._active.value = True
        if self._scope is None:
            _unscoped.add(self)

    def _stop_qt(self) -> None:
        if self._qt is not None:
            self._qt.stop()
        self._active.value = False
        _unscoped.discard(self)

    def dispose(self) -> None:
        self.stop()
        if self._when is not None:
            self._when.dispose()
        if self._qt is not None:
            self._qt.deleteLater()
            self._qt = None

    def _tick(self) -> None:
        if not self.repeat:
            self._wanted = False
            self._active.value = False
            _unscoped.discard(self)
        if self._running is not None and not self._running.done():
            self.skipped += 1
            return  # la ejecución asíncrona anterior no ha terminado: se salta este tic
        self.runs += 1
        started = time.perf_counter()
        try:
            # En el ámbito del componente: lo que cree la función (otro timeout, un efecto,
            # la tarea de una función async) también se libera al desmontarlo.
            with self._scope.active() if self._scope is not None else nullcontext():
                with untracked(), batch():
                    result = self.fn()
                if inspect.isawaitable(result):
                    from .tasks import spawn

                    self._running = spawn(result)
                    self._running.add_done_callback(lambda _t: self._measure(started))
                    return
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe parar la app
            log.error("error en el temporizador %s: %s: %s", self.__name__, type(exc).__name__, exc, exc_info=exc)
        self._measure(started)

    def _measure(self, started: float) -> None:
        self.last_duration = time.perf_counter() - started

    def __call__(self) -> Any:
        """Ejecuta la función ahora (sin cambiar cuándo toca la siguiente vez)."""
        return self.fn()

    def __repr__(self) -> str:
        kind = "interval" if self.repeat else "timeout"
        if self._active.peek():
            status = "activo"
        elif self._wanted and not self._allowed:
            status = "en espera de when"
        else:
            status = "parado"
        extra = f", {self.runs} ejecuciones" if self.runs else ""
        if self.skipped:
            extra += f", {self.skipped} saltados"
        if self.last_duration is not None:
            extra += f", última {self.last_duration * 1000:.1f} ms"
        return f"{kind}({self.ms} ms, {self.__name__}, {status}{extra})"


def _reader(when: When) -> Callable[[], Any]:
    if hasattr(when, "value"):  # State, Computed, Prop
        return lambda: when.value
    if callable(when):
        return when
    raise TypeError(f"when= espera un state, un computed o una función, no {type(when).__name__}")


@overload
def interval(ms: float, *, when: When = None) -> Callable[[Fn], Timer]: ...
@overload
def interval(ms: float, fn: Fn, *, when: When = None) -> Timer: ...
def interval(ms: float, fn: Fn | None = None, *, when: When = None) -> Any:
    """Llama a `fn` cada `ms` milisegundos (con `when=`, solo mientras se cumpla). También como
    decorador: `@interval(250)`."""
    if fn is None:
        return lambda f: Timer(ms, f, repeat=True, when=when)
    return Timer(ms, fn, repeat=True, when=when)


@overload
def timeout(ms: float, *, when: When = None) -> Callable[[Fn], Timer]: ...
@overload
def timeout(ms: float, fn: Fn, *, when: When = None) -> Timer: ...
def timeout(ms: float, fn: Fn | None = None, *, when: When = None) -> Any:
    """Llama a `fn` una vez, pasados `ms` milisegundos. También como decorador."""
    if fn is None:
        return lambda f: Timer(ms, f, repeat=False, when=when)
    return Timer(ms, fn, repeat=False, when=when)
