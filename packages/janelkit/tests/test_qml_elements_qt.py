"""Elementos propios en QML: importar un .qml del proyecto y usarlo como un elemento más."""
import logging
from pathlib import Path

import pytest
from janelkit.testing import find, texts
from PySide6.QtCore import QMetaObject, Q_ARG

from janelkit.compiler import compile_file
from janelkit.compiler.qml_interface import read_interface
from janelkit.diagnostics import JanelError

GAUGE = """import QtQuick

// Un indicador sencillo.
Rectangle {
    id: root
    property real value: 0
    property string label: "{no es una llave}"
    readonly property bool full: value >= 100
    property color tint: "steelblue"
    signal picked(real v, string why)
    signal reset
    implicitWidth: 120; implicitHeight: 16
    color: tint

    function pick(v) { root.value = v; root.picked(v, "click") }
    Item {
        property int notMine: 1
    }
}
"""

APP = """<script>
from janelkit import state, ref
from widgets.Gauge import Gauge
level = state(10)
picked = state([])
g = ref()
</script>
<Column>
  <Gauge id="g" ref={g} bind:value={level} label="Nivel" tint="tomato" width={200}
         on:picked={picked.append((event[0], event[1]))} />
  <Text>{level}</Text>
</Column>
"""


@pytest.fixture
def project(tmp_path):
    def make(files: dict[str, str]) -> Path:
        for rel, text in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return tmp_path / "App.janel"

    return make


def test_reads_the_interface_of_the_root_object(tmp_path):
    path = tmp_path / "Gauge.qml"
    path.write_text(GAUGE, encoding="utf-8")
    spec = read_interface(path, "Gauge", "W")
    assert spec.qml_type == "W.Gauge"
    assert {n: p.type for n, p in spec.props.items()} == {"value": "number", "label": "string", "tint": "color"}
    assert set(spec.two_way) == {"value", "label", "tint"}  # readonly 'full' no se puede escribir
    assert spec.events["picked"].args == ("v", "why") and spec.events["picked"].qml_handler == "onPicked"
    assert spec.events["reset"].args == ()


def test_qml_element_props_bind_events_and_ref(mount, project, caplog):
    m = mount(project({"App.janel": APP, "widgets/Gauge.qml": GAUGE}))
    assert caplog.text == ""
    gauge = find(m, "g")
    ns = m.instance.namespace
    assert gauge.property("value") == 10 and gauge.property("label") == "Nivel"
    assert ns["g"].value is gauge and gauge.property("width") == 200
    ns["level"].value = 30
    assert gauge.property("value") == 30
    assert QMetaObject.invokeMethod(gauge, "pick", Q_ARG("QVariant", 75))
    assert ns["level"].value == 75 and texts(m) == ["75.0"]  # bind:value devuelve el cambio (real en QML)
    assert ns["picked"].value == [(75, "click")]


def test_unknown_prop_and_event_are_compile_errors(project):
    app = APP.replace('label="Nivel"', 'lable="Nivel"')
    with pytest.raises(JanelError) as info:
        compile_file(project({"App.janel": app, "widgets/Gauge.qml": GAUGE}))
    assert "propiedad desconocida" in info.value.first.message or "lable" in info.value.first.message
    assert "label" in (info.value.first.hint or "")
    app = APP.replace("on:picked", "on:pickd")
    with pytest.raises(JanelError) as info:
        compile_file(project({"App.janel": app, "widgets/Gauge.qml": GAUGE}))
    assert "on:pickd" in info.value.first.message and "on:picked" in info.value.first.hint


def test_readonly_properties_cannot_be_set(project):
    app = APP.replace('label="Nivel"', "full={True}")
    with pytest.raises(JanelError):
        compile_file(project({"App.janel": app, "widgets/Gauge.qml": GAUGE}))


def test_qml_files_are_part_of_the_app_files(project):
    compiled = compile_file(project({"App.janel": APP, "widgets/Gauge.qml": GAUGE}))
    assert any(f.endswith("Gauge.qml") for f in compiled.files)
    assert compiled.qml.count("as JkUser0") == 1 and "JkUser0.Gauge {" in compiled.qml


def test_qml_errors_point_to_the_janel_usage(mount, project, caplog):
    broken = GAUGE.replace("color: tint", "color: noExiste")
    with caplog.at_level(logging.WARNING, logger="janelkit"):
        mount(project({"App.janel": APP, "widgets/Gauge.qml": broken}))
    assert "noExiste" in caplog.text


def test_flex_on_a_qml_element_follows_the_janel_layout_rules(mount, project):
    app = """<script>
from widgets.Gauge import Gauge
</script>
<Window width={400} height={300}>
  <Column>
    <Text>arriba</Text>
    <Gauge id="g" flex={1} />
  </Column>
</Window>
"""
    m = mount(project({"App.janel": app, "widgets/Gauge.qml": GAUGE}))
    gauge = find(m, "g")
    assert gauge.property("jkFlex") == 1
    assert gauge.height() > 200  # ocupa el alto libre de la columna (no sus 16 px naturales)


def test_a_list_passed_whole_to_qml_follows_in_place_changes(mount, project):
    """`values={serie.value}` entrega una copia a QML: modificar la lista en el sitio
    (append, del) también debe llegar, no solo asignar una lista nueva."""
    chart = 'import QtQuick\nItem { property var values: []; readonly property int n: values.length }'
    app = """<script>
from janelkit import state
from widgets.Chart import Chart
serie = state([1.0])
nested = state({"pts": [1, 2]})
</script>
<Column>
  <Chart id="a" values={serie} />
  <Chart id="b" values={nested["pts"]} />
</Column>
"""
    m = mount(project({"App.janel": app, "widgets/Chart.qml": chart}))
    ns = m.instance.namespace
    ns["serie"].value.append(2.0)
    assert find(m, "a").property("n") == 2
    del ns["serie"].value[0]
    assert list(find(m, "a").property("values")) == [2.0]
    ns["nested"].value["pts"].append(3)
    assert find(m, "b").property("n") == 3
