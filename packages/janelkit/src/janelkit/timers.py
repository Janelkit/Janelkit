"""Temporizadores ligados al componente.

    from janelkit import interval, timeout

    @interval(250)                     # cada 250 ms mientras exista el componente
    def muestrear():
        cpu.value = leer_cpu()

    ocultar = timeout(3000, lambda: aviso.set(""))   # una vez, a los 3 s
    ocultar.restart()                  # vuelve a contar desde cero (p. ej. "escribiendo…")

- Creados en el script de un componente (o en algo que se ejecuta dentro de
  él, como `on_mount`), se detienen solos al desmontarlo.
- Cada ejecución agrupa sus cambios de estado (`batch`) y, si la función es
  `async def`, se lanza con `spawn` (y se cancela con el componente). Mientras
  una ejecución asíncrona no termina, los tics siguientes se saltan: un
  muestreo lento no se acumula.
- Un error en la función se registra en el logger `janelkit`; el temporizador sigue.
- `.active` es reactivo; `.stop()`, `.start()` y `.restart()` lo controlan.
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, overload

from .reactivity import State, batch, untracked
from .reactivity.effects import current_scope

log = logging.getLogger("janelkit")
Fn = Callable[[], Any]


class Timer:
    """Un temporizador de `interval` o `timeout`."""

    def __init__(self, ms: float, fn: Fn, repeat: bool):
        self.ms = max(0, int(ms))
        self.fn = fn
        self.repeat = repeat
        self._active = State(False)
        self._qt: Any = None
        self._running: Any = None  # tarea de la última ejecución, si fn es async
        self._scope = current_scope()
        if self._scope is not None:
            self._scope.add(self)
        self.__name__ = getattr(fn, "__name__", "temporizador")
        self.start()

    @property
    def active(self) -> bool:
        """Reactivo: True mientras el temporizador está contando."""
        return self._active.value

    def start(self) -> None:
        """Arranca (o vuelve a arrancar desde cero) el temporizador."""
        if self._scope is not None and self._scope.disposed:
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

    restart = start

    def stop(self) -> None:
        if self._qt is not None:
            self._qt.stop()
        self._active.value = False

    def dispose(self) -> None:
        self.stop()
        if self._qt is not None:
            self._qt.deleteLater()
            self._qt = None

    def _tick(self) -> None:
        if not self.repeat:
            self._active.value = False
        if self._running is not None and not self._running.done():
            return  # la ejecución asíncrona anterior no ha terminado: se salta este tic
        try:
            with untracked(), batch():
                result = self.fn()
            if inspect.isawaitable(result):
                from .tasks import spawn

                if self._scope is not None:
                    with self._scope.active():
                        self._running = spawn(result)
                else:
                    self._running = spawn(result)
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe parar la app
            log.error("error en el temporizador %s: %s: %s", self.__name__, type(exc).__name__, exc, exc_info=exc)

    def __call__(self) -> Any:
        """Ejecuta la función ahora (sin cambiar cuándo toca la siguiente vez)."""
        return self.fn()

    def __repr__(self) -> str:
        kind = "interval" if self.repeat else "timeout"
        return f"{kind}({self.ms} ms, {self.__name__}, {'activo' if self._active.peek() else 'parado'})"


@overload
def interval(ms: float) -> Callable[[Fn], Timer]: ...
@overload
def interval(ms: float, fn: Fn) -> Timer: ...
def interval(ms: float, fn: Fn | None = None) -> Any:
    """Llama a `fn` cada `ms` milisegundos. También como decorador: `@interval(250)`."""
    if fn is None:
        return lambda f: Timer(ms, f, repeat=True)
    return Timer(ms, fn, repeat=True)


@overload
def timeout(ms: float) -> Callable[[Fn], Timer]: ...
@overload
def timeout(ms: float, fn: Fn) -> Timer: ...
def timeout(ms: float, fn: Fn | None = None) -> Any:
    """Llama a `fn` una vez, pasados `ms` milisegundos. También como decorador."""
    if fn is None:
        return lambda f: Timer(ms, f, repeat=False)
    return Timer(ms, fn, repeat=False)
