// Caja de FluxUI: el elemento <flex>, y la base de Column y Row (FxColumn/FxRow).
// La disposición la calcula flex.js (flexbox de CSS); aquí están el aspecto
// (fondo, bordes por lado, radios por esquina, recorte, desplazamiento) y lo que
// el motor y los hijos leen del contenedor.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx
import "flex.js" as Flex

Rectangle {
    id: box
    default property alias content: lay.data

    // -- flexbox ------------------------------------------------------------
    property string direction: "row"        // row | column | row-reverse | column-reverse
    property bool wrap: false
    property real gap: 0
    property real rowGap: gap
    property real columnGap: gap
    property string alignItems: "stretch"    // start | center | end | stretch | baseline ("" = Column/Row)
    property string justifyContent: "start"  // start | center | end | space-between | space-around | space-evenly
    property string alignContent: "stretch"
    property real padding: 0
    property real topPadding: padding
    property real rightPadding: padding
    property real bottomPadding: padding
    property real leftPadding: padding
    // Column/Row: valores por defecto de antes (bloques a lo ancho en columna, centrado en fila;
    // solo encoge lo que crece).
    property bool fxLegacy: false

    // -- aspecto ------------------------------------------------------------
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    // Bordes por lado (-1: el de border)
    property real fxBorderTop: -1
    property real fxBorderRight: -1
    property real fxBorderBottom: -1
    property real fxBorderLeft: -1
    property color fxBorderTopColor: fxBorderColor
    property color fxBorderRightColor: fxBorderColor
    property color fxBorderBottomColor: fxBorderColor
    property color fxBorderLeftColor: fxBorderColor
    property string fxOverflow: "visible"   // visible | hidden | auto | scroll
    readonly property bool fxSides: fxBorderTop >= 0 || fxBorderRight >= 0 || fxBorderBottom >= 0 || fxBorderLeft >= 0
    readonly property real fxBorderTopW: fxBorderTop >= 0 ? fxBorderTop : fxBorderWidth
    readonly property real fxBorderRightW: fxBorderRight >= 0 ? fxBorderRight : fxBorderWidth
    readonly property real fxBorderBottomW: fxBorderBottom >= 0 ? fxBorderBottom : fxBorderWidth
    readonly property real fxBorderLeftW: fxBorderLeft >= 0 ? fxBorderLeft : fxBorderWidth

    // -- como hijo de otro contenedor ---------------------------------------
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    // El tamaño viene de fuera aunque coincida con el natural (raíz de la ventana, fila de <List>).
    property bool fxSizedW: false
    property bool fxSizedH: false
    // Caja exterior de un componente (<Panel flex={1} />): su único hijo la ocupa entera.
    property bool fxFill: false
    // Algún hijo crece (flex). Lo calcula el motor en cada pasada (un binding recorrería
    // todos los hijos cada vez que se añade uno).
    property bool fillMain: fxFill

    // -- motor (flex.js) ----------------------------------------------------
    readonly property bool fxIsFlex: true
    readonly property Item fxLay: lay
    readonly property var fxState: ({ queued: false, busy: false })  // flex.js: en cola / colocándose
    readonly property bool fxScrollable: fxOverflow === "auto" || fxOverflow === "scroll"
    property real fxMinW: 0
    property Item fxScroller: null
    property Item fxSideItem: null

    // on:click: el contenedor entero se puede pulsar (tarjetas, filas de lista)
    property bool fxClickable: false
    readonly property bool hovered: hover.hovered
    signal clicked()

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: Fx.touch(parent, box, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)
    // Lo que cambia la disposición de los propios hijos.
    // El tamaño y el mínimo de contenido cambian a menudo: con manejadores, que no
    // vuelven a evaluar (ni a suscribir) todas las dependencias de un binding.
    onWidthChanged: Fx.resized(lay)
    onHeightChanged: Fx.resized(lay)
    onFxMinWChanged: Fx.resized(parent)
    readonly property bool fxSelfTouch: Fx.resized(lay, direction, wrap, rowGap, columnGap,
        alignItems, justifyContent, alignContent, topPadding, rightPadding, bottomPadding, leftPadding,
        fxBorderTopW, fxBorderRightW, fxBorderBottomW, fxBorderLeftW, fxLegacy, fxScrollable, fxFill,
        LayoutMirroring.enabled)

    color: fxClickable && hover.hovered ? Qt.tint(fxBackground, fxtheme.hover) : fxBackground
    radius: fxRadius
    // Con on:click se puede usar con el teclado: Tab para llegar, Espacio o Intro para pulsar.
    readonly property bool fxKeyFocus: fxClickable && activeFocus
    border.color: fxKeyFocus ? fxtheme.primary : fxBorderColor
    border.width: fxKeyFocus ? 2 : fxSides ? 0 : fxBorderWidth
    clip: fxOverflow === "hidden"
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

    // flex.js es una biblioteca sin imports: los objetos adjuntos (Layout.*, LayoutMirroring)
    // se leen desde aquí.
    function fxLayoutOf(c) { return c.Layout }
    function fxMirrored() { return LayoutMirroring.enabled }

    onFxSidesChanged: Fx.flexDecorations(box)
    onFxScrollableChanged: Fx.flexDecorations(box)
    Component.onCompleted: {
        Fx.flexDecorations(box)
        Flex.layoutNow(box)
    }

    HoverHandler {
        id: hover
        enabled: box.fxClickable
        cursorShape: Qt.PointingHandCursor
    }
    TapHandler {
        enabled: box.fxClickable
        onTapped: box.clicked()
    }

    Item {
        id: lay
        // Lo que leen los hijos (fx.js) y el motor (flex.js).
        readonly property Item fxBox: box
        readonly property bool fxHorizontal: box.direction === "row" || box.direction === "row-reverse"
        readonly property int fxAlign: Fx.alignFlags(box.alignItems, fxHorizontal)
        readonly property bool fxStretch: box.alignItems === "stretch"
        readonly property bool fxFill: box.fxFill
        readonly property real fxFlexUnit: 0
        readonly property real spacing: fxHorizontal ? box.columnGap : box.rowGap
        // Contenedores implícitos ({#if} con varios elementos): copian estos valores del padre.
        readonly property string fxDirection: box.direction
        readonly property string fxAlignItems: box.alignItems
        readonly property bool fxLegacy: box.fxLegacy
        width: box.width
        height: box.height
        onChildrenChanged: Flex.schedule(box)
    }
}
