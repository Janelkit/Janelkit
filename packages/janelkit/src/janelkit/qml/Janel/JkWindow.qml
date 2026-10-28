// Ventana raíz de JanelKit: colores, paleta y tipografía ligados a los tokens del tema.
import QtQuick
import QtQuick.Controls.Basic
import JanelEngine
import "flex.js" as Flex

ApplicationWindow {
    visible: true
    width: 640
    height: 480
    color: jktheme.bg
    font.family: jktheme.font_family
    font.pixelSize: jktheme.font_size
    palette.window: jktheme.bg
    palette.windowText: jktheme.text
    palette.base: jktheme.surface
    palette.alternateBase: jktheme.surface_alt
    palette.text: jktheme.text
    palette.button: jktheme.surface
    palette.buttonText: jktheme.text
    palette.highlight: jktheme.primary
    palette.highlightedText: jktheme.on_primary
    palette.placeholderText: jktheme.text_muted
    palette.mid: jktheme.border
    palette.dark: jktheme.text_muted
    palette.light: jktheme.surface_alt

    // Disposición de <flex>: se calcula en la fase de polish, antes de cada fotograma.
    JkPolisher {
        onPolishing: Flex.flush()
        Component.onCompleted: Flex.registerPolisher(this)
        Component.onDestruction: Flex.unregisterPolisher(this)
    }
}
