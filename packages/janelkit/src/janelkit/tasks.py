"""Trabajo asíncrono y en segundo plano.

Todo el código de la interfaz corre en el hilo de Qt. JanelKit integra el bucle
de `asyncio` con el de Qt (con `qasync`), así que las corrutinas se ejecutan
en ese mismo hilo y pueden modificar el estado directamente tras cada `await`:

    from janelkit import state, task, background

    async def guardar():                     # on:click={guardar}
        estado.value = "guardando…"
        await api.guardar(datos.value)       # la ventana sigue respondiendo
        estado.value = "guardado"

    @task                                    # .loading, .error, .value reactivos
    async def usuarios(consulta):
        return await api.buscar(consulta)

    def leer(ruta):                          # trabajo que bloquea (CPU, disco, bibliotecas síncronas)
        return Path(ruta).read_text()

    async def abrir(ruta):
        texto.value = await background(leer, ruta)   # se ejecuta en otro hilo

Las tareas lanzadas desde un componente (manejadores, `spawn`, `task`) se
cancelan al desmontarlo, de modo que nunca actualizan una vista que ya no existe.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Generic, TypeVar

from .reactivity import State, batch
from .reactivity.effects import current_scope

T = TypeVar("T")
log = logging.getLogger("janelkit")

_executor: ThreadPoolExecutor | None = None


def _loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop_policy().get_event_loop()


def background(fn: Callable[..., T], *args: Any, **kwargs: Any) -> "asyncio.Future[T]":
    """Ejecuta `fn(*args, **kwargs)` en un hilo aparte. `await background(...)` devuelve su resultado.

    `fn` no debe tocar el estado ni la interfaz: devuelve un valor y el código
    que hace `await` lo aplica, ya de vuelta en el hilo de la interfaz.
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(thread_name_prefix="janelkit-background")
    return _loop().run_in_executor(_executor, functools.partial(fn, *args, **kwargs))


class _Cancel:
    """Entrada de un ámbito reactivo que cancela una tarea al liberarse."""

    def __init__(self, task: asyncio.Task):
        self.task = task

    def dispose(self) -> None:
        if not self.task.done():
            self.task.cancel()


def spawn(awaitable: Awaitable[T], on_error: Callable[[BaseException], Any] | None = None) -> "asyncio.Task[T]":
    """Lanza una corrutina sin esperarla.

    Si se llama dentro de un componente (su script, un manejador, `on_mount`),
    la tarea se cancela al desmontarlo. Los errores se registran en el logger
    `janelkit` (o se pasan a `on_error`).
    """

    async def runner() -> Any:
        try:
            return await awaitable
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe cerrar la app
            if on_error is not None:
                on_error(exc)
            else:
                log.error("error en una tarea asíncrona: %s: %s", type(exc).__name__, exc, exc_info=exc)
            return None

    task = _loop().create_task(runner())
    scope = current_scope()
    if scope is not None:
        handle = _Cancel(task)
        scope.add(handle)
        task.add_done_callback(lambda _t: scope.discard(handle))
    return task


class Task(Generic[T]):
    """Operación asíncrona con estado reactivo: `.loading`, `.error`, `.value`.

    `run(*args)` la (re)inicia cancelando la ejecución anterior; `cancel()` la
    detiene. Creada en el script de un componente, se cancela al desmontarlo.
    """

    def __init__(self, fn: Callable[..., Awaitable[T]]):
        self._fn = fn
        self._value: State[T | None] = State(None)
        self._error: State[BaseException | None] = State(None)
        self._loading = State(False)
        self._task: asyncio.Task | None = None
        self.__name__ = getattr(fn, "__name__", "task")
        scope = current_scope()
        if scope is not None:
            scope.add(self)

    @property
    def value(self) -> T | None:
        """Resultado de la última ejecución correcta (se conserva mientras se carga otra)."""
        return self._value.value

    @property
    def error(self) -> BaseException | None:
        """Excepción de la última ejecución, o `None`."""
        return self._error.value

    @property
    def loading(self) -> bool:
        return self._loading.value

    def run(self, *args: Any, **kwargs: Any) -> asyncio.Task:
        self.cancel()
        with batch():
            self._loading.value = True
            self._error.value = None
        self._task = _loop().create_task(self._execute(args, kwargs))
        return self._task

    __call__ = run

    async def _execute(self, args: tuple, kwargs: dict) -> None:
        try:
            result = self._fn(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - se expone en .error
            log.debug("la tarea %s falló", self.__name__, exc_info=exc)
            with batch():
                self._error.value = exc
                self._loading.value = False
            return
        with batch():
            self._value.value = result
            self._loading.value = False

    def cancel(self) -> None:
        """Detiene la ejecución en curso, si la hay."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
        self._loading.value = False

    def dispose(self) -> None:
        self.cancel()

    def __repr__(self) -> str:
        state = "cargando" if self._loading.peek() else "error" if self._error.peek() else "listo"
        return f"task {self.__name__} ({state})"


def task(fn: Callable[..., Awaitable[T]]) -> Task[T]:
    """Decorador: `@task async def cargar(...)` crea una `Task`."""
    return Task(fn)
