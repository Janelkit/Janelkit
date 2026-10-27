// El elemento <flex> (y Column y Row cuando usan algo que un layout de Qt no sabe
// hacer: FxFlexColumn, FxFlexRow). La disposición la calcula flex.js (flexbox de CSS);
// el aspecto, los estados y los eventos están en FxBox.qml.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx
import "flex.js" as Flex

FxBox {
    id: box
    default property alias content: lay.data
    fxLay: lay
    readonly property var fxState: ({ queued: false, busy: false })  // flex.js: en cola / colocándose

    // Lo que cambia la disposición de los propios hijos.
    // El tamaño y el mínimo de contenido cambian a menudo: con manejadores, que no
    // vuelven a evaluar (ni a suscribir) todas las dependencias de un binding.
    onWidthChanged: Fx.resized(lay)
    onHeightChanged: Fx.resized(lay)
    onFxMinWChanged: Fx.resized(parent)
    readonly property bool fxSelfTouch: Fx.resized(lay, direction, wrap, gap, rowGap, columnGap,
        alignItems, justifyContent, alignContent, padding, topPadding, rightPadding, bottomPadding, leftPadding,
        fxBorderTopW, fxBorderRightW, fxBorderBottomW, fxBorderLeftW, fxLegacy, fxScrollable, fxFill,
        LayoutMirroring.enabled)
    Component.onCompleted: Flex.layoutNow(box)

    Item {
        id: lay
        // Lo que leen los hijos (fx.js) y el motor (flex.js).
        readonly property Item fxBox: box
        readonly property bool fxEngine: true  // los hijos avisan de sus cambios (Fx.touch)
        readonly property bool fxHorizontal: box.direction === "row" || box.direction === "row-reverse"
        readonly property int fxAlign: Fx.alignFlags(box.alignItems, fxHorizontal)
        readonly property bool fxStretch: box.alignItems === "stretch"
        width: box.width
        height: box.height
        // visibility: hidden: el contenido sigue ocupando su sitio (visible no cambia).
        opacity: box.fxHidden ? 0 : 1
        enabled: !box.fxHidden
        onChildrenChanged: Flex.schedule(box)
    }
}
