// Pulsación de una caja (on:click, :pressed). Lo crea Jk.flexDecorations solo cuando la
// caja lo necesita; la caja lee `pressed` de aquí.
import QtQuick

TapHandler {
    property Item box: null
    // Con JkBlocker (position absolute o fixed), el clic y el pulsado los lleva él: con
    // los dos, Qt deja pasar la pulsación a lo que hay debajo.
    enabled: box !== null && box.jkPointerEvents && (box.jkClickable || box.jkTrackPress) && box.jkBlocker === null
    acceptedButtons: Qt.LeftButton
    onPressedChanged: if (box) box.jkSyncPressed()
    onTapped: (eventPoint, button) => {
        if (box.jkClickable) box.jkActivate(eventPoint.position.x, eventPoint.position.y, button)
    }
}
