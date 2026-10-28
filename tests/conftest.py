import os

# Las pruebas de integración usan Qt sin mostrar ventanas.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def janel_app():
    from janelkit.qt_backend.application import Application

    return Application([])


@pytest.fixture
def mount(janel_app):
    """Monta componentes desde código fuente (o un archivo) y los desmonta al terminar la prueba."""
    from janelkit.compiler import compile_file, compile_source

    mounted = []

    def _mount(source, file: str = "App.janel"):
        compiled = compile_file(source) if hasattr(source, "read_text") else compile_source(source, file)
        m = janel_app.mount(compiled)
        janel_app.qt_app.processEvents()
        mounted.append(m)
        return m

    yield _mount
    for m in mounted:
        if m in janel_app.mounted:
            janel_app.unmount(m)
    janel_app.qt_app.processEvents()


@pytest.fixture(autouse=True, scope="session")
def _example_data(tmp_path_factory):
    """Los ejemplos que guardan datos (examples/compra, persisted) escriben en una carpeta temporal, no en $HOME."""
    os.environ["COMPRA_FILE"] = str(tmp_path_factory.mktemp("datos") / "lista-compra.json")
    os.environ["JANELKIT_DATA_DIR"] = str(tmp_path_factory.mktemp("persisted"))
    yield


@pytest.fixture(autouse=True)
def _reset_theme():
    from janelkit import theme

    yield
    theme.reset()
    from janelkit import i18n

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
    from janelkit.inspect import press

    press(item)


def find(mounted, name: str):
    for item in visual_items(mounted):
        if item.objectName() == name:
            return item
    raise AssertionError(f"no se encontró id={name}")


def find_all(mounted, name: str):
    return [i for i in visual_items(mounted) if i.objectName() == name]


def texts(mounted):
    """Textos visibles de los elementos <Text> (JkText), en orden."""
    return [i.property("text") for i in visual_items(mounted) if _is_jk_text(i) and i.isVisible()]


def _is_jk_text(item) -> bool:
    """Un JkText, también la raíz de un componente cuyo elemento exterior es un <Text>."""
    if not item.inherits("QQuickText"):
        return False
    meta = item.metaObject()
    while meta is not None:
        if meta.className().startswith("JkText_"):
            return True
        meta = meta.superClass()
    return False
