// box-shadow de un <flex>: un rectángulo desenfocado detrás de la caja (z negativo:
// Qt Quick dibuja esos hijos antes que su padre). Lo crea Fx.flexDecorations solo
// cuando se usa. Con overflow: hidden, la caja recorta su sombra.
import QtQuick
import QtQuick.Effects

Item {
    id: root
    property Item box: null
    readonly property bool fxDecoration: true  // events.py: no es destino del puntero
    readonly property real blur: box ? Math.max(0, box.fxShadowBlur) : 0
    readonly property real spread: box ? box.fxShadowSpread : 0
    visible: box !== null && box.fxShadow && !box.fxHidden
    z: -1
    x: (box ? box.fxShadowX : 0) - spread
    y: (box ? box.fxShadowY : 0) - spread
    width: box ? Math.max(0, box.width + 2 * spread) : 0
    height: box ? Math.max(0, box.height + 2 * spread) : 0

    Rectangle {
        id: shape
        anchors.fill: parent
        visible: root.blur <= 0
        layer.enabled: root.blur > 0
        color: root.box ? root.box.fxShadowColor : "transparent"
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
