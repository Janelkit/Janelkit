// Texto seleccionable de un <Text selectable>: una copia de solo lectura encima del texto
// (que se vuelve transparente), con la que se selecciona con el ratón o el teclado y se
// copia con Ctrl+C. La crea Fx.textDecorations solo para esos textos; el <Text> sigue
// midiendo y colocándose como siempre.
import QtQuick

TextEdit {
    id: edit
    property Item label: null
    width: label ? label.width : 0
    height: label ? label.height : 0
    readOnly: true
    selectByMouse: true
    activeFocusOnTab: false
    persistentSelection: false
    // TextEdit no pone puntos suspensivos: con text-overflow: ellipsis, al menos corta en el borde.
    clip: label !== null && label.elide !== Text.ElideNone
    // TextEdit no tiene lineHeight: con line-height, el texto plano va como texto enriquecido
    // con el mismo interlineado (Qt lo calcula igual) para que la copia cuadre con el original.
    readonly property bool fxSpaced: label !== null && label.lineHeight !== 1 && label.textFormat === Text.PlainText
    text: !label ? "" : fxSpaced ? fxSpacedHtml(label.text, label.lineHeight) : label.text
    textFormat: !label ? TextEdit.PlainText : fxSpaced ? TextEdit.RichText : label.textFormat
    function fxSpacedHtml(t, factor) {
        const escaped = String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        return '<div style="white-space:pre-wrap; line-height:' + Math.round(factor * 100) + '%">' + escaped + "</div>"
    }
    font: label ? label.font : Qt.font({})
    color: label ? label.fxColor : "black"
    wrapMode: label ? label.wrapMode : TextEdit.Wrap
    horizontalAlignment: label ? label.horizontalAlignment : TextEdit.AlignLeft
    verticalAlignment: label ? label.verticalAlignment : TextEdit.AlignTop
    topPadding: label ? label.topPadding : 0
    leftPadding: label ? label.leftPadding : 0
    rightPadding: label ? label.rightPadding : 0
    bottomPadding: label ? label.bottomPadding : 0
    selectionColor: fxtheme.primary
    selectedTextColor: fxtheme.on_primary
    // Los enlaces siguen funcionando: on:link del <Text> o el navegador.
    onLinkActivated: (link) => label.linkActivated(link)
    HoverHandler { cursorShape: edit.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor }
    // Como en la web, un clic sin arrastrar (no selecciona nada) sigue pulsando la caja con
    // on:click que contiene el texto: el TextEdit se queda el ratón para seleccionar.
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: (point) => {
            if (edit.selectedText !== "" || edit.hoveredLink !== "") return
            let box = edit.label ? edit.label.parent : null
            while (box && !(box.fxClickable === true && box.enabled)) box = box.parent
            if (!box) return
            const at = edit.mapToItem(box, point.position.x, point.position.y)
            box.fxActivate(at.x, at.y, Qt.LeftButton)
        }
    }
}
