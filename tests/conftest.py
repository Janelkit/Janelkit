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
    """Monta componentes desde código fuente (o un archivo) y los desmonta al terminar la prueba."""
    from fluxui.compiler import compile_file, compile_source

    mounted = []

    def _mount(source, file: str = "App.flux"):
        compiled = compile_file(source) if hasattr(source, "read_text") else compile_source(source, file)
        m = flux_app.mount(compiled)
        flux_app.qt_app.processEvents()
        mounted.append(m)
        return m

    yield _mount
    for m in mounted:
        if m in flux_app.mounted:
            flux_app.unmount(m)
    flux_app.qt_app.processEvents()


@pytest.fixture(autouse=True, scope="session")
def _example_data(tmp_path_factory):
    """Los ejemplos que guardan datos (examples/compra) escriben en una carpeta temporal, no en $HOME."""
    os.environ["COMPRA_FILE"] = str(tmp_path_factory.mktemp("datos") / "lista-compra.json")
    yield


@pytest.fixture(autouse=True)
def _reset_theme():
    from fluxui import theme

    yield
    theme.reset()
    from fluxui import i18n

    i18n.reset()


# -- recorrer la vista ---------------------------------------------------------------
def visual_items(mounted):
    """Todos los elementos visuales de la vista en orden de árbol (incluidos los de Repeater)."""
    root = mounted.root
    start = root.contentItem() if hasattr(root, "contentItem") else root
    out = []

    def walk(item):
        for child in item.childItems():
            out.append(child)
            walk(child)

    walk(start)
    return out


def click(item) -> None:
    """Pulsa un botón como el usuario (también en Qt < 6.8, sin click() invocable)."""
    from fluxui.inspect import press

    press(item)


def find(mounted, name: str):
    for item in visual_items(mounted):
        if item.objectName() == name:
            return item
    raise AssertionError(f"no se encontró id={name}")


def find_all(mounted, name: str):
    return [i for i in visual_items(mounted) if i.objectName() == name]


def texts(mounted):
    """Textos visibles de los elementos <Text> (FxText es un Label), en orden."""
    return [i.property("text") for i in visual_items(mounted) if i.inherits("QQuickLabel") and i.isVisible()]
