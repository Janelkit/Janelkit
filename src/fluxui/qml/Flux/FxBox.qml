// Caja de FluxUI: lo común a <flex>, Column y Row. Aquí están las propiedades de
// flexbox, el aspecto (fondo, bordes por lado, radios, recorte, desplazamiento), los
// estados, los eventos y la accesibilidad. A los hijos los coloca el tipo derivado:
// FxFlex.qml (el motor de flex.js, todo flexbox) o FxQtBox.qml (un layout de Qt, más
// rápido, para lo que este sabe hacer; lo elige el compilador).
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

Rectangle {
    id: box

    // -- flexbox ------------------------------------------------------------
    property string direction: "row"        // row | column | row-reverse | column-reverse
    property bool wrap: false
    property real gap: 0
    // Por lado: NaN = el de gap / padding (Fx.pad). Sin binding por lado.
    property real rowGap: NaN
    property real columnGap: NaN
    property string alignItems: "stretch"    // start | center | end | stretch | baseline ("" = Column/Row)
    property string justifyContent: "start"  // start | center | end | space-between | space-around | space-evenly
    property string alignContent: "stretch"
    property real padding: 0
    property real topPadding: NaN
    property real rightPadding: NaN
    property real bottomPadding: NaN
    property real leftPadding: NaN
    // Column/Row: valores por defecto de antes (bloques a lo ancho en columna, centrado en fila;
    // solo encoge lo que crece).
    property bool fxLegacy: false

    // -- aspecto ------------------------------------------------------------
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    // Bordes por lado (-1: el de border; color sin fijar: el de border). Los dibuja FxSides.
    property real fxBorderTop: -1
    property real fxBorderRight: -1
    property real fxBorderBottom: -1
    property real fxBorderLeft: -1
    property var fxBorderTopColor
    property var fxBorderRightColor
    property var fxBorderBottomColor
    property var fxBorderLeftColor
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
    property int fxCursor: -1               // cursor (Qt.CursorShape); -1: el de siempre

    // -- estados (pseudo-clases) --------------------------------------------
    property bool checked: false
    property bool selected: false
    property bool expanded: false
    // El compilador los activa cuando una regla usa :hover o :pressed.
    property bool fxTrackHover: false
    property bool fxTrackPress: false
    // Arrastrar y soltar (qt_backend/events.py): draggable, :dragging y :drag-over.
    property bool fxDraggable: false
    property bool fxDragging: false
    property bool fxDragOver: false
    property bool fxKeyDown: false
    // Lo que solo cambia en cajas interactivas no son bindings (cada uno cuesta memoria en
    // todas las cajas): los fijan FxTap, FxBlocker y FxRole, que solo existen en esas cajas.
    property bool fxPressed: false  // :pressed (puntero o Espacio)
    function fxSyncPressed() { fxPressed = (fxTap !== null && fxTap.pressed) || fxKeyDown || (fxBlocker !== null && fxBlocker.pressed) }
    readonly property bool fxSides: fxBorderTop >= 0 || fxBorderRight >= 0 || fxBorderBottom >= 0 || fxBorderLeft >= 0
    // Ancho de borde de cada lado: 0 en las cajas sin borde; con borde, Fx.flexDecorations
    // los enlaza a fxBorderTop… o a fxBorderWidth (bit D_BORDER de fxDecor).
    property real fxBorderTopW: 0
    property real fxBorderRightW: 0
    property real fxBorderBottomW: 0
    property real fxBorderLeftW: 0

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
    // todos los hijos cada vez que se añade uno). Con fxFill, el compilador lo fija también.
    property bool fillMain: false

    // -- motor (flex.js) ----------------------------------------------------
    readonly property bool fxIsFlex: true
    property Item fxLay: null  // donde van los hijos (lo fija FxFlex o FxQtBox)
    readonly property bool fxScrollable: fxOverflow === "auto" || fxOverflow === "scroll"
    property real fxMinW: 0
    property Item fxScroller: null
    property Item fxSideItem: null
    property Item fxShadowItem: null
    property Item fxBlocker: null
    property bool fxBorderBound: false  // fxBorder*W ya enlazados (Fx.flexDecorations)
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
    // Creados solo si hacen falta (Fx.flexDecorations): FxHover, FxTap, FxRole, FxTranslate.
    property QtObject fxHover: null
    property QtObject fxTap: null
    property QtObject fxRoleItem: null
    property QtObject fxTranslate: null
    // Qué decoraciones necesita la caja (bits de Fx.D_*): al cambiar, se crean las que falten.
    readonly property int fxDecor: (fxSides ? 1 : 0) | (fxShadow ? 2 : 0) | (fxOutlineWidth > 0 ? 4 : 0)
        | (fxPosition === "absolute" || fxPosition === "fixed" ? 8 : 0) | (fxScrollable ? 16 : 0)
        | (fxClickable || fxTrackHover || fxCursor >= 0 ? 32 : 0) | (fxClickable || fxTrackPress ? 64 : 0)
        | (fxAs !== "box" ? 128 : 0) | (fxTx !== 0 || fxTy !== 0 ? 256 : 0) | (fxSides || fxBorderWidth > 0 ? 512 : 0)

    // on:click: el contenedor entero se puede pulsar (tarjetas, filas de lista)
    property bool fxClickable: false
    property bool hovered: false  // lo fija FxHover
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

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    // Solo con el motor de <flex> (fxEngine): un layout de Qt lee los Layout.* por su cuenta.
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, box, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)

    // Resaltado por defecto al pasar el ratón, salvo que una regla :hover diga cómo se ve.
    color: fxHidden ? "transparent" : fxClickable && !fxTrackHover && hovered ? Qt.tint(fxBackground, fxtheme.hover) : fxBackground
    radius: fxRadius
    // Con un papel interactivo (o on:click) se usa con el teclado: Tab para llegar, Espacio o Intro para pulsar.
    // Foco con papel interactivo y anillo de foco (si ninguna regla fija outline): los fija FxRole.
    property bool fxKeyFocus: false
    property bool fxFocusRing: false
    border.color: fxFocusRing ? fxtheme.primary : fxBorderColor
    border.width: fxHidden ? 0 : fxFocusRing ? 2 : fxSides ? 0 : fxBorderWidth
    clip: fxOverflow === "hidden"
    activeFocusOnTab: fxTabIndex >= 0 || (fxTabIndex === -2 && fxAs !== "box" && ["button", "link", "checkbox", "switch"].indexOf(fxAs) >= 0)
    // Papel interactivo (accesibilidad y teclado) y manejadores del puntero: FxRole, FxHover y
    // FxTap, creados solo si la caja los usa (ver fxDecor).

    // flex.js es una biblioteca sin imports: los objetos adjuntos (Layout.*, LayoutMirroring)
    // se leen desde aquí.
    function fxLayoutOf(c) { return c.Layout }
    function fxMirrored() { return LayoutMirroring.enabled }

    onFxDecorChanged: Fx.flexDecorations(box)
    // fxListen fijado desde la etiqueta de un componente (FxRemote): cuando ya están fxOn y fxBridge.
    // Qt.callLater puede llegar con la caja ya destruida (página cerrada): sin contexto, ni fxevents.
    function fxRegister() { if (fxListen && typeof fxevents !== "undefined") fxevents.listen(box) }
    onFxListenChanged: Qt.callLater(fxRegister)
    Component.onCompleted: {
        if (fxDecor) Fx.flexDecorations(box)
        if (fxListen) fxevents.listen(box)
    }
}
