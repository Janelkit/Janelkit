// Contenedor vertical de FluxUI: ColumnLayout con relleno, fondo, borde y radio.
// El layout interior solo ocupa todo el eje principal cuando algún hijo tiene
// flex; así el espacio sobrante no se reparte entre los hijos (como en CSS).
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

Rectangle {
    id: box
    default property alias content: lay.data
    property alias gap: lay.spacing
    property real padding: 0
    property real topPadding: padding
    property real rightPadding: padding
    property real bottomPadding: padding
    property real leftPadding: padding
    property int align: 0           // align-items (banderas Qt.Align*)
    property bool stretch: false    // align-items: stretch
    property real justify: 0        // justify-content: 0 inicio, 0.5 centro, 1 final
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    // Como hijo de otro contenedor
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    // El compilador los activa cuando el tamaño viene de fuera aunque no haya layout
    // (raíz de la ventana, fila de <List>): entonces se puede repartir el espacio por flex.
    property bool fxSizedW: false
    property bool fxSizedH: false
    // Caja exterior de un componente (<Panel flex={1} />): su único hijo la ocupa entera.
    property bool fxFill: false
    readonly property bool fillMain: fxFill || Fx.anyFlex(lay.children)
    // on:click: el contenedor entero se puede pulsar (tarjetas, filas de lista)
    property bool fxClickable: false
    readonly property bool hovered: hover.hovered
    signal clicked()

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    color: fxClickable && hover.hovered ? Qt.tint(fxBackground, fxtheme.hover) : fxBackground
    radius: fxRadius
    // Con on:click se puede usar con el teclado: Tab para llegar, Espacio o Intro para pulsar.
    readonly property bool fxKeyFocus: fxClickable && activeFocus
    border.color: fxKeyFocus ? fxtheme.primary : fxBorderColor
    border.width: fxKeyFocus ? 2 : fxBorderWidth
    activeFocusOnTab: fxClickable
    Keys.onPressed: (event) => {
        if (fxClickable && [Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter].includes(event.key)) {
            box.clicked()
            event.accepted = true
        }
    }
    Accessible.role: Accessible.Button
    Accessible.ignored: !fxClickable
    Accessible.onPressAction: if (fxClickable) box.clicked()
    implicitWidth: lay.implicitWidth + leftPadding + rightPadding
    implicitHeight: lay.implicitHeight + topPadding + bottomPadding

    HoverHandler {
        id: hover
        enabled: box.fxClickable
        cursorShape: Qt.PointingHandCursor
    }
    TapHandler {
        enabled: box.fxClickable
        onTapped: box.clicked()
    }

    ColumnLayout {
        id: lay
        readonly property bool fxHorizontal: false
        readonly property int fxAlign: box.align
        readonly property bool fxStretch: box.stretch
        readonly property bool fxFill: box.fxFill
        readonly property real fxFree: box.height - box.topPadding - box.bottomPadding
        readonly property real fxFlexUnit: box.Layout.fillHeight || box.fxSizedH ? Fx.flexUnit(lay, false, fxFree) : 0
        x: box.leftPadding
        y: box.topPadding + (box.fillMain ? 0 : Math.max(0, fxFree - implicitHeight) * box.justify)
        width: box.width - box.leftPadding - box.rightPadding
        height: box.fillMain ? fxFree : implicitHeight
        spacing: 0
    }
}
