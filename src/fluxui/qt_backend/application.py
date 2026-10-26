"""Arranque de Qt, carga del QML generado y API pública `run()`."""
from __future__ import annotations

import atexit
import itertools
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlContext, QQmlEngine, QQmlError
from PySide6.QtQuickControls2 import QQuickStyle
from shiboken6 import Shiboken

from ..compiler import CompiledComponent, compile_file
from ..compiler.qml_generator import BRIDGE_NAME
from ..diagnostics import Diagnostic, FluxError
from ..runtime.component import ComponentInstance

log = logging.getLogger("fluxui")

DEFAULT_STYLE = "Fusion"
EXIT_AFTER_ENV = "FLUXUI_EXIT_AFTER_MS"  # para pruebas de humo: cierra la app tras N ms

_memory_ids = itertools.count(1)


@dataclass
class MountedComponent:
    instance: ComponentInstance
    root: QObject
    context: QQmlContext
    qml_component: QQmlComponent  # debe vivir tanto como la vista


class Application:
    """Una única `QGuiApplication` y un motor QML por proceso."""

    def __init__(self, argv: list[str] | None = None):
        existing = QGuiApplication.instance()
        if existing is not None and not isinstance(existing, QGuiApplication):
            raise RuntimeError("ya existe una QCoreApplication que no es QGuiApplication")
        if existing is None and not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
            QQuickStyle.setStyle(DEFAULT_STYLE)
        self.qt_app: QGuiApplication = existing or QGuiApplication(argv if argv is not None else sys.argv)
        self.engine = QQmlEngine()
        self.engine.quit.connect(self.qt_app.quit)
        self.engine.warnings.connect(self._on_warnings)
        self._by_url: dict[str, CompiledComponent] = {}
        self.mounted: list[MountedComponent] = []
        # Al salir del intérprete sin pasar por exec(), desmontar antes de que Python
        # recolecte los objetos en un orden arbitrario.
        atexit.register(self.close)

    def mount(self, compiled: CompiledComponent) -> MountedComponent:
        """Crea una instancia del componente y su vista. Lanza FluxError si Qt rechaza el QML."""
        url = self._url_for(compiled)
        component = QQmlComponent(self.engine)
        component.setData(compiled.qml.encode("utf-8"), url)
        if component.isError():
            raise self._qml_error(compiled, component.errors())

        instance = ComponentInstance(compiled)
        context = QQmlContext(self.engine.rootContext(), self.engine)
        context.setContextProperty(BRIDGE_NAME, instance.bridge)
        root = component.create(context)
        if root is None:
            instance.dispose()
            context.deleteLater()
            raise self._qml_error(compiled, component.errors())
        mounted = MountedComponent(instance, root, context, component)
        self.mounted.append(mounted)
        return mounted

    def unmount(self, mounted: MountedComponent) -> None:
        """Desmonta en orden: efectos, vista y por último el contexto con el puente.

        Si el puente desapareciera antes que la vista, QML reevaluaría sus
        bindings contra un `fx` nulo.
        """
        mounted.instance.dispose()
        if Shiboken.isValid(mounted.root):
            Shiboken.delete(mounted.root)
        if Shiboken.isValid(mounted.context):
            Shiboken.delete(mounted.context)
        self.mounted.remove(mounted)

    def close(self) -> None:
        for mounted in reversed(list(self.mounted)):
            self.unmount(mounted)

    def exec(self) -> int:
        if ms := os.environ.get(EXIT_AFTER_ENV):
            QTimer.singleShot(int(ms), self.qt_app.quit)
        code = self.qt_app.exec()
        self.close()
        return code

    # -- errores de Qt mapeados al .flux -------------------------------------
    def _url_for(self, compiled: CompiledComponent) -> QUrl:
        path = Path(compiled.file)
        if path.is_absolute() or path.exists():
            local = str(path.resolve()) + ".qml"
        else:
            local = str(Path.cwd() / f"__flux_memoria_{next(_memory_ids)}.qml")
        url = QUrl.fromLocalFile(local)
        self._by_url[url.toString()] = compiled
        return url

    def _diagnostic(self, compiled: CompiledComponent, error: QQmlError, severity: str) -> Diagnostic:
        loc = compiled.flux_location(error.line()) if error.line() > 0 else None
        qml_lines = compiled.qml.splitlines()
        hint = None
        if 0 < error.line() <= len(qml_lines):
            hint = f"QML generado (línea {error.line()}): {qml_lines[error.line() - 1].strip()}"
        return Diagnostic(error.description(), loc, hint, severity=severity, source=compiled.ir.source)

    def _qml_error(self, compiled: CompiledComponent, errors: list[QQmlError]) -> FluxError:
        diags = [self._diagnostic(compiled, e, "error") for e in errors]
        for d in diags:
            d.message = f"Qt rechazó el QML generado: {d.message}"
        return FluxError(diags or [Diagnostic("Qt no pudo crear el componente", None)])

    def _on_warnings(self, warnings: list[QQmlError]) -> None:
        for w in warnings:
            compiled = self._by_url.get(w.url().toString())
            if compiled is None:
                log.warning(w.toString())
            else:
                log.warning(self._diagnostic(compiled, w, "warning").format())


def _print_diagnostics(diags: list[Diagnostic]) -> None:
    for d in diags:
        print(d.format(), file=sys.stderr)


def run(entry: str | os.PathLike[str], argv: list[str] | None = None) -> int:
    """Compila el componente raíz `entry` (p. ej. src/App.flux), abre la ventana y ejecuta Qt.

    Devuelve el código de salida de la aplicación (1 si hubo errores de compilación).
    La carpeta del componente se añade a `sys.path` para que el script pueda
    importar módulos del proyecto (`from services.users import ...`).
    """
    path = Path(entry).resolve()
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    try:
        compiled = compile_file(path)
    except FluxError as exc:
        _print_diagnostics(exc.diagnostics)
        return 1
    _print_diagnostics(compiled.warnings)

    app = Application(argv)
    try:
        app.mount(compiled)
    except FluxError as exc:
        _print_diagnostics(exc.diagnostics)
        return 1
    except Exception:  # noqa: BLE001 - error en el <script> del usuario
        traceback.print_exc()
        return 1
    return app.exec()
