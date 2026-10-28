// Fondo y borde de un <Text> (etiquetas, contadores). Lo crea Fx.textDecorations solo si
// el texto tiene background o border.
import QtQuick

Rectangle {
    property Item label: null
    anchors.fill: parent
    z: -1
    visible: label !== null && (label.fxBackground.a > 0 || label.fxBorderWidth > 0)
    color: label ? label.fxBackground : "transparent"
    border.color: label ? label.fxBorderColor : "transparent"
    border.width: label ? label.fxBorderWidth : 0
    radius: label ? label.fxRadius : 0
}
