// Ventana de `flux dev` con los errores de compilación. Se cierra sola al corregirlos.
import QtQuick
import QtQuick.Controls.Basic

ApplicationWindow {
    title: "FluxUI \u2014 error al recargar"
    width: 820
    height: 420
    visible: true
    color: "#1f1416"
    property string message: ""

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        TextArea {
            text: message
            readOnly: true
            selectByMouse: true
            wrapMode: TextEdit.NoWrap
            color: "#ffc9c9"
            font.family: Qt.platform.os === "windows" ? "Consolas" : "monospace"
            font.pixelSize: 13
            background: null
        }
    }
}
