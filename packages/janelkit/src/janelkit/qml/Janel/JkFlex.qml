// El elemento <flex> (y Column y Row cuando usan algo que un layout de Qt no sabe
// hacer: JkFlexColumn, JkFlexRow). La disposición la calcula flex.js (flexbox de CSS);
// el aspecto, los estados y los eventos están en JkBox.qml.
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk
import "flex.js" as Flex

JkBox {
    id: box
    default property alias content: lay.data
    jkLay: lay
    // flex.js: en cola / colocándose / sin colocar mientras estaba oculta
    readonly property var jkState: ({ queued: false, busy: false, stale: false })
    onVisibleChanged: if (visible && jkState.stale) Flex.schedule(box)

    // Lo que cambia la disposición de los propios hijos.
    // El tamaño y el mínimo de contenido cambian a menudo: con manejadores, que no
    // vuelven a evaluar (ni a suscribir) todas las dependencias de un binding.
    onWidthChanged: Jk.resized(lay)
    onHeightChanged: Jk.resized(lay)
    onJkMinWChanged: Jk.resized(parent)
    readonly property bool jkSelfTouch: Jk.resized(lay, direction, wrap, gap, rowGap, columnGap,
        alignItems, justifyContent, alignContent, padding, topPadding, rightPadding, bottomPadding, leftPadding,
        jkBorderTopW, jkBorderRightW, jkBorderBottomW, jkBorderLeftW, jkLegacy, jkScrollable, jkFill,
        LayoutMirroring.enabled)
    Component.onCompleted: Flex.layoutNow(box)

    Item {
        id: lay
        // Lo que leen los hijos (jk.js) y el motor (flex.js).
        readonly property Item jkBox: box
        readonly property bool jkEngine: true  // los hijos avisan de sus cambios (Jk.touch)
        readonly property bool jkHorizontal: box.direction === "row" || box.direction === "row-reverse"
        readonly property int jkAlign: Jk.alignFlags(box.alignItems, jkHorizontal)
        readonly property bool jkStretch: box.alignItems === "stretch"
        width: box.width
        height: box.height
        // visibility: hidden: el contenido sigue ocupando su sitio (visible no cambia).
        opacity: box.jkHidden ? 0 : 1
        enabled: !box.jkHidden
        onChildrenChanged: Flex.schedule(box)
    }
}
