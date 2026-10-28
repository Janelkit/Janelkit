import QtQuick
import QtQuick.Shapes

// Gráfica de línea con relleno, escrita en QML (vía de escape: JanelKit no tiene
// <Canvas> ni <Chart>; según docs/alcance.md las gráficas son de janelkit-kit).
//   <LineChart values={serie.history.value} max={100} color="#3b5bdb" />
// Se traza con QtQuick.Shapes: los puntos se calculan en JS y se dibujan en la GPU.
Item {
    id: root
    property var values: []          // lista de números, del más antiguo al más reciente
    property real max: 100           // 0: escala automática (con margen)
    property int capacity: 0         // puntos que caben a lo ancho (0: los que haya); los nuevos, a la derecha
    property color color: jktheme.primary
    property string unit: ""         // solo para el texto al pasar el ratón
    property bool grid: true
    property bool hoverable: true
    readonly property real scaleMax: max > 0 ? max : niceMax()
    signal hovered(int index, real value)

    implicitWidth: 240
    implicitHeight: 80

    function niceMax() {
        let top = 0
        for (let i = 0; i < values.length; i++) if (values[i] > top) top = values[i]
        if (top <= 0) return 1
        const step = Math.pow(10, Math.floor(Math.log10(top)))
        for (const k of [1, 2, 5, 10]) if (k * step >= top * 1.1) return k * step
        return 10 * step
    }

    // Rejilla: tres líneas horizontales.
    Repeater {
        model: root.grid ? 3 : 0
        Rectangle {
            required property int index
            y: Math.round(root.height * (index + 1) / 4)
            width: root.width; height: 1
            color: jktheme.border
        }
    }

    // La línea y el relleno se trazan con Shapes (en la GPU): recalcular los puntos en JS
    // es barato; rasterizarlos en un Canvas, no (ver HALLAZGOS.md, mediciones).
    readonly property var jkLine: {
        const v = values, n = v.length, w = width, h = height
        if (n < 2 || w <= 0 || h <= 0) return []
        const slots = Math.max(capacity, n), dx = w / (slots - 1), x0 = (slots - n) * dx
        const top = scaleMax, pts = new Array(n)
        for (let i = 0; i < n; i++)
            pts[i] = Qt.point(x0 + i * dx, h - Math.max(0, Math.min(v[i] / top, 1)) * (h - 2) - 1)
        return pts
    }
    readonly property var jkArea: jkLine.length
        ? jkLine.concat([Qt.point(width, height), Qt.point(jkLine[0].x, height)]) : []

    Shape {
        anchors.fill: parent
        asynchronous: true          // la triangulación, en otro hilo
        ShapePath {
            strokeColor: "transparent"
            fillColor: Qt.alpha(root.color, 0.15)
            PathPolyline { path: root.jkArea }
        }
        ShapePath {
            strokeColor: root.color
            strokeWidth: 1.5
            fillColor: "transparent"
            PathPolyline { path: root.jkLine }
        }
    }

    // Valor bajo el ratón.
    HoverHandler { id: hover; enabled: root.hoverable }
    readonly property int jkSlots: Math.max(capacity, values.length)
    readonly property int hoverIndex: hover.hovered && values.length > 1
        ? Math.round(hover.point.position.x / width * (jkSlots - 1)) - (jkSlots - values.length) : -1
    onHoverIndexChanged: if (hoverIndex >= 0) hovered(hoverIndex, values[hoverIndex])
    Rectangle {
        visible: root.hoverIndex >= 0
        x: (root.hoverIndex + root.jkSlots - root.values.length) / Math.max(1, root.jkSlots - 1) * root.width
        width: 1; height: parent.height
        color: jktheme.text_muted
    }
    Text {
        visible: root.hoverIndex >= 0
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 4
        color: jktheme.text
        font.pixelSize: 11
        text: root.hoverIndex >= 0 ? Number(root.values[root.hoverIndex]).toFixed(1) + " " + root.unit : ""
    }
}
