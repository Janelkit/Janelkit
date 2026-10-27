"""Arranque de Qt, carga del QML generado, temas y API pública `run()`."""
from __future__ import annotations

import asyncio
import atexit
import itertools
import logging
import os
import sys
import time
import traceback
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import qasync
from PySide6.QtCore import QCoreApplication, QEvent, QFileSystemWatcher, QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlContext, QQmlEngine, QQmlError, QQmlPropertyMap
from PySide6.QtQuickControls2 import QQuickStyle
from shiboken6 import Shiboken

from ..compiler import CompiledComponent, compile_file
from ..compiler.qml_generator import BRIDGE_NAME
from ..diagnostics import Diagnostic, FluxError
from ..reactivity import Effect, Scope
from ..runtime.component import ComponentInstance, flush_mounts
from ..styling.compiler import THEME_OBJECT
from ..styling.theme import theme
from .events import router as event_router
from .polish import register_types

log = logging.getLogger("fluxui")

QML_DIR = Path(__file__).resolve().parent.parent / "qml"  # módulo interno `Flux`
DEFAULT_STYLE = "Basic"
EXIT_AFTER_ENV = "FLUXUI_EXIT_AFTER_MS"  # para pruebas de humo: cierra la app tras N ms
DEV_ENV = "FLUXUI_DEV"  # modo desarrollo: recarga al guardar (lo activa `flux dev`)

_memory_ids = itertools.count(1)


@dataclass
class MountedComponent:
    instance: ComponentInstance
    root: QObject
    context: QQmlContext
    qml_component: QQmlComponent  # debe vivir tanto como la vista
    compiled: CompiledComponent


class Application:
    """Una única `QGuiApplication` y un motor QML por proceso."""

    current: "Application | None" = None  # la última creada (la usan los diálogos)

    def __init__(self, argv: list[str] | None = None):
        existing = QGuiApplication.instance()
        if existing is not None and not isinstance(existing, QGuiApplication):
            raise RuntimeError("ya existe una QCoreApplication que no es QGuiApplication")
        if existing is None and not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
            QQuickStyle.setStyle(DEFAULT_STYLE)
        self.qt_app: QGuiApplication = existing or QGuiApplication(argv if argv is not None else sys.argv)
        # asyncio sobre el bucle de Qt: las corrutinas corren en el hilo de la interfaz.
        self.loop = qasync.QEventLoop(self.qt_app)
        asyncio.set_event_loop(self.loop)
        self._create_engine()
        self._by_url: dict[str, CompiledComponent] = {}
        self._delegates: dict[int, tuple[CompiledComponent, QQmlComponent]] = {}
        self._generation = 0  # cambia en cada recarga: URLs QML nuevas, sin cachés antiguas
        self.mounted: list[MountedComponent] = []
        self.dev_reloader: DevReloader | None = None  # modo desarrollo (flux dev)

        self._scope = Scope()
        with self._scope.active():
            Effect(self._sync_theme)
            Effect(self._sync_language)
        # Al salir del intérprete sin pasar por exec(), desmontar antes de que Python
        # recolecte los objetos en un orden arbitrario.
        atexit.register(self._at_exit)
        Application.current = self

    def main_window(self) -> QObject | None:
        """Ventana de la vista montada más reciente (padre de los diálogos), o None."""
        for mounted in reversed(self.mounted):
            if Shiboken.isValid(mounted.root) and mounted.root.isWindowType():
                return mounted.root
        return None

    def _create_engine(self) -> None:
        register_types()
        self.engine = QQmlEngine()
        self.engine.addImportPath(str(QML_DIR))
        self.engine.quit.connect(self.qt_app.quit)
        self.engine.warnings.connect(self._on_warnings)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.theme_map = QQmlPropertyMap(self.engine)
        self.engine.rootContext().setContextProperty(THEME_OBJECT, self.theme_map)
        # Idioma: dirección de escritura para las ventanas (fxi18n.rtl) y QLocale por defecto.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.i18n_map = QQmlPropertyMap(self.engine)
        self.engine.rootContext().setContextProperty("fxi18n", self.i18n_map)
        # Eventos de <flex> con propagación (events.py); uno para todas las ventanas.
        self.engine.rootContext().setContextProperty("fxevents", event_router)

    # -- tema ------------------------------------------------------------------
    def _sync_theme(self) -> None:
        tokens = theme.tokens
        if not tokens.get("font_family"):
            tokens["font_family"] = QGuiApplication.font().family()
        for key, value in tokens.items():
            if self.theme_map.value(key) != value:
                self.theme_map.insert(key, value)

    def _sync_language(self) -> None:
        from PySide6.QtCore import QLocale

        from ..i18n import i18n

        language = i18n.language
        self.i18n_map.insert("rtl", i18n.rtl)
        self.i18n_map.insert("language", language)
        QLocale.setDefault(QLocale(language.replace("-", "_")))

    def check_tokens(self, compiled: CompiledComponent) -> list[Diagnostic]:
        """Advertencias por `var(--x)` que no existe en el tema activo."""
        known = set(theme.tokens)
        out = []
        for comp in [compiled, *compiled.registry.values()]:
            for use in comp.ir.tokens:
                if use.name not in known:
                    out.append(
                        Diagnostic(
                            f"token de tema desconocido: --{use.name.replace('_', '-')}",
                            use.loc,
                            "defínelo con fluxui.theme.extend(...) o usa uno de los tokens documentados en docs/estilos.md",
                            severity="warning",
                            source=comp.ir.source,
                        )
                    )
        return list({(d.message, d.location): d for d in out}.values())

    # -- montaje ---------------------------------------------------------------
    def mount(
        self,
        compiled: CompiledComponent,
        *,
        props: dict[str, Any] | None = None,
        events: dict[str, Any] | None = None,
        parent: ComponentInstance | None = None,
        theme_name: str | None = None,
    ) -> MountedComponent:
        """Crea una instancia del componente y su vista. Lanza FluxError si Qt rechaza el QML.

        `props`/`events`/`parent` sirven para ventanas abiertas desde otro componente
        (`open_window`); `theme_name` fija un tema solo para esta vista.
        """
        component = QQmlComponent(self.engine)
        component.setData(compiled.qml.encode("utf-8"), self._url_for(compiled))
        if component.isError():
            raise self._qml_error(compiled, component.errors())

        instance = ComponentInstance(compiled, host=self, props=props, events=events, parent=parent)
        context = QQmlContext(self.engine.rootContext(), self.engine)
        context.setContextProperty(BRIDGE_NAME, instance.bridge)
        if theme_name is not None:
            context.setContextProperty(THEME_OBJECT, self._theme_map_for(theme_name, context, instance))
        root = component.create(context)
        if root is None:
            instance.dispose()
            context.deleteLater()
            raise self._qml_error(compiled, component.errors())
        mounted = MountedComponent(instance, root, context, component, compiled)
        self.mounted.append(mounted)
        if parent is None and root.isWindowType():
            # Al cerrar la ventana principal se cierran las secundarias que abrió (open_window).
            root.visibleChanged.connect(
                lambda visible, m=mounted: None if visible else QTimer.singleShot(0, lambda: self._close_children(m))
            )
        flush_mounts()
        return mounted

    def _close_children(self, main: MountedComponent) -> None:
        for other in list(self.mounted):
            node = other.instance.parent
            while node is not None and node is not main.instance:
                node = node.parent
            if other is not main and node is main.instance:
                self.unmount(other)

    def _theme_map_for(self, name: str, owner: QObject, instance: ComponentInstance) -> QQmlPropertyMap:
        """Tokens de un tema fijo para una vista, sincronizados mientras viva la instancia."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            tokens_map = QQmlPropertyMap(owner)

        def sync() -> None:
            tokens = theme.tokens_of(name)
            if not tokens.get("font_family"):
                tokens["font_family"] = QGuiApplication.font().family()
            for key, value in tokens.items():
                if tokens_map.value(key) != value:
                    tokens_map.insert(key, value)

        with instance.scope.active():
            Effect(sync)
        return tokens_map

    def delegate_for(self, compiled: CompiledComponent) -> QQmlComponent:
        """Componente QML de un hijo `.flux`, creado una vez por compilación."""
        entry = self._delegates.get(id(compiled))
        if entry is not None and entry[0] is compiled:
            return entry[1]
        component = QQmlComponent(self.engine)
        component.setData(compiled.qml.encode("utf-8"), self._url_for(compiled))
        if component.isError():
            raise self._qml_error(compiled, component.errors())
        self._delegates[id(compiled)] = (compiled, component)
        return component

    def fragment_delegate(self, compiled: CompiledComponent, template_id: str) -> QQmlComponent:
        """Componente QML del contenido de un slot escrito en `compiled`."""
        key = (id(compiled), template_id)
        entry = self._delegates.get(key)
        if entry is not None and entry[0] is compiled:
            return entry[1]
        doc = compiled.fragments[template_id]
        component = QQmlComponent(self.engine)
        component.setData(doc.qml.encode("utf-8"), self._url_for(compiled, doc, f".{template_id}"))
        if component.isError():
            raise self._qml_error(doc, component.errors())
        self._delegates[key] = (compiled, component)
        return component

    def unmount(self, mounted: MountedComponent) -> None:
        """Desmonta en orden: efectos, vista y por último el contexto con el puente.

        Si el puente desapareciera antes que la vista, QML reevaluaría sus
        bindings contra un `fx` nulo.
        """
        mounted.instance.dispose()
        # Se borran a través de Qt (deleteLater + procesar ya los borrados pendientes),
        # no con Shiboken.delete: borrar una ventana desde Python deja a PySide6 6.6
        # en un estado que termina en un fallo de acceso al salir del intérprete.
        if Shiboken.isValid(mounted.root):
            mounted.root.setVisible(False)
            mounted.root.deleteLater()
        if Shiboken.isValid(mounted.context):
            mounted.context.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if mounted in self.mounted:
            self.mounted.remove(mounted)
        # Olvidar los componentes QML de hijos que ya no usa ninguna vista montada.
        live = {id(c) for m in self.mounted for c in [m.compiled, *m.compiled.registry.values()]}
        for key in [k for k in self._delegates if (k[0] if isinstance(k, tuple) else k) not in live]:
            del self._delegates[key]

    def close(self) -> None:
        for mounted in reversed(list(self.mounted)):
            self.unmount(mounted)

    def _at_exit(self) -> None:
        self.close()
        # El bucle de qasync se cierra ahora, con Qt todavía vivo: si lo cerrara el
        # recolector al final, Qt ya no existiría ("Signal source has been deleted").
        if not self.loop.is_running() and not self.loop.is_closed():
            try:
                self.loop.close()
            except RuntimeError:
                pass

    def exec(self) -> int:
        if ms := os.environ.get(EXIT_AFTER_ENV):
            QTimer.singleShot(int(ms), self.qt_app.quit)
        code = self.loop.run_forever()
        self.close()
        return code

    def process_events(self) -> None:
        """Procesa los eventos pendientes de Qt con el bucle de asyncio marcado como activo.

        Así los pasos de corrutinas que Qt ejecute ven `asyncio.get_running_loop()`,
        como dentro de `exec()`. No debe llamarse desde dentro de una corrutina.
        """
        if asyncio._get_running_loop() is not None:
            self.qt_app.processEvents()
            return
        asyncio.events._set_running_loop(self.loop)
        try:
            self.qt_app.processEvents()
        finally:
            asyncio.events._set_running_loop(None)

    def run_until(self, awaitable: Any, timeout: float = 5.0) -> Any:
        """Ejecuta el bucle hasta que termina `awaitable` (para pruebas y scripts)."""
        return self.loop.run_until_complete(asyncio.wait_for(awaitable, timeout))

    # -- errores de Qt mapeados al .flux -------------------------------------
    def _url_for(self, compiled: CompiledComponent, doc: object = None, part: str = "") -> QUrl:
        path = Path(compiled.file)
        suffix = part + (f".r{self._generation}.qml" if self._generation else ".qml")
        if path.is_absolute() or path.exists():
            local = str(path.resolve()) + suffix
        else:
            local = str(Path.cwd() / f"__flux_memoria_{next(_memory_ids)}.qml")
        url = QUrl.fromLocalFile(local)
        self._by_url[url.toString()] = doc if doc is not None else compiled
        return url

    def _diagnostic(self, compiled: CompiledComponent, error: QQmlError, severity: str) -> Diagnostic:
        loc = compiled.flux_location(error.line()) if error.line() > 0 else None
        qml_lines = compiled.qml.splitlines()
        hint = None
        if 0 < error.line() <= len(qml_lines):
            hint = f"QML generado (línea {error.line()}): {qml_lines[error.line() - 1].strip()}"
        return Diagnostic(error.description(), loc, hint, severity=severity, source=compiled.source)

    def _qml_error(self, compiled: CompiledComponent, errors: list[QQmlError]) -> FluxError:
        diags = []
        for e in errors:
            owner = self._by_url.get(e.url().toString(), compiled)
            d = self._diagnostic(owner, e, "error")
            d.message = f"Qt rechazó el QML generado: {d.message}"
            diags.append(d)
        return FluxError(diags or [Diagnostic("Qt no pudo crear el componente", None)])

    def _on_warnings(self, qml_warnings: list[QQmlError]) -> None:
        for w in qml_warnings:
            compiled = self._by_url.get(w.url().toString())
            if compiled is None:
                log.warning(w.toString())
            else:
                log.warning(self._diagnostic(compiled, w, "warning").format())


class DevReloader:
    """Modo desarrollo: recompila y vuelve a montar la vista al guardar un `.flux`.

    Es una recarga completa (el estado se reinicia). Si el archivo tiene
    errores, se muestran en la consola y en una ventana de error, y la última
    versión correcta sigue abierta.
    """

    def __init__(self, app: Application, entry: Path, mounted: MountedComponent | None, files: list[str]):
        self.app = app
        self.entry = entry
        self.mounted = mounted
        self.watcher = QFileSystemWatcher()
        self.watcher.fileChanged.connect(self._schedule)
        self.watcher.directoryChanged.connect(self._schedule)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)  # agrupa las escrituras de un mismo guardado
        self.timer.timeout.connect(self.reload)
        self._error_window: QObject | None = None
        self._error_component: QQmlComponent | None = None
        self._snapshot: dict[str, bytes | None] = {}
        self.watch(files)

    def watch(self, files: list[str]) -> None:
        # Solo .flux: los .qml propios los vigila el supervisor de `flux dev`, que reinicia el proceso.
        paths = [str(Path(f).resolve()) for f in files if Path(f).is_file() and not f.endswith(".qml")]
        dirs = sorted({str(Path(p).parent) for p in paths})
        current = set(self.watcher.files()) | set(self.watcher.directories())
        missing = [p for p in [*paths, *dirs] if p not in current]
        if missing:
            self.watcher.addPaths(missing)
        self._snapshot = {p: _contents(p) for p in paths}

    def _schedule(self, *_: object) -> None:
        self.timer.start()

    def reload(self) -> None:
        # Los cambios de carpeta también avisan de archivos ajenos: recargar solo si cambió uno de la app.
        changed = [p for p, c in self._snapshot.items() if _contents(p) != c]
        if self.mounted is not None and not changed:
            return
        started = time.perf_counter()
        try:
            compiled = compile_file(self.entry)
        except FluxError as exc:
            self.watch(list(self._snapshot) + [str(self.entry)])
            self.show_error(exc.diagnostics)
            return
        for w in compiled.all_warnings + self.app.check_tokens(compiled):
            print(w.format(), file=sys.stderr)
        self.app._generation += 1
        geometry = None
        from ..runtime import component as runtime

        snapshot = runtime.HotReload(self.mounted.instance) if self.mounted is not None else None
        runtime.hot_reload = snapshot
        try:
            new = self.app.mount(compiled)
        except FluxError as exc:
            self.watch(compiled.files)
            self.show_error(exc.diagnostics)
            return
        except Exception:  # noqa: BLE001 - error en el <script>
            self.watch(compiled.files)
            self.show_error([Diagnostic(traceback.format_exc().rstrip())])
            return
        finally:
            runtime.hot_reload = None
        old, self.mounted = self.mounted, new
        if old is not None:
            if Shiboken.isValid(old.root) and hasattr(old.root, "geometry"):
                geometry = old.root.geometry()
            self.app.unmount(old)
        if geometry is not None and hasattr(new.root, "setGeometry"):
            new.root.setGeometry(geometry)
        self.hide_error()
        self.watch(compiled.files)
        elapsed = (time.perf_counter() - started) * 1000
        detail = ""
        if snapshot is not None:
            detail = f"; estado conservado en {snapshot.restored} componente(s)"
            if snapshot.reset_files:
                detail += f"; script cambiado, estado reiniciado: {', '.join(sorted(snapshot.reset_files))}"
        print(f"[flux dev] {Path(self.entry).name} recargado en {elapsed:.0f} ms{detail}", file=sys.stderr, flush=True)

    def show_error(self, diagnostics: list[Diagnostic]) -> None:
        text = "\n\n".join(d.format() for d in diagnostics)
        print(f"[flux dev] hay errores; se mantiene la última versión correcta:\n{text}", file=sys.stderr, flush=True)
        if self._error_window is None or not Shiboken.isValid(self._error_window):
            self._error_component = QQmlComponent(self.app.engine, QUrl.fromLocalFile(str(QML_DIR / "DevError.qml")))
            self._error_window = self._error_component.create(self.app.engine.rootContext())
            if self._error_window is None:
                log.warning("no se pudo abrir la ventana de errores: %s", self._error_component.errorString())
        if self._error_window is not None:
            self._error_window.setProperty("message", text)
            self._error_window.setProperty("visible", True)

    def hide_error(self) -> None:
        if self._error_window is not None and Shiboken.isValid(self._error_window):
            self._error_window.setProperty("visible", False)


def _contents(path: str) -> bytes | None:
    """Contenido actual (las marcas de tiempo no distinguen dos guardados muy seguidos)."""
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _print_diagnostics(diags: list[Diagnostic]) -> None:
    for d in diags:
        print(d.format(), file=sys.stderr)


def run(entry: str | os.PathLike[str], argv: list[str] | None = None) -> int:
    """Compila el componente raíz `entry` (p. ej. src/App.flux), abre la ventana y ejecuta Qt.

    Devuelve el código de salida de la aplicación (1 si hubo errores de compilación).
    La carpeta del componente se añade a `sys.path` para que el script pueda
    importar módulos del proyecto (`from services.users import ...`) y se usa
    como raíz para importar componentes (`from components.Card import Card`).
    Con la variable de entorno FLUXUI_DEV=1 (la fija `flux dev`), la vista se
    recarga al guardar cualquier `.flux` de la aplicación.
    """
    path = Path(entry).resolve()
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    dev = os.environ.get(DEV_ENV) == "1"

    compiled: CompiledComponent | None = None
    try:
        compiled = compile_file(path)
    except FluxError as exc:
        _print_diagnostics(exc.diagnostics)
        if not dev:
            return 1

    app = Application(argv)
    mounted = None
    if compiled is not None:
        _print_diagnostics(compiled.all_warnings + app.check_tokens(compiled))
        try:
            mounted = app.mount(compiled)
        except FluxError as exc:
            _print_diagnostics(exc.diagnostics)
            if not dev:
                return 1
        except Exception:  # noqa: BLE001 - error en el <script> del usuario
            traceback.print_exc()
            if not dev:
                return 1

    if dev:
        reloader = DevReloader(app, path, mounted, compiled.files if compiled else [str(path)])
        if mounted is None:
            reloader.show_error([Diagnostic("la aplicación no pudo arrancar; corrige el error y guarda el archivo")])
        print(f"[flux dev] observando cambios en {path.parent}", file=sys.stderr, flush=True)
        app.dev_reloader = reloader  # mantener vivo
    return app.exec()
