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

    // <window screen={i} fullscreen={bool}>: en qué pantalla y si ocupa la pantalla entera.
    // `screen` es el índice en `screens` o el nombre de la pantalla; si no existe (un proyector
    // desconectado), la ventana se queda donde está y vuelve a colocarse al conectarla.
    property var jkScreen: undefined
    property bool jkFullscreen: false
    onJkScreenChanged: jkPlace()
    onJkFullscreenChanged: jkPlace()
    Component.onCompleted: jkPlace()
    Connections {
        target: Qt.application
        function onScreensChanged() { jkPlace() }
    }

    function jkTargetScreen() {
        const list = Qt.application.screens
        if (typeof jkScreen === "number")
            return jkScreen >= 0 && jkScreen < list.length ? list[Math.floor(jkScreen)] : null
        if (typeof jkScreen === "string")
            for (let i = 0; i < list.length; i++)
                if (list[i].name === jkScreen) return list[i]
        return null
    }

    function jkPlace() {
        const target = jkTargetScreen()
        if (target !== null && screen.name !== target.name) {
            // Una ventana a pantalla completa no se mueve: sale, cambia de pantalla y vuelve.
            if (visibility === Window.FullScreen) showNormal()
            screen = target
            x = target.virtualX + Math.max(0, (target.width - width) / 2)
            y = target.virtualY + Math.max(0, (target.height - height) / 2)
        }
        if (jkFullscreen && visibility !== Window.FullScreen) showFullScreen()
        else if (!jkFullscreen && visibility === Window.FullScreen) showNormal()
    }

    // Disposición de <flex>: se calcula en la fase de polish, antes de cada fotograma.
    JkPolisher {
        onPolishing: Flex.flush()
        Component.onCompleted: Flex.registerPolisher(this)
        Component.onDestruction: Flex.unregisterPolisher(this)
    }
}
