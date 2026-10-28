"""Navegación con pages(): push, pop, replace y reset; las páginas de abajo conservan su estado."""
import pytest
from conftest import texts

HOME = """<script>
from janelkit import state, inject
clicks = state(0)
session = inject("session", "-")
</script>
<Column><Text>Inicio {clicks} {session}</Text></Column>
"""

DETAIL = """<script>
from janelkit import prop, event, on_destroy
import tests_pages_log as log
item = prop()
done = event()
on_destroy(lambda: log.EVENTS.append(("destroy", item.value)))
</script>
<Column><Text>Detalle {item}</Text></Column>
"""

APP = """<script>
from janelkit import state, pages, provide
from screens.Home import Home
from screens.Detail import Detail
provide("session", "S1")
nav = pages(Home)
finished = state([])
</script>
<Window width={400} height={300}>
  <Column>
    <Text>{nav.current} ({nav.depth})</Text>
    <Pages id="pages" stack={nav} />
  </Column>
</Window>
"""


@pytest.fixture
def log(monkeypatch):
    import sys
    import types

    module = types.ModuleType("tests_pages_log")
    module.EVENTS = []
    monkeypatch.setitem(sys.modules, "tests_pages_log", module)
    return module.EVENTS


@pytest.fixture
def app(mount, tmp_path, log):
    files = {"App.janel": APP, "screens/Home.janel": HOME, "screens/Detail.janel": DETAIL}
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return mount(tmp_path / "App.janel")


def test_first_page_and_context(app):
    assert texts(app) == ["Home (1)", "Inicio 0 S1"]


def test_push_keeps_the_previous_page_alive_and_pop_returns_to_it(app, log):
    ns = app.instance.namespace
    nav, Detail = ns["nav"], ns["Detail"]
    home = nav.page
    home.namespace["clicks"].value = 3
    nav.push(Detail, item="a", on_done=ns["finished"].value.append)
    assert nav.current == "Detail" and nav.can_go_back
    assert texts(app) == ["Detail (2)", "Detalle a"]  # la de abajo no se ve
    nav.page.namespace["done"].emit("ok")
    assert ns["finished"].value == ["ok"]
    nav.pop()
    assert texts(app) == ["Home (1)", "Inicio 3 S1"]  # conserva su estado
    assert nav.page is home and not home.disposed
    assert log == [("destroy", "a")]  # la descartada se liberó


def test_replace_and_reset_release_discarded_pages(app, log):
    ns = app.instance.namespace
    nav, Home, Detail = ns["nav"], ns["Home"], ns["Detail"]
    nav.push(Detail, item="a")
    nav.replace(Detail, item="b")
    assert texts(app)[1] == "Detalle b" and log == [("destroy", "a")]
    nav.push(Detail, item="c")
    nav.reset(Home)
    assert nav.depth == 1 and texts(app) == ["Home (1)", "Inicio 0 S1"]
    assert sorted(log) == [("destroy", "a"), ("destroy", "b"), ("destroy", "c")]
    nav.pop()  # en la primera página no hace nada
    assert nav.depth == 1


def test_unmounting_the_app_releases_all_pages(app, janel_app, log):
    ns = app.instance.namespace
    ns["nav"].push(ns["Detail"], item="x")
    janel_app.unmount(app)
    assert log == [("destroy", "x")]


def test_wrong_props_are_rejected(app):
    ns = app.instance.namespace
    with pytest.raises(TypeError, match="Detail no declara la prop 'iten'"):
        ns["nav"].push(ns["Detail"], iten="a")
