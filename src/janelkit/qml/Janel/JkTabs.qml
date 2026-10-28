// Barra de pestañas de JanelKit. Solo la barra: el contenido se elige con {#if} según `value`.
// options: lista de textos o de {label, value}.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

TabBar {
    id: bar
    property var options: []
    property var value: undefined
    property color jkColor: jktheme.text
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false
    readonly property var jkModel: Jk.options(options)
    signal picked(var choice)

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, bar, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    function jkSync() {
        for (let i = 0; i < jkModel.length; ++i)
            if (jkModel[i].value === value) { currentIndex = i; return }
        currentIndex = -1
    }
    onValueChanged: jkSync()
    onJkModelChanged: jkSync()
    Component.onCompleted: jkSync()

    background: Rectangle {
        color: "transparent"
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: jktheme.border
        }
    }

    Repeater {
        model: bar.jkModel

        TabButton {
            id: tab
            required property var modelData
            Accessible.name: modelData.label
            required property int index
            text: modelData.label
            width: implicitWidth
            leftPadding: 14
            rightPadding: 14
            hoverEnabled: true
            onClicked: bar.picked(modelData.value)

            contentItem: Text {
                text: tab.text
                font: tab.font
                color: tab.checked ? jktheme.primary : bar.jkColor
                opacity: tab.enabled ? 1 : 0.55
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                implicitHeight: 36
                color: tab.hovered && !tab.checked ? jktheme.hover : "transparent"
                border.color: tab.visualFocus ? jktheme.primary : "transparent"
                border.width: tab.visualFocus ? 2 : 0
                radius: jktheme.radius_sm
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 2
                    color: jktheme.primary
                    visible: tab.checked
                }
            }
        }
    }
}
