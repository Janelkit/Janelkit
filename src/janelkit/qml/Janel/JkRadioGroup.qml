// Grupo de opciones excluyentes de JanelKit.
// options: lista de textos o de {label, value}. value: el valor elegido. horizontal: en fila.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

Grid {
    id: group
    property var options: []
    property var value: undefined
    property bool horizontal: false
    property var jkCurrent: undefined
    property color jkColor: jktheme.text
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false
    signal picked(var choice)

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, false, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, group, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    columns: horizontal ? Math.max(1, Jk.options(options).length) : 1
    columnSpacing: 16
    rowSpacing: 4
    onValueChanged: jkCurrent = value
    Component.onCompleted: jkCurrent = value

    Repeater {
        model: Jk.options(group.options)

        RadioButton {
            id: radio
            required property var modelData
            Accessible.name: modelData.label
            text: modelData.label
            checked: modelData.value === group.jkCurrent
            autoExclusive: false
            enabled: group.enabled
            hoverEnabled: true
            spacing: 8
            onClicked: {
                group.jkCurrent = modelData.value
                checked = Qt.binding(() => modelData.value === group.jkCurrent)
                group.picked(modelData.value)
            }

            indicator: Rectangle {
                implicitWidth: 18
                implicitHeight: 18
                x: radio.mirrored ? radio.width - width - radio.rightPadding : radio.leftPadding
                y: radio.topPadding + (radio.availableHeight - height) / 2
                radius: 9
                color: jktheme.surface
                border.color: radio.checked || radio.visualFocus ? jktheme.primary : jktheme.border
                border.width: radio.visualFocus ? 2 : 1
                opacity: radio.enabled ? 1 : 0.55

                Rectangle {
                    anchors.centerIn: parent
                    width: 10
                    height: 10
                    radius: 5
                    color: jktheme.primary
                    visible: radio.checked
                }
            }

            contentItem: Text {
                text: radio.text
                font: radio.font
                color: group.jkColor
                opacity: radio.enabled ? 1 : 0.55
                leftPadding: radio.mirrored ? 0 : radio.indicator.width + radio.spacing
                rightPadding: radio.mirrored ? radio.indicator.width + radio.spacing : 0
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
