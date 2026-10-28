// Ratón encima de una caja (:hover, on:click, cursor). Lo crea Fx.flexDecorations solo
// cuando la caja lo necesita; la caja lee `hovered` de aquí.
import QtQuick

HoverHandler {
    property Item box: null
    enabled: box !== null && box.fxPointerEvents && (box.fxClickable || box.fxTrackHover || box.fxCursor >= 0)
    cursorShape: box && box.fxCursor >= 0 ? box.fxCursor : box && box.fxClickable ? Qt.PointingHandCursor : undefined
    onHoveredChanged: if (box) box.hovered = hovered
}
