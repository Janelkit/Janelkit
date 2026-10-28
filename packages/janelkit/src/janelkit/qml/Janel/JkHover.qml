// Ratón encima de una caja (:hover, on:click, cursor). Lo crea Jk.flexDecorations solo
// cuando la caja lo necesita; la caja lee `hovered` de aquí.
import QtQuick

HoverHandler {
    property Item box: null
    enabled: box !== null && box.jkPointerEvents && (box.jkClickable || box.jkTrackHover || box.jkCursor >= 0)
    cursorShape: box && box.jkCursor >= 0 ? box.jkCursor : box && box.jkClickable ? Qt.PointingHandCursor : undefined
    onHoveredChanged: if (box) box.hovered = hovered
}
