// Zona de desplazamiento de un <flex> con overflow: auto o scroll. La crea
// Fx.flexDecorations y mueve dentro el contenido del <flex>; el motor (flex.js)
// da al contenido su tamaño completo en el eje principal.
import QtQuick
import QtQuick.Controls.Basic

Flickable {
    id: flick
    property Item box: null
    anchors.fill: parent
    clip: true
    contentWidth: box && box.fxLay ? box.fxLay.width : 0
    contentHeight: box && box.fxLay ? box.fxLay.height : 0
    boundsBehavior: Flickable.StopAtBounds
    readonly property bool fxAlways: box ? box.fxOverflow === "scroll" : false
    ScrollBar.vertical: ScrollBar {
        policy: flick.fxAlways ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
        visible: flick.fxAlways || flick.contentHeight > flick.height + 0.5
    }
    ScrollBar.horizontal: ScrollBar {
        policy: flick.fxAlways ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
        visible: flick.fxAlways || flick.contentWidth > flick.width + 0.5
    }
}
