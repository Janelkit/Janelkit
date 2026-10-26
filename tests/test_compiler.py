import pytest

from fluxui.compiler import compile_source
from fluxui.compiler.ir import ExprBinding, TextBinding, VisibilityBinding
from fluxui.diagnostics import FluxError


def compile_error(source: str) -> FluxError:
    with pytest.raises(FluxError) as info:
        compile_source(source, "App.flux")
    return info.value


def test_static_window_generates_qml_literals():
    qml = compile_source(
        '<Window title="Hola" width={800} height="600"><Column><Text>Uno</Text><Button>Dos</Button></Column></Window>'
    ).qml
    assert "import QtQuick\nimport QtQuick.Controls" in qml
    assert "ApplicationWindow {" in qml
    assert 'title: "Hola"' in qml
    assert "width: 800" in qml and "height: 600" in qml
    assert 'Label {\n            text: "Uno"' in qml
    assert 'text: "Dos"' in qml


def test_non_ascii_text_is_kept_readable():
    assert 'text: "Ñandú ¿qué?"' in compile_source("<Text>Ñandú ¿qué?</Text>").qml


def test_root_that_is_not_a_window_gets_wrapped():
    qml = compile_source("<Column><Text>x</Text></Column>").qml
    assert qml.index("ApplicationWindow") < qml.index("Column {")
    assert "visible: true" in qml


def test_window_with_several_children_gets_a_column():
    qml = compile_source("<Window><Text>a</Text><Text>b</Text></Window>").qml
    assert qml.index("Column {") < qml.index('text: "a"')


def test_text_whitespace_is_collapsed():
    qml = compile_source("<Text>\n   Hola\n   mundo   \n</Text>").qml
    assert 'text: "Hola mundo"' in qml


def test_dynamic_props_text_events_and_bind():
    c = compile_source(
        """<script>
from fluxui import state
n = state(0)
name = state("")
def inc(): pass
</script>
<Window>
  <Column>
    <Button on:click={inc} enabled={n < 3}>Clicks: {n}</Button>
    <TextField bind:value={name} on:input={inc} placeholder="Nombre" />
  </Column>
</Window>""",
        "App.flux",
    )
    kinds = [type(b) for b in c.ir.bindings]
    assert kinds == [ExprBinding, TextBinding, ExprBinding]
    assert "enabled: fx.b0" in c.qml
    assert "text: fx.b1" in c.qml
    assert 'onClicked: fx.invoke("h0", [])' in c.qml
    # bind:value escribe primero y luego llama al manejador on:input
    assert 'onTextEdited: { fx.write("b2", text); fx.invoke("h1", [text]) }' in c.qml
    assert [w.binding_id for w in c.ir.writes] == ["b2"]


def test_literal_expression_attributes_are_inlined():
    c = compile_source('<Window width={640} title={"Hola"}><Button flat={True} /></Window>')
    assert c.ir.bindings == []
    assert "width: 640" in c.qml and 'title: "Hola"' in c.qml and "flat: true" in c.qml


def test_if_else_creates_visibility_bindings():
    c = compile_source("<Column>{#if a}<Text>A</Text>{:else}texto {b}{/if}</Column>")
    vis = [b for b in c.ir.bindings if isinstance(b, VisibilityBinding)]
    assert [g.index for b in vis for g in b.guards] == [0, 1]
    assert c.qml.count("visible: fx.") == 2


def test_style_classes_and_element_selectors():
    c = compile_source(
        """<Column class="page"><Text class="title big">Hola</Text></Column>
<style>
Text { color: #333; }
.page { padding: 24px; gap: 12px; }
.title { font-size: 20px; font-weight: bold; }
.big { font-size: 32px; }
</style>"""
    )
    assert "padding: 24" in c.qml and "spacing: 12" in c.qml
    assert "font.pixelSize: 32" in c.qml  # la última regla de clase gana
    assert "font.weight: 700" in c.qml
    assert 'color: "#333"' in c.qml
    assert c.warnings == []


def test_explicit_attribute_overrides_style():
    c = compile_source('<Column class="p" gap={4}></Column>\n<style>.p { gap: 20px; }</style>')
    assert "spacing: 4" in c.qml and "spacing: 20" not in c.qml


def test_unsupported_style_property_is_a_warning_with_location():
    c = compile_source("<Text class=\"t\">x</Text>\n<style>\n.t { text-shadow: 1px; }\n</style>", "App.flux")
    assert len(c.warnings) == 1
    w = c.warnings[0]
    assert w.severity == "warning" and "text-shadow" in w.message
    assert (w.location.line, w.location.column) == (3, 6)


def test_style_not_applicable_to_element_is_a_warning():
    c = compile_source('<Column class="c" />\n<style>.c { font-size: 12px; }</style>')
    assert "no tiene efecto en Column" in c.warnings[0].message


def test_source_map_points_back_to_flux_lines():
    c = compile_source("<Window>\n  <Column>\n    <Button>Ok</Button>\n  </Column>\n</Window>", "App.flux")
    button_line = next(i for i, line in enumerate(c.qml.splitlines(), 1) if "Button {" in line)
    loc = c.flux_location(button_line + 1)
    assert (loc.line, loc.column) == (3, 5)


# -- errores de validación -------------------------------------------------------


def test_unknown_element():
    err = compile_error("<Window>\n  <Slider />\n</Window>")
    assert "elemento desconocido <Slider>" in err.first.message
    assert err.first.location.line == 2
    assert "Button" in err.first.hint


def test_unknown_property_lists_available_ones():
    err = compile_error('<Button colour="red" />')
    assert "propiedad desconocida 'colour'" in err.first.message
    assert "enabled" in err.first.hint


def test_unknown_event():
    err = compile_error("<Button on:press={go} />")
    assert "on:click" in err.first.hint


def test_event_needs_expression():
    err = compile_error('<Button on:click="go" />')
    assert "espera una función" in err.first.message


def test_bind_requires_state_name():
    err = compile_error("<TextField bind:value={a + b} />")
    assert "necesita el nombre de un state" in err.first.message


def test_bind_not_available():
    err = compile_error("<Button bind:text={x} />")
    assert "no está disponible" in err.first.message


def test_wrong_literal_type():
    err = compile_error('<Window width="ancho" />')
    assert "espera un número" in err.first.message


def test_multiple_roots():
    err = compile_error("<Window />\n<Window />")
    assert err.first.location.line == 2


def test_empty_template():
    err = compile_error("<script>x = 1</script>")
    assert "vacía" in err.first.message


def test_each_not_supported_yet():
    err = compile_error("<Column>{#each xs as x}<Text>{x}</Text>{/each}</Column>")
    assert "{#each} aún no está soportado" in err.first.message


def test_text_element_rejects_child_elements():
    err = compile_error("<Button><Text>x</Text></Button>")
    assert "solo admite texto" in err.first.message


def test_several_errors_are_reported_together():
    err = compile_error("<Window>\n  <Foo />\n  <Bar />\n</Window>")
    assert [d.location.line for d in err.diagnostics] == [2, 3]
