// Contenedor horizontal de FluxUI: RowLayout con relleno, fondo, borde y radio.
// El layout interior solo ocupa todo el eje principal cuando algún hijo tiene
// flex; así el espacio sobrante no se reparte entre los hijos (como en CSS).
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

Rectangle {
    id: box
    default property alias content: lay.data
    property alias gap: lay.spacing
    property real padding: 0
    property real topPadding: padding
    property real rightPadding: padding
    property real bottomPadding: padding
    property real leftPadding: padding
    property int align: 0           // align-items (banderas Qt.Align*)
    property bool stretch: false    // align-items: stretch
    property real justify: 0        // justify-content: 0 inicio, 0.5 centro, 1 final
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    // Como hijo de otro contenedor
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    readonly property bool fillMain: Fx.anyFlex(lay.children)
    // on:click: el contenedor entero se puede pulsar (tarjetas, filas de lista)
    property bool fxClickable: false
    readonly property bool hovered: hover.hovered
    signal clicked()

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    color: fxClickable && hover.hovered ? Qt.tint(fxBackground, fxtheme.hover) : fxBackground
    radius: fxRadius
    border.color: fxBorderColor
    border.width: fxBorderWidth
    implicitWidth: lay.implicitWidth + leftPadding + rightPadding
    implicitHeight: lay.implicitHeight + topPadding + bottomPadding

    HoverHandler {
        id: hover
        enabled: box.fxClickable
        cursorShape: Qt.PointingHandCursor
    }
    TapHandler {
        enabled: box.fxClickable
        onTapped: box.clicked()
    }

    RowLayout {
        id: lay
        readonly property bool fxHorizontal: true
        readonly property int fxAlign: box.align
        readonly property bool fxStretch: box.stretch
        readonly property real fxFree: box.width - box.leftPadding - box.rightPadding
        x: box.leftPadding + (box.fillMain ? 0 : Math.max(0, fxFree - implicitWidth) * box.justify)
        y: box.topPadding
        width: box.fillMain ? fxFree : implicitWidth
        height: box.height - box.topPadding - box.bottomPadding
        spacing: 0
    }
}
