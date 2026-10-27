// Columna con desplazamiento vertical. Por defecto ocupa el espacio libre (flex: 1).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

ScrollView {
    id: sv
    default property alias content: col.content
    property alias gap: col.gap
    property alias innerPadding: col.padding
    property alias innerTopPadding: col.topPadding
    property alias innerRightPadding: col.rightPadding
    property alias innerBottomPadding: col.bottomPadding
    property alias innerLeftPadding: col.leftPadding
    property alias alignItems: col.alignItems
    property alias justifyContent: col.justifyContent
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    property int fxFlex: 1
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight
    readonly property bool fxScrollable: true
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, sv, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)
    contentWidth: availableWidth
    clip: true
    background: Rectangle {
        color: sv.fxBackground
        radius: sv.fxRadius
        border.color: sv.fxBorderColor
        border.width: sv.fxBorderWidth
    }

    FxFlexColumn {
        id: col
        width: sv.availableWidth
        fxSizedW: true
    }
}
