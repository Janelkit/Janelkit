// box-shadow de un <flex>: un rectángulo desenfocado detrás de la caja (z negativo:
// Qt Quick dibuja esos hijos antes que su padre). Lo crea Jk.flexDecorations solo
// cuando se usa. Con overflow: hidden, la caja recorta su sombra.
import QtQuick
import QtQuick.Effects

Item {
    id: root
    property Item box: null
    readonly property bool jkDecoration: true  // events.py: no es destino del puntero
    readonly property real blur: box ? Math.max(0, box.jkShadowBlur) : 0
    readonly property real spread: box ? box.jkShadowSpread : 0
    visible: box !== null && box.jkShadow && !box.jkHidden
    z: -1
    x: (box ? box.jkShadowX : 0) - spread
    y: (box ? box.jkShadowY : 0) - spread
    width: box ? Math.max(0, box.width + 2 * spread) : 0
    height: box ? Math.max(0, box.height + 2 * spread) : 0

    Rectangle {
        id: shape
        anchors.fill: parent
        visible: root.blur <= 0
        layer.enabled: root.blur > 0
        color: root.box ? root.box.jkShadowColor : "transparent"
        topLeftRadius: root.box ? Math.max(0, root.box.topLeftRadius + root.spread) : 0
        topRightRadius: root.box ? Math.max(0, root.box.topRightRadius + root.spread) : 0
        bottomLeftRadius: root.box ? Math.max(0, root.box.bottomLeftRadius + root.spread) : 0
        bottomRightRadius: root.box ? Math.max(0, root.box.bottomRightRadius + root.spread) : 0
    }
    MultiEffect {
        anchors.fill: shape
        source: shape
        visible: root.blur > 0
        blurEnabled: true
        blur: 1.0
        blurMax: Math.max(1, Math.min(64, Math.round(root.blur)))
        autoPaddingEnabled: true
    }
}
