// Lista desplegable de FluxUI.
// options: lista de textos o de {label, value}. value: el valor elegido.
// La selección del usuario se refleja al momento; si Python cambia `value`, manda Python.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

ComboBox {
    id: control
    property var options: []
    property var value: undefined
    property string placeholder: ""
    property color fxColor: fxtheme.text
    property color fxBackground: fxtheme.surface
    property color fxBorderColor: fxtheme.border
    property real fxBorderWidth: 1
    property real fxRadius: fxtheme.radius
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, false)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: Fx.touch(parent, control, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)
    Accessible.name: currentIndex < 0 ? placeholder : currentText  // el atributo label la sustituye

    model: Fx.options(options)
    textRole: "label"
    valueRole: "value"
    displayText: currentIndex < 0 ? placeholder : currentText
    hoverEnabled: true

    function fxSync() { currentIndex = indexOfValue(value) }
    onValueChanged: fxSync()
    onModelChanged: fxSync()
    Component.onCompleted: fxSync()

    contentItem: Text {
        leftPadding: control.mirrored ? control.indicator.width + 6 : 10
        rightPadding: control.mirrored ? 10 : control.indicator.width + 6
        text: control.displayText
        font: control.font
        color: control.currentIndex < 0 ? fxtheme.text_muted : control.fxColor
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        opacity: control.enabled ? 1 : 0.55
    }

    indicator: Text {
        x: control.mirrored ? 10 : control.width - width - 10
        y: (control.height - height) / 2
        text: "▾"
        color: fxtheme.text_muted
        font.pixelSize: 14
    }

    background: Rectangle {
        implicitWidth: 160
        implicitHeight: 34
        radius: control.fxRadius
        color: control.hovered ? Qt.tint(control.fxBackground, fxtheme.hover) : control.fxBackground
        border.color: control.visualFocus || control.popup.visible ? fxtheme.primary : control.fxBorderColor
        border.width: control.visualFocus ? 2 : control.fxBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }

    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: modelData.label
            font: control.font
            color: index === control.currentIndex ? fxtheme.primary : fxtheme.text
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { color: highlighted ? fxtheme.hover : "transparent" }
    }

    popup: Popup {
        y: control.height + 2
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        padding: 4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
        }
        background: Rectangle {
            radius: control.fxRadius
            color: fxtheme.surface
            border.color: fxtheme.border
        }
    }
}
