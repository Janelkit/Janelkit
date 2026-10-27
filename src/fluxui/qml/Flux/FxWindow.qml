// Ventana raíz de FluxUI: colores, paleta y tipografía ligados a los tokens del tema.
import QtQuick
import QtQuick.Controls.Basic
import FluxEngine
import "flex.js" as Flex

ApplicationWindow {
    visible: true
    width: 640
    height: 480
    color: fxtheme.bg
    font.family: fxtheme.font_family
    font.pixelSize: fxtheme.font_size
    palette.window: fxtheme.bg
    palette.windowText: fxtheme.text
    palette.base: fxtheme.surface
    palette.alternateBase: fxtheme.surface_alt
    palette.text: fxtheme.text
    palette.button: fxtheme.surface
    palette.buttonText: fxtheme.text
    palette.highlight: fxtheme.primary
    palette.highlightedText: fxtheme.on_primary
    palette.placeholderText: fxtheme.text_muted
    palette.mid: fxtheme.border
    palette.dark: fxtheme.text_muted
    palette.light: fxtheme.surface_alt

    // Disposición de <flex>: se calcula en la fase de polish, antes de cada fotograma.
    FxPolisher {
        onPolishing: Flex.flush()
        Component.onCompleted: Flex.registerPolisher(this)
        Component.onDestruction: Flex.unregisterPolisher(this)
    }
}
