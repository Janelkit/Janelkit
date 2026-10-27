// Pulsación de una caja (on:click, :pressed). Lo crea Fx.flexDecorations solo cuando la
// caja lo necesita; la caja lee `pressed` de aquí.
import QtQuick

TapHandler {
    property Item box: null
    // Con FxBlocker (position absolute o fixed), el clic y el pulsado los lleva él: con
    // los dos, Qt deja pasar la pulsación a lo que hay debajo.
    enabled: box !== null && box.fxPointerEvents && (box.fxClickable || box.fxTrackPress) && box.fxBlocker === null
    acceptedButtons: Qt.LeftButton
    onTapped: (eventPoint, button) => {
        if (box.fxClickable) box.fxActivate(eventPoint.position.x, eventPoint.position.y, button)
    }
}
