"""Vía rápida de Column, Row y <flex direction="column">: layout de Qt cuando se puede,
motor de <flex> (flex.js) cuando no. Ver compiler/layout_choice.py y docs/arquitectura.md."""
import re
import tempfile
from pathlib import Path

import pytest
from janelkit.testing import find
from PySide6.QtCore import QCoreApplication, QPointF

from janelkit.compiler import compile_file, compile_source, layout_choice

BOX = re.compile(r"\b(JkColumn|JkRow|JkQtBox|JkFlexColumn|JkFlexRow|JkFlex) \{")


def boxes(template, style=""):
    """Tipos de caja generados, en orden (la raíz de la ventana primero)."""
    return BOX.findall(compile_source(f"{template}\n<style>{style}</style>" if style else template).qml)


def test_plain_column_and_row_use_qt_layouts():
    assert boxes("<column><row><text>a</text><button text='b' /></row><text>c</text></column>") == ["JkColumn", "JkRow"]


def test_flex_column_without_growing_children_uses_qt_layout():
    assert boxes('<column><flex direction="column"><text>a</text></flex><flex><text>b</text></flex></column>') == [
        "JkColumn", "JkQtBox", "JkFlex",  # <flex> en fila: encoge como CSS, siempre con el motor
    ]


@pytest.mark.parametrize(
    "style",
    [
        ".c { flex-wrap: wrap; }",
        ".c { justify-content: center; }",
        ".c { justify-content: space-between; }",
        ".c { overflow: auto; }",
        ".h { order: 1; }",
        ".h { margin-left: auto; }",
        ".h { width: 50%; }",
        ".h { flex-shrink: 0; }",
        ".h { flex-basis: 100px; }",
        ".h { position: relative; top: 2px; }",
        ".h:first-child { color: red; }",
        ".h { flex: 1; } .g { flex: 2; }",
        ".h:hover { order: 2; }",  # también lo que llega con un estado
        ".h { margin: 0 auto; }",
    ],
)
def test_what_only_the_flex_engine_does(style):
    t = '<column><row class="c"><text class="h">a</text><text class="g">b</text></row></column>'
    assert boxes(t, style)[1] == "JkFlexRow"


def test_one_growing_child_or_only_spacers_keep_qt_layout():
    t = '<column><row><text class="h">a</text><text>b</text></row><row><spacer /><text>c</text><spacer /></row></column>'
    assert boxes(t, ".h { flex: 1; }") == ["JkColumn", "JkRow", "JkRow"]
    # Un Spacer y otro hijo con flex: Qt no reparte en proporción
    assert boxes('<row><spacer /><text class="h">a</text></row>', ".h { flex: 1; }") == ["JkFlexRow"]


def test_repeated_or_implicit_children():
    script = "<script>\nitems = [1, 2]\nshow = True\n</script>\n"
    each = compile_source(script + '<row>{#each items as i}<text class="h">{i}</text>{/each}</row>\n<style>.h { flex: 1; }</style>').qml
    assert BOX.findall(each) == ["JkFlexRow"]  # varias filas con flex
    implicit = compile_source(script + "<column>{#if show}<text>a</text><text>b</text>{/if}</column>").qml
    assert BOX.findall(implicit) == ["JkColumn", "JkFlexColumn"]  # la caja implícita del {#if}, con el motor


def project(files):
    d = Path(tempfile.mkdtemp())
    (d / "components").mkdir()
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8")
    return d


def test_component_children_count_with_their_root_styles():
    d = project({
        "components/Ancho.janel": '<flex class="ancho"><text>x</text></flex>\n<style>.ancho { flex: 1; }</style>',
        "components/Quieto.janel": '<flex class="quieto"><text>x</text></flex>\n<style>.quieto { padding: 4px; }</style>',
        "components/Movido.janel": '<flex class="movido"><text>x</text></flex>\n<style>.movido { order: 2; }</style>',
        "components/Hueco.janel": "<column><slot /></column>",
        "A.janel": "<script>\nfrom components.Ancho import Ancho\nfrom components.Quieto import Quieto\n</script>\n"
                  "<row><Ancho /><Quieto /></row>",
        "B.janel": "<script>\nfrom components.Ancho import Ancho\n</script>\n<row><Ancho /><Ancho /></row>",
        "C.janel": "<script>\nfrom components.Movido import Movido\n</script>\n<row><Movido /><text>a</text></row>",
        "D.janel": '<script>\nfrom components.Quieto import Quieto\n</script>\n<row><Quieto class="h" /><text>a</text></row>\n'
                  "<style>.h { margin-left: auto; }</style>",
    })
    kind = lambda f: BOX.findall(compile_file(d / f).qml)[0]  # noqa: E731
    assert kind("A.janel") == "JkRow"  # un solo hijo crece
    assert kind("B.janel") == "JkFlexRow"  # dos raíces con flex: 1
    assert kind("C.janel") == "JkFlexRow"  # order en la raíz del componente
    assert kind("D.janel") == "JkFlexRow"  # margin: auto puesto desde la etiqueta
    hueco = compile_file(project({"components/Hueco.janel": "<column><slot /></column>"}) / "components" / "Hueco.janel", as_window=False).qml
    assert BOX.findall(hueco) == ["JkFlexColumn"]  # el contenido de un <slot /> no se conoce


def test_boxes_inside_an_engine_box_use_the_engine_too():
    # El motor lee al momento el tamaño de sus hijos; un layout de Qt lo calcula después.
    t = '<flex class="r"><column><text>a</text><row><text>b</text></row></column></flex>'
    assert boxes(t, ".r { flex-wrap: wrap; }") == ["JkFlex", "JkFlexColumn", "JkFlexRow"]
    # <scroll> no cuenta: su contenido sigue con layouts de Qt.
    assert boxes("<scroll><column><row><text>a</text></row></column></scroll>") == ["JkColumn", "JkRow"]


def test_component_root_inside_an_engine_box_uses_the_engine():
    d = project({
        "components/Tarjeta.janel": '<column class="t"><row><text>x</text></row></column>\n<style>.t { gap: 4px; }</style>',
        "Rejilla.janel": "<script>\nfrom components.Tarjeta import Tarjeta\nitems = [1, 2]\n</script>\n"
                        '<flex class="g">{#each items as i (i)}<Tarjeta />{/each}</flex>\n<style>.g { flex-wrap: wrap; }</style>',
        "Lista.janel": "<script>\nfrom components.Tarjeta import Tarjeta\nitems = [1, 2]\n</script>\n"
                      "<column>{#each items as i (i)}<Tarjeta />{/each}</column>",
    })
    path = str((d / "components" / "Tarjeta.janel").resolve())
    tarjeta = lambda page: BOX.findall(compile_file(d / page).component(path).qml)  # noqa: E731
    assert tarjeta("Rejilla.janel") == ["JkFlexColumn", "JkFlexRow"]
    assert tarjeta("Lista.janel") == ["JkColumn", "JkRow"]


def test_qt_boxes_with_engine_boxes_inside_are_marked():
    qml = compile_source('<column><column><flex><text>a</text></flex></column><column><text>b</text></column></column>').qml
    assert qml.count("jkDeep: true") == 2  # la exterior y la primera interior; la segunda no


def test_qt_box_in_scroll_follows_the_width(mount):
    # JkScroll coloca su contenido con el motor; la columna de dentro es un layout de Qt,
    # que flex.js coloca al momento (settleQt). Lo que ahorra se ve en las mediciones
    # (docs/arquitectura.md); aquí, que el resultado sea el mismo.
    m = mount("""<window width={400} height={300}><scroll><column id="c"><text id="t">""" + "palabra " * 40
              + """</text><text>fin</text></column></scroll></window>""")
    c, t = find(m, "c"), find(m, "t")
    assert c.metaObject().className().startswith("JkColumn")
    m.root.setWidth(150)
    QCoreApplication.processEvents()
    assert t.height() > 60 and c.height() == c.property("implicitHeight") >= t.height()


PAGE = """<window width={640} height={480}>
<column id="raiz" class="raiz">
  <text id="t1">Un título largo que se corta en varias líneas cuando la ventana es estrecha de verdad</text>
  <row id="cab" class="cab">
    <text id="nombre" class="nombre">Nombre que también puede cortarse si no cabe</text>
    <text id="etq">etiqueta</text>
    <button id="b1" text="Abrir" />
  </row>
  <row id="centrada"><spacer /><text id="medio">en medio</text><spacer /></row>
  <column id="caja" class="caja">
    <text id="corto" class="fin">corto</text>
    <button id="b2" text="Botón" />
    <text id="mx" class="max">limitado a 120 px de ancho, con varias palabras</text>
  </column>
  <flex id="fcol" direction="column" class="fcol">
    <text id="f1">uno</text>
    <flex id="f2" class="cuadro" />
    <text id="f3" class="centro">fin</text>
  </flex>
  <row id="margenes" class="margenes"><flex id="m1" class="cuadro m" /><flex id="m2" class="cuadro" /></row>
</column>
</window>
<style>
.raiz { gap: 8px; padding: 10px; }
.cab { gap: 6px; padding: 4px 8px; border: 1px solid #cccccc; }
.nombre { flex: 1; font-weight: 600; }
.caja { align-items: center; gap: 4px; padding: 6px; }
.fin { align-self: end; }
.max { max-width: 120px; }
.fcol { gap: 3px; padding: 5px; }
.cuadro { width: 40px; height: 30px; }
.centro { align-self: center; }
.m { margin: 4px 10px; }
.margenes { gap: 2px; }
</style>
"""
IDS = ["raiz", "t1", "cab", "nombre", "etq", "b1", "centrada", "medio", "caja", "corto", "b2", "mx",
       "fcol", "f1", "f2", "f3", "margenes", "m1", "m2"]  # fmt: skip


def geometry(mount, fast, monkeypatch):
    from janelkit.testing import find

    monkeypatch.setattr(layout_choice, "FAST_LAYOUTS", fast)
    m = mount(PAGE)
    out = []
    for width in (640, 300):
        m.root.setWidth(width)
        for _ in range(4):
            QCoreApplication.processEvents()
        shot = {}
        for i in IDS:
            it = find(m, i)
            p = it.mapToScene(QPointF(0, 0))
            shot[i] = (round(p.x(), 1), round(p.y(), 1), round(it.width(), 1), round(it.height(), 1))
        out.append(shot)
    kinds = {i: find(m, i).metaObject().className().split("_QML")[0] for i in ("raiz", "cab", "caja", "fcol", "margenes")}
    return out, kinds


def test_qt_layout_places_like_the_flex_engine(mount, monkeypatch):
    fast, kinds = geometry(mount, True, monkeypatch)
    assert set(kinds.values()) == {"JkColumn", "JkRow", "JkQtBox"}  # de verdad por la vía rápida
    slow, kinds = geometry(mount, False, monkeypatch)
    assert set(kinds.values()) == {"JkFlexColumn", "JkFlexRow", "JkFlex"}
    for a, b in zip(fast, slow):
        for i in IDS:
            # Los layouts de Qt redondean a píxeles enteros; el motor, no (en macOS los
            # textos miden fracciones distintas que en Windows): hasta 1 px de diferencia.
            assert a[i] == pytest.approx(b[i], abs=1.0), i
    # Comprobaciones directas: el espacio de sobra se queda al final, Spacer centra,
    # align-self y max-width.
    narrow = fast[1]
    assert narrow["t1"][1] == 10 and narrow["t1"][3] > 20  # arriba (padding) y cortado en varias líneas
    medio = fast[0]["medio"]
    assert medio[0] + medio[2] / 2 == pytest.approx(320, abs=1)
    assert fast[0]["mx"][2] == 120
    caja = fast[0]["caja"]
    assert fast[0]["corto"][0] + fast[0]["corto"][2] == pytest.approx(caja[0] + caja[2] - 6, abs=0.6)  # align-self: end
