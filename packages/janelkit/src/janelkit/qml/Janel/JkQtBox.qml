// Caja dispuesta por un layout de Qt (GridLayout, en C++): la vía rápida de Column, Row
// y <flex direction="column">. El compilador la elige solo si la caja y sus hijos usan
// lo que el layout sabe hacer igual que flex.js: dirección (sin -reverse), gap, padding,
// align-items/align-self (sin baseline), márgenes fijos, tamaños en px, mín./máx. y un
// solo hijo con flex (o solo Spacer). Lo demás (wrap, justify-content, order, márgenes
// auto, %, position, :first-child…) va con JkFlex. El aspecto y los eventos, en JkBox.qml.
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk

JkBox {
    id: box
    default property alias content: lay.data
    jkLay: lay
    readonly property bool jkQt: true  // flex.js: su mínimo de contenido se calcula al pedirlo
    // Dentro hay cajas con el motor de <flex> (o puede haberlas): flex.js las coloca al
    // colocar esta caja (settleQt). Lo pone el compilador.
    property bool jkDeep: false

    // Padding y gap por lado: NaN = el general (ver Jk.pad).
    readonly property real jkPadL: (isNaN(leftPadding) ? padding : leftPadding) + jkBorderLeftW
    readonly property real jkPadT: (isNaN(topPadding) ? padding : topPadding) + jkBorderTopW
    readonly property real jkPadH: jkPadL + (isNaN(rightPadding) ? padding : rightPadding) + jkBorderRightW
    readonly property real jkPadV: jkPadT + (isNaN(bottomPadding) ? padding : bottomPadding) + jkBorderBottomW
    implicitWidth: lay.implicitWidth + jkPadH
    implicitHeight: lay.implicitHeight + jkPadV

    GridLayout {
        id: lay
        // Lo que leen los hijos (jk.js): Layout.fill*/alignment salen de aquí.
        readonly property Item jkBox: box
        readonly property bool jkHorizontal: box.direction === "row" || box.direction === "row-reverse"
        readonly property int jkAlign: Jk.alignFlags(box.alignItems, jkHorizontal)
        readonly property bool jkStretch: box.alignItems === "stretch"
        flow: jkHorizontal ? GridLayout.LeftToRight : GridLayout.TopToBottom
        rowSpacing: isNaN(box.rowGap) ? box.gap : box.rowGap
        columnSpacing: isNaN(box.columnGap) ? box.gap : box.columnGap
        x: box.jkPadL
        y: box.jkPadT
        // Con espacio de sobra y ningún hijo que crezca, un layout de Qt separa los hijos;
        // en flexbox se quedan al principio. Por eso en el eje principal el layout no pasa
        // de su máximo (su tamaño natural si nadie crece; infinito si alguien crece).
        readonly property real jkAvailW: Math.max(0, box.width - box.jkPadH)
        readonly property real jkAvailH: Math.max(0, box.height - box.jkPadV)
        width: jkHorizontal ? Math.min(jkAvailW, Layout.maximumWidth) : jkAvailW
        height: jkHorizontal ? jkAvailH : Math.min(jkAvailH, Layout.maximumHeight)
        // visibility: hidden: el contenido sigue ocupando su sitio (visible no cambia).
        opacity: box.jkHidden ? 0 : 1
        enabled: !box.jkHidden
    }
}
