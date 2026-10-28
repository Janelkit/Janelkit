import QtQuick

// Elemento propio escrito en QML: una barra de progreso que se puede pulsar.
// JanelKit lee sus `property` y `signal` para validar el uso desde App.janel:
//   <Meter value={count} max={5} on:picked={count = event} />
// Los tokens del tema están disponibles como `jktheme`.
Rectangle {
    id: root
    property real value: 0
    property real max: 5
    signal picked(int step)

    implicitWidth: 320
    implicitHeight: 14
    radius: height / 2
    color: jktheme.border

    Rectangle {
        width: parent.width * Math.max(0, Math.min(root.value / root.max, 1))
        height: parent.height
        radius: parent.radius
        color: root.value >= root.max ? jktheme.success : jktheme.primary
        Behavior on width { NumberAnimation { duration: 150 } }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: (mouse) => root.picked(Math.round(mouse.x / width * root.max))
    }
}
