// Mano sobre los enlaces de un <Text format="markdown"> o "html" (el texto en sí no
// captura el ratón). La crea Jk.textDecorations solo para esos textos.
import QtQuick

HoverHandler {
    property Item label: null
    enabled: label !== null && label.format !== "plain"
    cursorShape: label && label.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
}
