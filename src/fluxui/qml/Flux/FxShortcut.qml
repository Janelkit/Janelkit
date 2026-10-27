// Atajo de teclado de FluxUI: <Shortcut keys="Ctrl+S" on:activate={guardar} />.
// No ocupa espacio: es un elemento invisible que solo escucha el teclado de su ventana.
import QtQuick

Item {
    id: root
    property string keys: ""
    property bool fxActive: true
    signal activated()

    visible: false
    width: 0
    height: 0

    Shortcut {
        sequences: root.keys ? [root.keys] : []
        enabled: root.fxActive && root.enabled
        onActivated: root.activated()
    }
}
