// outline de un <flex>: un anillo por fuera de la caja que no ocupa sitio (anillo de
// foco). Lo crea Jk.flexDecorations solo cuando se usa.
import QtQuick

Rectangle {
    property Item box: null
    readonly property bool jkDecoration: true  // events.py: no es destino del puntero
    readonly property real ring: box ? box.jkOutlineWidth + box.jkOutlineOffset : 0
    visible: box !== null && box.jkOutlineWidth > 0 && !box.jkHidden
    z: 2
    x: -ring
    y: -ring
    width: box ? box.width + 2 * ring : 0
    height: box ? box.height + 2 * ring : 0
    color: "transparent"
    border.width: box ? box.jkOutlineWidth : 0
    border.color: box ? box.jkOutlineColor : "transparent"
    radius: box && box.jkRadius > 0 ? box.jkRadius + ring : 0
}
