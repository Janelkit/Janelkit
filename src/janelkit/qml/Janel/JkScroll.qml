// Columna con desplazamiento vertical. Por defecto ocupa el espacio libre (flex: 1).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

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
    property color jkBackground: "transparent"
    property real jkRadius: 0
    property color jkBorderColor: "transparent"
    property real jkBorderWidth: 0
    property int jkFlex: 1
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)

    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight
    readonly property bool jkScrollable: true
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, sv, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)
    contentWidth: availableWidth
    clip: true
    background: Rectangle {
        color: sv.jkBackground
        radius: sv.jkRadius
        border.color: sv.jkBorderColor
        border.width: sv.jkBorderWidth
    }

    JkFlexColumn {
        id: col
        width: sv.availableWidth
        jkSizedW: true
    }
}
