"""<flex>: el elemento base con flexbox (fase 1: caja y disposición). Ver docs/flex.md."""
import pytest
from conftest import find, visual_items
from PySide6.QtCore import QCoreApplication

from fluxui.compiler import compile_source
from fluxui.diagnostics import FluxError


def settle(m, rounds=3):
    for _ in range(rounds):
        QCoreApplication.processEvents()


def geo(item):
    p = item.mapToItem(None, 0, 0)
    return round(p.x(), 1), round(p.y(), 1), round(item.width(), 1), round(item.height(), 1)


def page(body, style="", width=400, height=300):
    return f"""<Window width={{{width}}} height={{{height}}}>
{body}
</Window>
<style>
.a {{ width: 50px; height: 20px; }}
.b {{ width: 50px; height: 40px; }}
{style}
</style>"""


def test_flex_is_a_row_and_stretches_by_default(mount):
    m = mount(page('<flex><flex id="x" class="a" /><Text id="t">hola</Text></flex>'))
    settle(m)
    x, t = find(m, "x"), find(m, "t")
    assert geo(x)[:2] == (0, 0) and geo(x)[2] == 50
    assert geo(t)[0] == 50 and geo(t)[1] == 0
    assert geo(t)[3] == 300  # align-items: stretch (alto de la fila)


def test_grow_shrink_and_basis(mount):
    m = mount(page(
        '<flex direction="column">'
        '<flex id="fila1"><flex id="g1" class="g1" /><flex id="g2" class="g2" /></flex>'
        '<flex id="fila2"><flex id="s1" class="s" /><flex id="s2" class="s" /></flex>'
        '</flex>',
        ".g1 { flex: 1; } .g2 { flex: 2; } .s { flex-basis: 300px; height: 10px; }",
    ))
    settle(m)
    assert geo(find(m, "g1"))[2] == pytest.approx(400 / 3, abs=0.1)
    assert geo(find(m, "g2"))[2] == pytest.approx(800 / 3, abs=0.1)
    # flex-shrink: 1 por defecto, en proporción a la base
    assert geo(find(m, "s1"))[2] == 200 and geo(find(m, "s2"))[0] == 200


def test_justify_auto_margins_and_order(mount):
    m = mount(page(
        '<flex direction="column">'
        '<flex class="fila" id="sb"><flex id="j1" class="a" /><flex id="j2" class="a" /><flex id="j3" class="a" /></flex>'
        '<flex class="fila"><flex id="m1" class="a" /><flex id="m2" class="a empuja" /></flex>'
        '<flex class="fila"><flex id="o1" class="a" /><flex id="o2" class="a primero" /></flex>'
        '</flex>',
        ".fila { height: 20px; } .empuja { margin-left: auto; } .primero { order: -1; }",
    ))
    settle(m)
    find(m, "sb")  # existe
    assert [geo(find(m, i))[0] for i in ("j1", "j2", "j3")] == [0, 50, 100]
    assert geo(find(m, "m2"))[0] == 350 and geo(find(m, "m1"))[0] == 0
    assert geo(find(m, "o2"))[0] == 0 and geo(find(m, "o1"))[0] == 50


def test_space_between_and_center(mount):
    m = mount(page(
        '<flex direction="column">'
        '<flex justify="space-between"><flex id="a1" class="a" /><flex id="a2" class="a" /><flex id="a3" class="a" /></flex>'
        '<flex justify="space-evenly"><flex id="e1" class="a" /><flex id="e2" class="a" /></flex>'
        '<flex class="alto" align="center"><flex id="c1" class="a" /><flex id="c2" class="b fin" /></flex>'
        '</flex>',
        ".alto { height: 100px; } .fin { align-self: end; }",
    ))
    settle(m)
    assert [geo(find(m, i))[0] for i in ("a1", "a2", "a3")] == [0, 175, 350]
    assert [geo(find(m, i))[0] for i in ("e1", "e2")] == [100, 250]
    top = geo(find(m, "c1"))[1] - 40  # la caja alta empieza 40 px más abajo (dos filas de 20)
    assert top == 40 and geo(find(m, "c2"))[1] == 40 + 100 - 40


def test_percent_sizes(mount):
    m = mount(page(
        '<flex direction="column" align="start"><flex id="p" class="mitad" /></flex>',
        ".mitad { width: 50%; height: 25%; }",
    ))
    settle(m)
    assert geo(find(m, "p"))[2:] == (200, 75)


def test_wrap_makes_a_grid_that_reflows_on_resize(mount):
    cells = "".join(f'<flex id="c{i}" class="celda" />' for i in range(6))
    m = mount(page(f'<flex class="rejilla">{cells}</flex>', ".rejilla { flex-wrap: wrap; gap: 10px; align-content: start; } .celda { flex: 1 1 200px; height: 30px; }", width=500))
    settle(m)
    rows = sorted({geo(find(m, f"c{i}"))[1] for i in range(6)})
    assert rows == [0, 40, 80]  # 2 por fila
    assert geo(find(m, "c1"))[2] == 245

    m.root.setWidth(700)
    settle(m)
    rows = sorted({geo(find(m, f"c{i}"))[1] for i in range(6)})
    assert rows == [0, 40]  # 3 por fila
    assert geo(find(m, "c2"))[2] == pytest.approx(680 / 3, abs=0.1)


def test_text_wraps_in_a_narrow_row_and_the_row_grows(mount):
    long = "palabra " * 30
    m = mount(page(
        f'<flex direction="column" align="start"><flex id="fila" class="estrecha"><Text id="t">{long}</Text></flex></flex>',
        ".estrecha { width: 120px; }",
    ))
    settle(m)
    t, fila = find(m, "t"), find(m, "fila")
    assert geo(t)[2] == 120
    assert geo(t)[3] > 60 and geo(fila)[3] == geo(t)[3]


def test_overflow_auto_scrolls_the_content(mount):
    items = "".join(f'<flex id="i{n}" class="item" />' for n in range(5))
    m = mount(page(
        f'<flex direction="column" align="start"><flex id="zona" class="zona">{items}</flex></flex>',
        ".zona { direction: column; height: 100px; width: 200px; overflow: auto; } .item { height: 50px; }",
    ))
    settle(m)
    zona = find(m, "zona")
    assert geo(zona)[3] == 100
    flick = next(i for i in visual_items(m) if i.inherits("QQuickFlickable"))
    assert flick.property("contentHeight") == 250
    assert geo(find(m, "i4"))[1] == 200


def test_per_side_borders_and_corner_radii(mount):
    m = mount(page(
        '<flex id="caja" class="caja" />',
        ".caja { border-left: 3px solid #f00; border-radius: 8px 0 8px 0; padding: 4px; }",
    ))
    settle(m)
    caja = find(m, "caja")
    assert caja.property("fxBorderLeftW") == 3 and caja.property("fxBorderTopW") == 0
    assert caja.property("topLeftRadius") == 8 and caja.property("topRightRadius") == 0
    assert any(i.metaObject().className().startswith("FxSides") for i in visual_items(m))


def test_lowercase_tags_are_base_elements():
    with pytest.raises(FluxError) as exc:
        compile_source("<flx />")
    assert "elemento base desconocido <flx>" in str(exc.value) and "<flex>" in str(exc.value)


def test_flex_attribute_values_are_checked():
    with pytest.raises(FluxError) as exc:
        compile_source('<flex direction="diagonal" />')
    assert "row-reverse" in str(exc.value)


def test_new_style_properties_compile_without_warnings():
    c = compile_source(
        '<flex class="f"><Text class="t">x</Text></flex>\n<style>'
        ".f { flex-direction: column; flex-wrap: wrap; row-gap: 4px; column-gap: 8px;"
        " justify-content: space-around; align-content: center; overflow: hidden; }"
        " .t { flex: 1 0 120px; order: 2; margin: 4px auto; align-self: baseline; }</style>"
    )
    assert [w.message for w in c.warnings] == ["align-self no soportado: 'baseline'; valores admitidos: start, center, end, stretch, auto"]
    for expected in ('direction: "column"', "wrap: true", "rowGap: 4", "columnGap: 8", 'justifyContent: "space-around"',
                     'alignContent: "center"', 'fxOverflow: "hidden"', "property real fxShrink: 0",
                     "property real fxBasis: 120", "property int fxOrder: 2", "property int fxAutoMargin: 10",
                     "Layout.topMargin: 4"):
        assert expected in c.qml, expected


def test_element_selector_for_flex():
    c = compile_source('<flex><Text>x</Text></flex>\n<style>flex { gap: 6px; }</style>')
    assert "gap: 6" in c.qml and c.warnings == []
