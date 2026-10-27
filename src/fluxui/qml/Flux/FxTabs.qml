// Barra de pestañas de FluxUI. Solo la barra: el contenido se elige con {#if} según `value`.
// options: lista de textos o de {label, value}.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

TabBar {
    id: bar
    property var options: []
    property var value: undefined
    property color fxColor: fxtheme.text
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    readonly property var fxModel: Fx.options(options)
    signal picked(var choice)

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, bar, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)

    function fxSync() {
        for (let i = 0; i < fxModel.length; ++i)
            if (fxModel[i].value === value) { currentIndex = i; return }
        currentIndex = -1
    }
    onValueChanged: fxSync()
    onFxModelChanged: fxSync()
    Component.onCompleted: fxSync()

    background: Rectangle {
        color: "transparent"
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: fxtheme.border
        }
    }

    Repeater {
        model: bar.fxModel

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
                color: tab.checked ? fxtheme.primary : bar.fxColor
                opacity: tab.enabled ? 1 : 0.55
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                implicitHeight: 36
                color: tab.hovered && !tab.checked ? fxtheme.hover : "transparent"
                border.color: tab.visualFocus ? fxtheme.primary : "transparent"
                border.width: tab.visualFocus ? 2 : 0
                radius: fxtheme.radius_sm
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 2
                    color: fxtheme.primary
                    visible: tab.checked
                }
            }
        }
    }
}
