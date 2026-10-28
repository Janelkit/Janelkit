// QML escrito a mano: solo existe en el spike. En JanelKit lo genera el compilador.
import QtQuick
import QtQuick.Controls

ApplicationWindow {
    visible: true
    width: 360; height: 220
    title: "Spike: puente Python ↔ Qt Quick"

    Column {
        anchors.fill: parent
        padding: 24; spacing: 12
        Label { objectName: "label"; text: jk.countText; font.pixelSize: 20 }
        Button { objectName: "button"; text: "Incrementar"; onClicked: jk.invoke("increment") }
        TextField {
            objectName: "field"
            text: jk.name
            placeholderText: "Tu nombre"
            onTextEdited: jk.write("name", text)
        }
        Label { objectName: "echo"; text: "Hola, " + (jk.name || "invitado") }
    }
}
