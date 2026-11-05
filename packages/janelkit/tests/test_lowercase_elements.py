"""Elementos del núcleo en minúscula (0.2): los nombres de 0.1 compilan con un aviso y `janel migrate` los cambia."""
import pytest

from janelkit.cli.main import main
from janelkit.cli.migrate import migrate_janel, migrate_python
from janelkit.compiler import FORMAT_VERSION, compile_file, compile_source
from janelkit.diagnostics import JanelError
from janelkit.inspect import mount


def warnings_of(source: str) -> list[str]:
    return [w.message for w in compile_source(source).warnings]


def test_old_names_compile_like_the_new_ones_with_a_warning():
    old = compile_source('<Window title="x"><Column><Text>hola</Text><Button>ok</Button></Column></Window>')
    new = compile_source('<window title="x"><column><text>hola</text><button>ok</button></column></window>')
    assert old.qml == new.qml
    assert [w.message for w in old.warnings] == [
        "<Window> ahora se escribe <window>", "<Column> ahora se escribe <column>",
        "<Text> ahora se escribe <text>", "<Button> ahora se escribe <button>",
    ]  # fmt: skip
    assert "janel migrate" in old.warnings[0].hint
    assert new.warnings == []


def test_old_type_selectors_still_apply_with_a_warning():
    source = '<column><text class="t">hola</text></column>\n<style>\nText { color: #123456; }\n.t:hover, Column > Text.t { font-size: 20px; }\n</style>'
    c = compile_source(source)
    assert 'jkColor: "#123456"' in c.qml
    assert [(w.message, w.location.line, w.location.column) for w in c.warnings] == [
        ("el selector 'Text' ahora es 'text'", 3, 1),
        ("el selector 'Column' ahora es 'column'", 4, 11),
        ("el selector 'Text' ahora es 'text'", 4, 20),
    ]


def test_an_imported_component_keeps_its_capitalised_name(tmp_path):
    (tmp_path / "Button.janel").write_text('<flex class="b"><text>propio</text></flex>', encoding="utf-8")
    (tmp_path / "App.janel").write_text(
        "<script>\nfrom Button import Button\n</script>\n<window><Button /><button>nativo</button></window>\n"
        "<style>\nButton { padding: 4px; }\n</style>",
        encoding="utf-8",
    )
    c = compile_file(tmp_path / "App.janel")
    assert c.all_warnings == []
    assert "JkButton" in c.qml  # el <button> del núcleo


def test_capitalised_core_names_without_legacy_meaning_point_to_lowercase():
    with pytest.raises(JanelError) as exc:
        compile_source("<window><Textfield /></window>")
    assert "van en minúscula: <textfield>" in exc.value.first.hint
    with pytest.raises(JanelError) as exc:
        compile_source("<window><Colum /></window>")
    assert "<column>" in exc.value.first.hint and "impórtalo" in exc.value.first.hint
    with pytest.raises(JanelError) as exc:
        compile_source("<window><txt /></window>")
    assert exc.value.first.message == "elemento desconocido <txt>" and "<text>" in exc.value.first.hint


def test_the_format_version_counts_the_02_changes():
    assert FORMAT_VERSION == 2


def test_inspect_still_finds_by_the_old_name_with_a_deprecation_warning(tmp_path):
    (tmp_path / "App.janel").write_text("<window><button>Hola</button></window>", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        assert app.find("button").text == "Hola"
        with pytest.warns(DeprecationWarning, match='find\\("button"\\)'):
            assert app.find("Button").text == "Hola"


# -- janel migrate -------------------------------------------------------------------

JANEL_01 = """<script>
from components.Tarjeta import Tarjeta
from components.Text import Text
from janelkit import History, state
</script>
<Window title="x">
  <Column class="raiz">
    <Text>propio</Text>
    <Tarjeta><Button on:click={n += 1}>+</Button></Tarjeta>
    <TextField bind:value={n} />
    <Slot />
  </Column>
</Window>
<style>
Column > Button:hover, .Text, Text { color: red; }
/* Button en un comentario */
.raiz { font-family: Text; }
</style>
"""


def test_migrate_janel_renames_tags_and_selectors_but_not_imported_components():
    new, notes = migrate_janel(JANEL_01)
    assert "<window title" in new and "</window>" in new and "<column class" in new and "</column>" in new
    assert "<Text>propio</Text>" in new  # es un componente importado
    assert "<button on:click={n += 1}>+</button>" in new and "<textfield bind" in new and "<slot />" in new
    assert "column > button:hover, .Text, Text { color: red; }" in new  # Text es el componente
    assert "/* Button en un comentario */" in new and "font-family: Text;" in new
    assert "from components.Text import Text" in new  # el script no se toca
    assert any("History se quitó" in n for n in notes)
    assert migrate_janel(new) == (new, notes)  # aplicarlo dos veces no cambia nada


def test_migrate_python_updates_templates_and_find_in_tests():
    src = 'SRC = "<Column><Text>a</Text></Column>\\n<style>Text { color: red; }</style>"\nel = app.find("Button")\napp.find_all(\'Text\', text="a")\n'
    new, notes = migrate_python(src)
    assert new == 'SRC = "<column><text>a</text></column>\\n<style>text { color: red; }</style>"\nel = app.find("button")\napp.find_all(\'text\', text="a")\n'
    assert notes == []


def test_janel_migrate_shows_a_diff_and_writes_only_with_write(tmp_path, capsys):
    app = tmp_path / "src" / "App.janel"
    app.parent.mkdir()
    app.write_text("<Window><Text>hola</Text></Window>\n", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "Otro.janel").write_text("<Text>no</Text>", encoding="utf-8")
    assert main(["migrate", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "-<Window><Text>hola</Text></Window>" in out and "+<window><text>hola</text></window>" in out
    assert "1 de 1 archivo(s) cambiarían" in out
    assert app.read_text(encoding="utf-8") == "<Window><Text>hola</Text></Window>\n"
    assert main(["migrate", str(tmp_path), "--write"]) == 0
    assert app.read_text(encoding="utf-8") == "<window><text>hola</text></window>\n"
    assert (tmp_path / ".venv" / "lib" / "Otro.janel").read_text(encoding="utf-8") == "<Text>no</Text>"
    assert compile_file(app).warnings == []


def test_migrate_moves_the_navigation_imports_to_janelkit_router():
    src = """<script>
from janelkit import state, pages, navigation as nav_de  # navegación
from Inicio import Inicio
nav = pages(Inicio)
</script>
<Column><Pages stack={nav} /></Column>
"""
    new, _ = migrate_janel(src)
    assert "from janelkit import state\nfrom janelkit_router import pages, navigation as nav_de, Pages  # navegación\n" in new
    assert "<column><Pages stack={nav} /></column>" in new
    assert migrate_janel(new)[0] == new
    only, _ = migrate_janel("<script>\nfrom janelkit import sections\ns = sections()\n</script>\n<Sections of={s} />\n")
    assert "\nfrom janelkit_router import sections, Sections\n" in only and "from janelkit import" not in only
    py, _ = migrate_python("from janelkit import PageStack, Sections\n")
    assert py == "from janelkit_router import PageStack, SectionSet\n"


def test_migrate_moves_persisted_to_janelkit_store():
    py, _ = migrate_python("from janelkit import state, persisted, pages\n")
    assert py == "from janelkit import state\nfrom janelkit_store import persisted\nfrom janelkit_router import pages\n"
