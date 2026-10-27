// Caja dispuesta por un layout de Qt (GridLayout, en C++): la vía rápida de Column, Row
// y <flex direction="column">. El compilador la elige solo si la caja y sus hijos usan
// lo que el layout sabe hacer igual que flex.js: dirección (sin -reverse), gap, padding,
// align-items/align-self (sin baseline), márgenes fijos, tamaños en px, mín./máx. y un
// solo hijo con flex (o solo Spacer). Lo demás (wrap, justify-content, order, márgenes
// auto, %, position, :first-child…) va con FxFlex. El aspecto y los eventos, en FxBox.qml.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

FxBox {
    id: box
    default property alias content: lay.data
    fxLay: lay
    readonly property bool fxQt: true  // flex.js: su mínimo de contenido se calcula al pedirlo
    // Dentro hay cajas con el motor de <flex> (o puede haberlas): flex.js las coloca al
    // colocar esta caja (settleQt). Lo pone el compilador.
    property bool fxDeep: false

    // Padding y gap por lado: NaN = el general (ver Fx.pad).
    readonly property real fxPadL: (isNaN(leftPadding) ? padding : leftPadding) + fxBorderLeftW
    readonly property real fxPadT: (isNaN(topPadding) ? padding : topPadding) + fxBorderTopW
    readonly property real fxPadH: fxPadL + (isNaN(rightPadding) ? padding : rightPadding) + fxBorderRightW
    readonly property real fxPadV: fxPadT + (isNaN(bottomPadding) ? padding : bottomPadding) + fxBorderBottomW
    implicitWidth: lay.implicitWidth + fxPadH
    implicitHeight: lay.implicitHeight + fxPadV

    GridLayout {
        id: lay
        // Lo que leen los hijos (fx.js): Layout.fill*/alignment salen de aquí.
        readonly property Item fxBox: box
        readonly property bool fxHorizontal: box.direction === "row" || box.direction === "row-reverse"
        readonly property int fxAlign: Fx.alignFlags(box.alignItems, fxHorizontal)
        readonly property bool fxStretch: box.alignItems === "stretch"
        flow: fxHorizontal ? GridLayout.LeftToRight : GridLayout.TopToBottom
        rowSpacing: isNaN(box.rowGap) ? box.gap : box.rowGap
        columnSpacing: isNaN(box.columnGap) ? box.gap : box.columnGap
        x: box.fxPadL
        y: box.fxPadT
        // Con espacio de sobra y ningún hijo que crezca, un layout de Qt separa los hijos;
        // en flexbox se quedan al principio. Por eso en el eje principal el layout no pasa
        // de su máximo (su tamaño natural si nadie crece; infinito si alguien crece).
        readonly property real fxAvailW: Math.max(0, box.width - box.fxPadH)
        readonly property real fxAvailH: Math.max(0, box.height - box.fxPadV)
        width: fxHorizontal ? Math.min(fxAvailW, Layout.maximumWidth) : fxAvailW
        height: fxHorizontal ? fxAvailH : Math.min(fxAvailH, Layout.maximumHeight)
        // visibility: hidden: el contenido sigue ocupando su sitio (visible no cambia).
        opacity: box.fxHidden ? 0 : 1
        enabled: !box.fxHidden
    }
}
