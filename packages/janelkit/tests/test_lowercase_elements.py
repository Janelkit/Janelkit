"""Elementos del núcleo en minúscula (0.2): los nombres de 0.1 compilan con un aviso (janel migrate: test_migrate.py)."""
import pytest

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
