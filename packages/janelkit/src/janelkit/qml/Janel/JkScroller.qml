// Zona de desplazamiento de un <flex> con overflow: auto o scroll. La crea
// Jk.flexDecorations y mueve dentro el contenido del <flex>; el motor (flex.js)
// da al contenido su tamaño completo en el eje principal.
import QtQuick
import QtQuick.Controls.Basic

Flickable {
    id: flick
    property Item box: null
    anchors.fill: parent
    clip: true
    contentWidth: box && box.jkLay ? box.jkLay.width : 0
    contentHeight: box && box.jkLay ? box.jkLay.height : 0
    boundsBehavior: Flickable.StopAtBounds
    readonly property bool jkAlways: box ? box.jkOverflow === "scroll" : false
    ScrollBar.vertical: ScrollBar {
        policy: flick.jkAlways ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
        visible: flick.jkAlways || flick.contentHeight > flick.height + 0.5
    }
    ScrollBar.horizontal: ScrollBar {
        policy: flick.jkAlways ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
        visible: flick.jkAlways || flick.contentWidth > flick.width + 0.5
    }
}
