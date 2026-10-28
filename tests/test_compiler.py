from pathlib import Path

import pytest

from janelkit.compiler import compile_file, compile_source
from janelkit.compiler.ir import ComponentSlot, EachSlot, ExprBinding, IfSlot, TextBinding
from janelkit.diagnostics import JanelError


def compile_error(source: str) -> JanelError:
    with pytest.raises(JanelError) as info:
        compile_source(source, "App.janel")
    return info.value


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_static_window_generates_qml_literals():
    qml = compile_source(
        '<Window title="Hola" width={800} height="600"><Column><Text>Uno</Text><Button>Dos</Button></Column></Window>'
    ).qml
    assert "import QtQuick\nimport QtQuick.Controls\nimport QtQuick.Layouts\nimport Janel" in qml
    assert "JkWindow {" in qml
    assert 'title: "Hola"' in qml
    assert "width: 800" in qml and "height: 600" in qml
    assert 'JkText {\n            text: "Uno"' in qml
    assert 'text: "Dos"' in qml


def test_non_ascii_text_is_kept_readable():
    assert 'text: "Ñandú ¿qué?"' in compile_source("<Text>Ñandú ¿qué?</Text>").qml


def test_root_that_is_not_a_window_gets_wrapped_and_fills_it():
    qml = compile_source("<Column><Text>x</Text></Column>").qml
    assert qml.index("JkWindow") < qml.index("JkColumn {")
    assert "anchors.fill: parent" in qml


def test_window_with_several_children_gets_a_column():
    qml = compile_source("<Window><Text>a</Text><Text>b</Text></Window>").qml
    assert qml.index("JkColumn {") < qml.index('text: "a"')


def test_window_only_as_root():
    err = compile_error("<Column><Window /></Column>")
    assert "solo puede usarse como raíz" in err.first.message


def test_text_whitespace_is_collapsed():
    qml = compile_source("<Text>\n   Hola\n   mundo   \n</Text>").qml
    assert 'text: "Hola mundo"' in qml


def test_dynamic_props_text_events_and_bind():
    c = compile_source(
        """<script>
from janelkit import state
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
        "App.janel",
    )
    kinds = [type(b) for b in c.ir.template.bindings]
    assert kinds == [ExprBinding, TextBinding, ExprBinding]
    assert "enabled: jk.b0" in c.qml
    assert "text: jk.b1" in c.qml
    assert 'onClicked: jk.invoke("h0", [])' in c.qml
    # bind:value escribe primero y luego llama al manejador on:input
    assert 'onTextEdited: { jk.write("b2", text); jk.invoke("h1", [text]) }' in c.qml
    assert [w.binding_id for w in c.ir.template.writes] == ["b2"]


def test_literal_expression_attributes_are_inlined():
    c = compile_source('<Window width={640} title={"Hola"}><Button flat={True} /></Window>')
    assert c.ir.template.bindings == []
    assert "width: 640" in c.qml and 'title: "Hola"' in c.qml and "flat: true" in c.qml


def test_width_attribute_maps_to_layout_and_disables_fill():
    qml = compile_source("<Column><TextField width={200} flex={1} /></Column>").qml
    assert "Layout.preferredWidth: 200" in qml and "Layout.fillWidth: false" in qml
    assert "jkFlex: 1" in qml


# -- control de flujo ----------------------------------------------------------------

SCRIPT = """<script>
from janelkit import state
a = state(True)
b = state(1)
items = state([])
def remove(x): pass
</script>
"""


def test_if_else_creates_one_repeater_per_branch():
    c = compile_source(SCRIPT + "<Column>{#if a}<Text>A</Text>{:else if b}<Text>B</Text>{:else}texto {b}{/if}</Column>")
    (slot,) = c.ir.template.slots
    assert isinstance(slot, IfSlot)
    assert [br.condition.code if br.condition else None for br in slot.branches] == ["a", "b", None]
    assert c.qml.count("Repeater {") == 3
    assert "model: jk.m0" in c.qml and "delegate: JkText {" in c.qml
    # el texto de la rama {:else} pertenece al fragmento, no a la plantilla raíz
    assert c.ir.template.bindings == []
    assert isinstance(slot.branches[2].fragment.template.bindings[0], TextBinding)


def test_empty_if_branch_has_no_repeater():
    c = compile_source(SCRIPT + "<Column>{#if a}{:else}<Text>no</Text>{/if}</Column>")
    slot = c.ir.template.slots[0]
    assert slot.branches[0].model_id is None
    assert c.qml.count("Repeater {") == 1


def test_each_with_key_index_and_else():
    c = compile_source(
        SCRIPT
        + """<Column>
  {#each items as item, i (item["id"])}
    <Row><Text>{i}. {item["t"]}</Text><Button on:click={lambda: remove(item)}>x</Button></Row>
  {:else}
    <Text>Vacío</Text>
  {/each}
</Column>"""
    )
    (slot,) = c.ir.template.slots
    assert isinstance(slot, EachSlot)
    assert (slot.item, slot.index, slot.key.code) == ("item", "i", 'item["id"]')
    assert slot.empty_model_id is not None
    frag = slot.fragment
    assert frag.root.qml_type == "JkRow"
    assert [h.expression.code for h in frag.template.handlers] == ["lambda: remove(item)"]
    assert "delegate: JkRow {" in c.qml


def test_each_with_several_nodes_gets_an_implicit_container_matching_the_parent():
    c = compile_source(SCRIPT + "<Row>{#each items as x}<Text>{x}</Text><Text>-</Text>{/each}</Row>")
    root = c.ir.template.slots[0].fragment.root
    assert root.qml_type == "JkFlexRow" and len(root.children) == 2  # caja implícita: motor de <flex>
    assert "Jk.mainGap(parent)" in root.props["gap"].qml
    assert root.props["jkFlex"].qml == "fillMain ? 1 : 0"


def test_loop_variables_are_scoped_to_the_block():
    err = compile_error(SCRIPT + "<Column>{#each items as x}<Text>{x}</Text>{/each}<Text>{x}</Text></Column>")
    assert "'x' no está definido" in err.first.message


def test_bind_cannot_target_loop_variable():
    err = compile_error(SCRIPT + "<Column>{#each items as x}<TextField bind:value={x} />{/each}</Column>")
    assert "variable de {#each}" in err.first.message


# -- nombres -------------------------------------------------------------------------


def test_undefined_name_suggests_closest_with_exact_location():
    err = compile_error("<script>\ncount = 1\n</script>\n<Text>Total: {1 + cuont}</Text>")
    d = err.first
    assert d.message == "'cuont' no está definido"
    assert (d.location.line, d.location.column) == (4, 19)
    assert "count" in d.hint


def test_names_inside_lambdas_and_comprehensions_are_not_reported():
    compile_source(SCRIPT + "<Text>{', '.join(str(v) for v in items)} {(lambda z: z)(b)}</Text>")


def test_builtins_are_known():
    compile_source(SCRIPT + "<Text>{len(items)} {max(b, 2)}</Text>")


def test_star_import_disables_name_checks():
    compile_source("<script>\nfrom math import *\n</script>\n<Text>{pi}</Text>")


def test_script_syntax_error_is_reported_at_compile_time():
    err = compile_error("<script>\nx = (\n</script>\n<Text>a</Text>")
    assert "error de sintaxis en el script" in err.first.message
    assert err.first.location.line >= 2


# -- estilos -------------------------------------------------------------------------


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
    assert "padding: 24" in c.qml and "gap: 12" in c.qml
    assert "font.pixelSize: 32" in c.qml  # la última regla de clase gana
    assert "font.weight: 700" in c.qml
    assert 'jkColor: "#333"' in c.qml
    assert c.warnings == []


def test_box_styles_tokens_and_alignment():
    c = compile_source(
        """<Column class="card"><Button class="b">x</Button></Column>
<style>
.card { padding: 8px 16px; background: var(--surface); border: 1px solid var(--border);
        border-radius: var(--radius-lg); align-items: center; justify-content: end; }
.b { flex: 1; align-self: stretch; width: 100%; text-transform: uppercase; }
</style>"""
    )
    qml = c.qml
    for expected in (
        "topPadding: 8",
        "rightPadding: 16",
        "jkBackground: jktheme.surface",
        "jkBorderWidth: 1",
        "jkBorderColor: jktheme.border",
        "jkRadius: jktheme.radius_lg",
        'alignItems: "center"',
        'justifyContent: "end"',
        "jkFlex: 1",
        "jkSelfStretch: true",
        "Layout.fillWidth: true",
        "font.capitalization: Font.AllUppercase",
    ):
        assert expected in qml, expected
    assert [t.name for t in c.ir.tokens] == ["surface", "border", "radius_lg"]
    assert c.warnings == []


def test_row_align_items_is_passed_to_the_flex_engine():
    qml = compile_source('<Row class="r" />\n<style>.r { align-items: end; }</style>').qml
    assert 'alignItems: "end"' in qml


def test_explicit_attribute_overrides_style():
    c = compile_source('<Column class="p" gap={4}></Column>\n<style>.p { gap: 20px; }</style>')
    assert "gap: 4" in c.qml and "gap: 20" not in c.qml


def test_unsupported_style_property_is_a_warning_with_location():
    c = compile_source("<Text class=\"t\">x</Text>\n<style>\n.t { text-shadow: 1px; }\n</style>", "App.janel")
    assert len(c.warnings) == 1
    w = c.warnings[0]
    assert w.severity == "warning" and "text-shadow" in w.message
    assert (w.location.line, w.location.column) == (3, 6)


def test_style_not_applicable_to_element_is_a_warning():
    c = compile_source('<Scroll class="c" />\n<style>.c { font-size: 12px; }</style>')
    assert "no tiene efecto en <Scroll>" in c.warnings[0].message


def test_unsupported_style_values_are_warnings():
    c = compile_source('<Column class="c" />\n<style>.c { justify-content: middle; width: 50pc; }</style>')
    messages = " | ".join(w.message for w in c.warnings)
    assert "justify-content no soportado" in messages and "número" in messages


def test_source_map_points_back_to_janel_lines():
    c = compile_source("<Window>\n  <Column>\n    <Button>Ok</Button>\n  </Column>\n</Window>", "App.janel")
    button_line = next(i for i, line in enumerate(c.qml.splitlines(), 1) if "JkButton {" in line)
    loc = c.janel_location(button_line + 1)
    assert (loc.line, loc.column) == (3, 5)


# -- componentes -----------------------------------------------------------------------

CARD = """<script>
from janelkit import prop, event
title = prop()
compact = prop(False)
closed = event()
</script>
<Column><Text>{title}</Text></Column>
"""


def test_component_import_props_and_events(tmp_path):
    write(tmp_path, "components/Card.janel", CARD)
    app = write(
        tmp_path,
        "App.janel",
        """<script>
from janelkit import state
from components.Card import Card
name = state("x")
def on_close(): pass
</script>
<Column>
  <Card title={name} compact on:closed={on_close} />
  {#each [1, 2] as n (n)}
    <Card title={str(n)} />
  {/each}
</Column>""",
    )
    c = compile_file(app)
    slot = c.ir.template.slots[0]
    assert isinstance(slot, ComponentSlot)
    assert set(slot.use.props) == {"title", "compact"}
    assert list(slot.use.events) == ["closed"]
    each = c.ir.template.slots[1]
    assert each.fragment.component is not None and each.fragment.root is None
    assert "delegate: jk.m0.delegate" in c.qml
    child = c.component(str((tmp_path / "components" / "Card.janel").resolve()))
    assert child.ir.is_window is False and "JkWindow" not in child.qml
    assert "Card.janel" in " ".join(c.files)


def test_component_import_forms(tmp_path):
    write(tmp_path, "components/Card.janel", CARD)
    write(tmp_path, "pages/Home.janel", '<script>\nfrom ..components import Card\n</script>\n<Card title="a" />')
    app = write(tmp_path, "App.janel", "<script>\nfrom pages import Home\n</script>\n<Home />")
    c = compile_file(app)
    assert len(c.registry) == 3


def test_component_usage_errors(tmp_path):
    write(tmp_path, "components/Card.janel", CARD)
    app = write(
        tmp_path,
        "App.janel",
        """<script>
from components.Card import Card
</script>
<Column>
  <Card titel="x" on:open={print} bind:title={x} />
</Column>""",
    )
    with pytest.raises(JanelError) as info:
        compile_file(app)
    messages = [d.message for d in info.value.diagnostics]
    assert "<Card> no declara la prop 'titel'" in messages
    assert "<Card> no declara el evento 'open'" in messages
    assert "'bind:title' no se admite en componentes" in messages
    assert any("falta la prop obligatoria 'title'" in m for m in messages)
    titel = next(d for d in info.value.diagnostics if "titel" in d.message)
    assert "title" in titel.hint


def test_child_component_cannot_be_a_window(tmp_path):
    write(tmp_path, "W.janel", "<Window />")
    app = write(tmp_path, "App.janel", "<script>\nfrom W import W\n</script>\n<W />")
    with pytest.raises(JanelError) as info:
        compile_file(app)
    assert "no puede tener <Window> como raíz" in info.value.first.message
    assert info.value.first.location.file.endswith("W.janel")


def test_recursive_component(tmp_path):
    write(
        tmp_path,
        "Tree.janel",
        """<script>
from janelkit import prop
from Tree import Tree
node = prop()
</script>
<Column>
  <Text>{node["name"]}</Text>
  {#each node.get("children", []) as child (child["name"])}<Tree node={child} />{/each}
</Column>""",
    )
    app = write(tmp_path, "App.janel", '<script>\nfrom Tree import Tree\n</script>\n<Tree node={{"name": "r"}} />')
    c = compile_file(app)
    assert len(c.registry) == 2


def test_unknown_uppercase_tag_suggests_import():
    err = compile_error("<Column><TodoItem /></Column>")
    assert "from components.TodoItem import TodoItem" in err.first.hint


def test_prop_and_event_declarations_must_be_top_level():
    err = compile_error("<script>\nfrom janelkit import prop\ndef f():\n    x = prop(1)\n</script>\n<Text>a</Text>")
    assert "nivel superior" in err.first.message
    assert err.first.location.line == 4


def test_bind_cannot_target_a_prop():
    err = compile_error("<script>\nfrom janelkit import prop\nv = prop('')\n</script>\n<TextField bind:value={v} />")
    assert "solo lectura" in err.first.message


# -- errores de validación -------------------------------------------------------


def test_unknown_element():
    err = compile_error("<Window>\n  <Carousel />\n</Window>")
    assert "elemento desconocido <Carousel>" in err.first.message
    assert err.first.location.line == 2


def test_unknown_element_suggests_closest():
    err = compile_error("<Colum />")
    assert "<Column>" in err.first.hint


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
    err = compile_error("<TextField bind:value={prefs['tema']} />")
    assert "necesita el nombre de un state" in err.first.message


def test_bind_accepts_a_path_of_attributes():
    compiled = compile_source("""<script>
from services import prefs
</script>
<TextField bind:value={prefs.ajustes.tema} />""")
    assert compiled.all_warnings == []


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


def test_text_element_rejects_child_elements():
    err = compile_error("<Button><Text>x</Text></Button>")
    assert "solo admite texto" in err.first.message


def test_several_errors_are_reported_together():
    err = compile_error("<Window>\n  <Foo />\n  <Bar />\n</Window>")
    assert [d.location.line for d in err.diagnostics] == [2, 3]


# -- class: y {#key} --------------------------------------------------------------


def test_conditional_classes_generate_bindings_and_last_wins():
    c = compile_source(
        SCRIPT
        + """<Column class="card" class:sel={a} class:warn={b > 1}><Text>x</Text></Column>
<style>
.card { background: var(--surface); }
.sel { background: var(--primary); border-width: 2px; }
.warn { background: var(--danger); }
</style>"""
    )
    qml = c.qml
    assert "jkBackground: jktheme.surface" in qml
    # Un solo Binding por propiedad: gana la última clase activa.
    assert (
        "Binding on jkBackground { when: !!jk.b0 || !!jk.b1; value: !!jk.b1 ? jktheme.danger : jktheme.primary }"
        in qml
    )
    assert "Binding on jkBorderWidth { when: !!jk.b0; value: 2 }" in qml
    assert c.warnings == []


def test_conditional_class_shorthand_and_missing_rules():
    c = compile_source(SCRIPT + '<Text class:a>x</Text>\n<style>.b { color: red; }</style>')
    assert "no tiene reglas" in c.warnings[0].message


def test_key_block():
    c = compile_source(SCRIPT + "<Column>{#key b}<Text>{b}</Text>{/key}</Column>")
    (slot,) = c.ir.template.slots
    assert type(slot).__name__ == "KeySlot" and slot.expression.code == "b"
    assert "model: jk.m0" in c.qml


# -- manejadores en línea -------------------------------------------------------------
INLINE_SCRIPT = "<script>\nfrom janelkit import state, prop\nn = state(0)\nitems = state([1])\nlimit = prop(3)\n</script>\n"


def test_handlers_accept_calls_and_simple_statements():
    compiled = compile_source(
        INLINE_SCRIPT
        + "<Column>"
        + "<Button on:click={n += 1}>a</Button>"
        + "<Button on:click={n = 0; items.append(n)}>b</Button>"
        + "<Button on:click={print(n)}>c</Button>"
        + "<Button on:click={lambda: print(n)}>d</Button>"
        + "<TextField on:input={n = len(event)} />"
        + "</Column>"
    )
    handlers = compiled.ir.template.handlers
    assert [h.inline for h in handlers] == [True, True, True, False, True]


def test_compound_statements_are_rejected_in_handlers():
    err = compile_error(INLINE_SCRIPT + "<Button on:click={for x in items: n = x}>a</Button>")
    assert "'for' no está permitido en un manejador" in err.first.message
    assert "función en el <script>" in err.first.hint


def test_statements_are_still_rejected_outside_handlers():
    err = compile_error(INLINE_SCRIPT + "<Text>{n = 1}</Text>")
    assert "expresión Python no válida" in err.first.message


def test_inline_handler_checks_assigned_names():
    assert "'m' no está definido" in compile_error(INLINE_SCRIPT + "<Button on:click={m = 1}>a</Button>").first.message
    err = compile_error(INLINE_SCRIPT + "<Button on:click={limit = 1}>a</Button>")
    assert "no puede asignar a la prop 'limit'" in err.first.message
    err = compile_error(INLINE_SCRIPT + "<Column>{#each items as x}<Button on:click={x = 2}>a</Button>{/each}</Column>")
    assert "variable de bloque 'x'" in err.first.message
