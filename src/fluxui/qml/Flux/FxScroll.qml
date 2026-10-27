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
    property alias align: col.align
    property alias stretch: col.stretch
    property alias justify: col.justify
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    property int fxFlex: 1
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight
    contentWidth: availableWidth
    clip: true
    background: Rectangle {
        color: sv.fxBackground
        radius: sv.fxRadius
        border.color: sv.fxBorderColor
        border.width: sv.fxBorderWidth
    }

    FxColumn {
        id: col
        width: sv.availableWidth
    }
}
