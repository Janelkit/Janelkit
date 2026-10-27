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
    // box-shadow (una sombra) y outline: decoraciones que no ocupan sitio.
    property bool fxShadow: false
    property real fxShadowX: 0
    property real fxShadowY: 0
    property real fxShadowBlur: 0
    property real fxShadowSpread: 0
    property color fxShadowColor: "transparent"
    property real fxOutlineWidth: 0
    property color fxOutlineColor: "transparent"
    property real fxOutlineOffset: 0
    // Alguna regla fija outline: sustituye al anillo de foco por defecto (el borde).
    property bool fxCustomOutline: false
    // transform: translate() (scale y rotate son scale y rotation de Qt; no afectan a la disposición)
    property real fxTx: 0
    property real fxTy: 0
    transform: Translate { x: box.fxTx; y: box.fxTy }
    property int fxCursor: -1               // cursor (Qt.CursorShape); -1: el de siempre

    // -- estados (pseudo-clases) --------------------------------------------
    property bool checked: false
    property bool selected: false
    property bool expanded: false
    // El compilador los activa cuando una regla usa :hover o :pressed.
    property bool fxTrackHover: false
    property bool fxTrackPress: false
    property bool fxKeyDown: false
    readonly property bool fxPressed: tap.pressed || fxKeyDown || (fxBlocker !== null && fxBlocker.pressed)
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
    property Item fxShadowItem: null
    property Item fxBlocker: null
    // Texto heredado y variables propias: el contexto propio (si la caja fija algo de eso)
    // o el de su contenedor (FxContext.qml).
    property QtObject fxOwnCtx: null
    // Componente cuya raíz es esta caja: clases puestas en la etiqueta (" a b "), que
    // activan las reglas del componente que las combinan con su clase (.boton.primary).
    property string fxInClass: ""
    property Item fxRemote: null  // su FxRemote: flex.js la coloca donde está él
    // Propiedades de hijo de <flex> poco usadas; las cajas las tienen declaradas para que
    // se puedan fijar desde la etiqueta de un componente (FxRemote.qml).
    property int fxOrder: 0
    property real fxShrink: NaN
    property real fxBasis: -2
    property real fxBasisPct: 0
    property real fxWidthPct: 0
    property real fxHeightPct: 0
    property int fxAutoMargin: 0
    property string fxPosition: ""   // position: "", "relative", "absolute", "fixed"
    property var fxTop
    property var fxRight
    property var fxBottom
    property var fxLeft
    readonly property QtObject fxCtx: fxOwnCtx ? fxOwnCtx : Fx.ctxOf(box)
    property Item fxOutlineItem: null

    // on:click: el contenedor entero se puede pulsar (tarjetas, filas de lista)
    property bool fxClickable: false
    readonly property bool hovered: hover.hovered
    // Activación: clic, Espacio/Intro según el papel, lector de pantalla o pruebas. Avisa a
    // on:click (events.py) con la posición del clic (x < 0: sin puntero, desde el teclado).
    signal clicked()
    property real fxClickX: -1
    property real fxClickY: -1
    property int fxClickButton: Qt.LeftButton
    function fxActivate(x, y, button) {
        fxClickX = x
        fxClickY = y
        fxClickButton = button
        clicked()
        fxClickX = -1
    }
    onClicked: if (fxOn && fxOn.click !== undefined) fxevents.click(box, fxClickX, fxClickY, fxClickButton)

    // -- eventos y accesibilidad (fase 3 de docs/flex.md) ---------------------
    // Eventos con propagación: {tipo: id del manejador} y el puente de la plantilla (events.py).
    property var fxOn: null
    property QtObject fxBridge: null
    property string fxRole: ""            // as: "" = automático (button con on:click, si no box)
    readonly property string fxAs: fxRole !== "" ? fxRole : fxClickable ? "button" : "box"
    property int fxTabIndex: -2           // tabindex: 0 en el orden de Tab, -1 solo por código; -2 sin fijar
    property bool disabled: false
    enabled: !disabled
    property bool fxPointerEvents: true   // pointer-events: none -> false
    property bool fxHidden: false         // visibility: hidden (ocupa su sitio sin verse)
    // Eventos que no son on:click (esos se leen de fxOn al hacer clic): el compilador lo activa.
    property bool fxListen: false
    // Las listas solo se evalúan si la caja tiene un papel (la mayoría son "box").
    readonly property bool fxSpaceActivates: fxAs !== "box" && ["button", "checkbox", "switch", "tab", "menuitem", "option"].indexOf(fxAs) >= 0
    readonly property bool fxEnterActivates: fxAs !== "box" && ["button", "link", "tab", "menuitem", "option"].indexOf(fxAs) >= 0

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

    // Resaltado por defecto al pasar el ratón, salvo que una regla :hover diga cómo se ve.
    color: fxHidden ? "transparent" : fxClickable && !fxTrackHover && hover.hovered ? Qt.tint(fxBackground, fxtheme.hover) : fxBackground
    radius: fxRadius
    // Con un papel interactivo (o on:click) se usa con el teclado: Tab para llegar, Espacio o Intro para pulsar.
    readonly property bool fxKeyFocus: fxAs !== "box" && activeFocus
    readonly property bool fxFocusRing: fxKeyFocus && !fxCustomOutline
    border.color: fxFocusRing ? fxtheme.primary : fxBorderColor
    border.width: fxHidden ? 0 : fxFocusRing ? 2 : fxSides ? 0 : fxBorderWidth
    clip: fxOverflow === "hidden"
    activeFocusOnTab: fxTabIndex >= 0 || (fxTabIndex === -2 && fxAs !== "box" && ["button", "link", "checkbox", "switch"].indexOf(fxAs) >= 0)
    // Como un botón: Intro pulsa al momento; Espacio, al soltarlo (mientras tanto, :pressed).
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space && fxSpaceActivates) {
            if (!event.isAutoRepeat) fxKeyDown = true
            event.accepted = true
        } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && fxEnterActivates) {
            box.fxActivate(-1, -1, Qt.LeftButton)
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space && fxKeyDown && !event.isAutoRepeat) {
            fxKeyDown = false
            box.fxActivate(-1, -1, Qt.LeftButton)
            event.accepted = true
        }
    }
    onActiveFocusChanged: if (!activeFocus) fxKeyDown = false
    Accessible.role: fxAs === "box" || fxAs === "button" ? Accessible.Button : ({
        "button": Accessible.Button, "link": Accessible.Link, "checkbox": Accessible.CheckBox,
        "switch": Accessible.CheckBox, "tab": Accessible.PageTab, "menuitem": Accessible.MenuItem,
        "option": Accessible.ListItem, "listitem": Accessible.ListItem, "list": Accessible.List,
        "menu": Accessible.PopupMenu, "tablist": Accessible.PageTabList, "dialog": Accessible.Dialog,
        "heading": Accessible.Heading, "region": Accessible.Pane,
    })[fxAs] || Accessible.Grouping
    Accessible.ignored: fxAs === "box"
    // checkable, checked y selected los añade el compilador solo a las cajas que los usan.
    Accessible.onPressAction: if (fxAs !== "box") box.fxActivate(-1, -1, Qt.LeftButton)
    Accessible.onToggleAction: if (Accessible.checkable) box.fxActivate(-1, -1, Qt.LeftButton)

    // flex.js es una biblioteca sin imports: los objetos adjuntos (Layout.*, LayoutMirroring)
    // se leen desde aquí.
    function fxLayoutOf(c) { return c.Layout }
    function fxMirrored() { return LayoutMirroring.enabled }

    onFxSidesChanged: Fx.flexDecorations(box)
    onFxScrollableChanged: Fx.flexDecorations(box)
    onFxShadowChanged: Fx.flexDecorations(box)
    onFxPositionChanged: Fx.flexDecorations(box)
    onFxOutlineWidthChanged: Fx.flexDecorations(box)
    // fxListen fijado desde la etiqueta de un componente (FxRemote): cuando ya están fxOn y fxBridge.
    function fxRegister() { if (fxListen) fxevents.listen(box) }
    onFxListenChanged: Qt.callLater(fxRegister)
    Component.onCompleted: {
        Fx.flexDecorations(box)
        Flex.layoutNow(box)
        if (fxListen) fxevents.listen(box)
    }

    HoverHandler {
        id: hover
        enabled: box.fxPointerEvents && (box.fxClickable || box.fxTrackHover || box.fxCursor >= 0)
        cursorShape: box.fxCursor >= 0 ? box.fxCursor : box.fxClickable ? Qt.PointingHandCursor : undefined
    }
    TapHandler {
        id: tap
        // Con FxBlocker (position absolute o fixed), el clic y el pulsado los lleva él: con
        // los dos, Qt deja pasar la pulsación a lo que hay debajo.
        enabled: box.fxPointerEvents && (box.fxClickable || box.fxTrackPress) && box.fxBlocker === null
        acceptedButtons: Qt.LeftButton
        onTapped: (eventPoint, button) => {
            if (box.fxClickable) box.fxActivate(eventPoint.position.x, eventPoint.position.y, button)
        }
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
        // visibility: hidden: el contenido sigue ocupando su sitio (visible no cambia).
        opacity: box.fxHidden ? 0 : 1
        enabled: !box.fxHidden
        onChildrenChanged: Flex.schedule(box)
    }
}
