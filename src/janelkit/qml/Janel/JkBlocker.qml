// Caja con position absolute o fixed: como en la web, el puntero no atraviesa la caja
// (un velo sobre la ventana no deja pulsar lo de debajo). Va debajo de su contenido; el
// clic en la propia caja se pasa a su on:click (y su `pressed`, a :pressed). La crea Jk.flexDecorations, solo entonces.
import QtQuick

MouseArea {
    property Item box: null
    readonly property bool jkDecoration: true
    anchors.fill: parent
    z: -1
    enabled: box !== null && box.jkPointerEvents && (box.jkPosition === "absolute" || box.jkPosition === "fixed")
    acceptedButtons: Qt.AllButtons
    hoverEnabled: true
    cursorShape: box && box.jkCursor >= 0 ? box.jkCursor : Qt.ArrowCursor
    onWheel: (wheel) => { wheel.accepted = true }
    onPressedChanged: if (box) box.jkSyncPressed()
    onClicked: (mouse) => { if (box.jkClickable && mouse.button === Qt.LeftButton) box.jkActivate(mouse.x, mouse.y, mouse.button) }
}
