// Grupo de opciones excluyentes de FluxUI.
// options: lista de textos o de {label, value}. value: el valor elegido. horizontal: en fila.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

Grid {
    id: group
    property var options: []
    property var value: undefined
    property bool horizontal: false
    property var fxCurrent: undefined
    property color fxColor: fxtheme.text
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    signal picked(var choice)

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, false, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, group, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)

    columns: horizontal ? Math.max(1, Fx.options(options).length) : 1
    columnSpacing: 16
    rowSpacing: 4
    onValueChanged: fxCurrent = value
    Component.onCompleted: fxCurrent = value

    Repeater {
        model: Fx.options(group.options)

        RadioButton {
            id: radio
            required property var modelData
            Accessible.name: modelData.label
            text: modelData.label
            checked: modelData.value === group.fxCurrent
            autoExclusive: false
            enabled: group.enabled
            hoverEnabled: true
            spacing: 8
            onClicked: {
                group.fxCurrent = modelData.value
                checked = Qt.binding(() => modelData.value === group.fxCurrent)
                group.picked(modelData.value)
            }

            indicator: Rectangle {
                implicitWidth: 18
                implicitHeight: 18
                x: radio.mirrored ? radio.width - width - radio.rightPadding : radio.leftPadding
                y: radio.topPadding + (radio.availableHeight - height) / 2
                radius: 9
                color: fxtheme.surface
                border.color: radio.checked || radio.visualFocus ? fxtheme.primary : fxtheme.border
                border.width: radio.visualFocus ? 2 : 1
                opacity: radio.enabled ? 1 : 0.55

                Rectangle {
                    anchors.centerIn: parent
                    width: 10
                    height: 10
                    radius: 5
                    color: fxtheme.primary
                    visible: radio.checked
                }
            }

            contentItem: Text {
                text: radio.text
                font: radio.font
                color: group.fxColor
                opacity: radio.enabled ? 1 : 0.55
                leftPadding: radio.mirrored ? 0 : radio.indicator.width + radio.spacing
                rightPadding: radio.mirrored ? radio.indicator.width + radio.spacing : 0
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
