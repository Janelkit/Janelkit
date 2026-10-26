import os

# Las pruebas de integración usan Qt sin mostrar ventanas.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def flux_app():
    from fluxui.qt_backend.application import Application

    return Application([])


@pytest.fixture
def mount(flux_app):
    """Monta componentes desde código fuente y los desmonta al terminar la prueba."""
    from fluxui.compiler import compile_source

    mounted = []

    def _mount(source: str, file: str = "App.flux"):
        m = flux_app.mount(compile_source(source, file))
        mounted.append(m)
        return m

    yield _mount
    for m in mounted:
        if m in flux_app.mounted:
            flux_app.unmount(m)
    flux_app.qt_app.processEvents()
