// Caja con position absolute o fixed: como en la web, el puntero no atraviesa la caja
// (un velo sobre la ventana no deja pulsar lo de debajo). Va debajo de su contenido; el
// clic en la propia caja se pasa a su on:click (y su `pressed`, a :pressed). La crea Fx.flexDecorations, solo entonces.
import QtQuick

MouseArea {
    property Item box: null
    readonly property bool fxDecoration: true
    anchors.fill: parent
    z: -1
    enabled: box !== null && box.fxPointerEvents && (box.fxPosition === "absolute" || box.fxPosition === "fixed")
    acceptedButtons: Qt.AllButtons
    hoverEnabled: true
    cursorShape: box && box.fxCursor >= 0 ? box.fxCursor : Qt.ArrowCursor
    onWheel: (wheel) => { wheel.accepted = true }
    onClicked: (mouse) => { if (box.fxClickable && mouse.button === Qt.LeftButton) box.fxActivate(mouse.x, mouse.y, mouse.button) }
}
