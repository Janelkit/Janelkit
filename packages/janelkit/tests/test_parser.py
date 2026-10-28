import pytest

from janelkit.compiler.ast_nodes import EachBlock, Element, Expression, IfBlock, Interpolation, Text, dump
from janelkit.compiler.sfc_parser import parse_sfc
from janelkit.diagnostics import JanelError

APP = """<script lang="python">
from janelkit import state
count = state(0)
</script>

<Window title="Mi app" width={640}>
  <Column class="page">
    <Text>Hola</Text>
    <Button on:click={increment}>Clicks: {count}</Button>
  </Column>
</Window>

<style>
.page { padding: 24px; }
</style>
"""


def parse_error(source: str) -> JanelError:
    with pytest.raises(JanelError) as info:
        parse_sfc(source, "App.janel")
    return info.value


# -- secciones -----------------------------------------------------------------


def test_extracts_sections_with_locations():
    sfc = parse_sfc(APP, "App.janel")
    assert sfc.script is not None and "count = state(0)" in sfc.script.content
    assert sfc.script.loc.line == 1
    assert sfc.style is not None and ".page" in sfc.style.content
    assert sfc.style.loc.line == 13
    assert len(sfc.root_elements) == 1


def test_template_keeps_original_line_numbers():
    sfc = parse_sfc(APP, "App.janel")
    window = sfc.root_elements[0]
    assert isinstance(window, Element) and window.tag == "Window"
    assert (window.loc.line, window.loc.column) == (6, 1)
    column = [c for c in window.children if isinstance(c, Element)][0]
    assert (column.loc.line, column.loc.column) == (7, 3)
    button = [c for c in column.children if isinstance(c, Element)][1]
    assert button.loc.line == 9
    assert button.attribute("on:click").loc.column == 13


def test_crlf_is_normalized():
    sfc = parse_sfc(APP.replace("\n", "\r\n"), "App.janel")
    assert sfc.root_elements[0].loc.line == 6


def test_unclosed_script_reports_opening_tag():
    err = parse_error("<script>\nx = 1\n<Window />")
    assert "no está cerrada" in err.first.message
    assert err.first.location.line == 1


def test_duplicate_script_is_an_error():
    err = parse_error("<script>a=1</script>\n<script>b=2</script>\n<Window />")
    assert err.first.location.line == 2


def test_non_python_script_is_rejected():
    err = parse_error('<script lang="js">x</script><Window />')
    assert "no soportado" in err.first.message


def test_script_inside_comment_is_ignored():
    sfc = parse_sfc("<!-- <script> -->\n<Window />", "App.janel")
    assert sfc.script is None


# -- plantilla -----------------------------------------------------------------


def test_attributes_literal_expression_boolean_and_shorthand():
    sfc = parse_sfc('<Button text="Hola" width={1 + 2} flat {enabled} on:click={go} />', "App.janel")
    attrs = {a.name: a.value for a in sfc.root_elements[0].attributes}
    assert attrs["text"] == "Hola"
    assert isinstance(attrs["width"], Expression) and attrs["width"].code == "1 + 2"
    assert attrs["flat"] is True
    assert isinstance(attrs["enabled"], Expression) and attrs["enabled"].code == "enabled"
    assert attrs["on:click"].code == "go"


def test_expressions_may_contain_braces_inside_strings_and_dicts():
    sfc = parse_sfc('<Text>{ {"a": "}"}["a"] }</Text>', "App.janel")
    interp = sfc.root_elements[0].children[0]
    assert isinstance(interp, Interpolation)
    assert interp.expression.code.strip() == '{"a": "}"}["a"]'


def test_mixed_text_and_interpolations():
    sfc = parse_sfc("<Button>Clicks: {count}!</Button>", "App.janel")
    kinds = [type(c) for c in sfc.root_elements[0].children]
    assert kinds == [Text, Interpolation, Text]


def test_if_else_blocks():
    sfc = parse_sfc(
        "<Column>\n{#if a}\n<Text>A</Text>\n{:else if b}\n<Text>B</Text>\n{:else}\n<Text>C</Text>\n{/if}\n</Column>",
        "App.janel",
    )
    block = [c for c in sfc.root_elements[0].children if isinstance(c, IfBlock)][0]
    assert [b.condition.code if b.condition else None for b in block.branches] == ["a", "b", None]
    assert all(any(isinstance(n, Element) for n in b.children) for b in block.branches)


def test_each_block_with_index_and_key():
    sfc = parse_sfc("<Column>{#each items as item, i (item.id)}<Text>{item}</Text>{/each}</Column>", "App.janel")
    block = sfc.root_elements[0].children[0]
    assert isinstance(block, EachBlock)
    assert (block.iterable.code, block.item, block.index, block.key.code) == ("items", "item", "i", "item.id")


def test_comments_are_skipped():
    sfc = parse_sfc("<Column><!-- <Nope> --><Text /></Column>", "App.janel")
    assert [c.tag for c in sfc.root_elements[0].children if isinstance(c, Element)] == ["Text"]


def test_dump_lists_nodes_with_positions():
    out = dump(parse_sfc(APP, "App.janel"))
    assert "<Window title=\"Mi app\" width={640}> @6:1" in out
    assert "{count} @9:" in out


# -- errores ---------------------------------------------------------------------


def test_mismatched_closing_tag():
    err = parse_error("<Window>\n  <Column>\n</Window>")
    d = err.first
    assert "se esperaba </Column>" in d.message
    assert (d.location.line, d.location.column) == (3, 1)
    assert "línea 2" in d.hint


def test_unclosed_element_points_to_opening_tag():
    err = parse_error("<Window>\n  <Column>\n    <Text />\n")
    assert "<Window> no está cerrado" in err.first.message or "<Column> no está cerrado" in err.first.message
    assert err.first.location.line in (1, 2)


def test_invalid_expression_location():
    err = parse_error("<Window>\n  <Text>{count +}</Text>\n</Window>")
    d = err.first
    assert "expresión Python no válida" in d.message
    assert d.location.line == 2
    assert d.location.column >= 10


def test_statements_are_not_expressions():
    err = parse_error("<Window>\n  {#if x = 3}\n  {/if}\n</Window>")
    assert err.first.location.line == 2


def test_empty_expression():
    err = parse_error("<Text>{ }</Text>")
    assert "vacía" in err.first.message


def test_unclosed_if_block():
    err = parse_error("<Window>\n{#if x}\n<Text/>\n</Window>")
    assert "antes de cerrar el bloque {#if}" in err.first.message
    assert err.first.location.line == 4


def test_block_closed_inside_element():
    err = parse_error("<Column>\n{#if x}\n<Row>\n{/if}\n</Row>\n</Column>")
    assert "dentro de <Row>" in err.first.message
    assert err.first.location.line == 4


def test_unknown_block():
    err = parse_error("<Column>{#for x}{/for}</Column>")
    assert "bloque desconocido" in err.first.message


def test_duplicate_attribute():
    err = parse_error('<Text a="1" a="2" />')
    assert "duplicado" in err.first.message


def test_diagnostic_format_shows_source_line_and_caret():
    err = parse_error("<Window>\n  <Column>\n</Window>")
    text = str(err)
    assert text.startswith("App.janel:3:1: error:")
    assert "   3 | </Window>" in text
    assert "^" in text
