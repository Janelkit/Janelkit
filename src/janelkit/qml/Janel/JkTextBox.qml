// Fondo y borde de un <Text> (etiquetas, contadores). Lo crea Jk.textDecorations solo si
// el texto tiene background o border.
import QtQuick

Rectangle {
    property Item label: null
    anchors.fill: parent
    z: -1
    visible: label !== null && (label.jkBackground.a > 0 || label.jkBorderWidth > 0)
    color: label ? label.jkBackground : "transparent"
    border.color: label ? label.jkBorderColor : "transparent"
    border.width: label ? label.jkBorderWidth : 0
    radius: label ? label.jkRadius : 0
}
