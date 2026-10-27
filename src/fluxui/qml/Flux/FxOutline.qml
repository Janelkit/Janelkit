// outline de un <flex>: un anillo por fuera de la caja que no ocupa sitio (anillo de
// foco). Lo crea Fx.flexDecorations solo cuando se usa.
import QtQuick

Rectangle {
    property Item box: null
    readonly property bool fxDecoration: true  // events.py: no es destino del puntero
    readonly property real ring: box ? box.fxOutlineWidth + box.fxOutlineOffset : 0
    visible: box !== null && box.fxOutlineWidth > 0 && !box.fxHidden
    z: 2
    x: -ring
    y: -ring
    width: box ? box.width + 2 * ring : 0
    height: box ? box.height + 2 * ring : 0
    color: "transparent"
    border.width: box ? box.fxOutlineWidth : 0
    border.color: box ? box.fxOutlineColor : "transparent"
    radius: box && box.fxRadius > 0 ? box.fxRadius + ring : 0
}
