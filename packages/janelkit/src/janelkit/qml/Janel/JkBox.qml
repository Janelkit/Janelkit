// Caja de JanelKit: lo común a <flex>, Column y Row. Aquí están las propiedades de
// flexbox, el aspecto (fondo, bordes por lado, radios, recorte, desplazamiento), los
// estados, los eventos y la accesibilidad. A los hijos los coloca el tipo derivado:
// JkFlex.qml (el motor de flex.js, todo flexbox) o JkQtBox.qml (un layout de Qt, más
// rápido, para lo que este sabe hacer; lo elige el compilador).
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk

Rectangle {
    id: box

    // -- flexbox ------------------------------------------------------------
    property string direction: "row"        // row | column | row-reverse | column-reverse
    property bool wrap: false
    property real gap: 0
    // Por lado: NaN = el de gap / padding (Jk.pad). Sin binding por lado.
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
    property bool jkLegacy: false

    // -- aspecto ------------------------------------------------------------
    property color jkBackground: "transparent"
    property real jkRadius: 0
    property color jkBorderColor: "transparent"
    property real jkBorderWidth: 0
    // Bordes por lado (-1: el de border; color sin fijar: el de border). Los dibuja JkSides.
    property real jkBorderTop: -1
    property real jkBorderRight: -1
    property real jkBorderBottom: -1
    property real jkBorderLeft: -1
    property var jkBorderTopColor
    property var jkBorderRightColor
    property var jkBorderBottomColor
    property var jkBorderLeftColor
    property string jkOverflow: "visible"   // visible | hidden | auto | scroll
    // box-shadow (una sombra) y outline: decoraciones que no ocupan sitio.
    property bool jkShadow: false
    property real jkShadowX: 0
    property real jkShadowY: 0
    property real jkShadowBlur: 0
    property real jkShadowSpread: 0
    property color jkShadowColor: "transparent"
    property real jkOutlineWidth: 0
    property color jkOutlineColor: "transparent"
    property real jkOutlineOffset: 0
    // Alguna regla fija outline: sustituye al anillo de foco por defecto (el borde).
    property bool jkCustomOutline: false
    // transform: translate() (scale y rotate son scale y rotation de Qt; no afectan a la disposición)
    property real jkTx: 0
    property real jkTy: 0
    property int jkCursor: -1               // cursor (Qt.CursorShape); -1: el de siempre

    // -- estados (pseudo-clases) --------------------------------------------
    property bool checked: false
    property bool selected: false
    property bool expanded: false
    // El compilador los activa cuando una regla usa :hover o :pressed.
    property bool jkTrackHover: false
    property bool jkTrackPress: false
    // Arrastrar y soltar (qt_backend/events.py): draggable, :dragging y :drag-over.
    property bool jkDraggable: false
    property bool jkDragging: false
    property bool jkDragOver: false
    property bool jkKeyDown: false
    // Lo que solo cambia en cajas interactivas no son bindings (cada uno cuesta memoria en
    // todas las cajas): los fijan JkTap, JkBlocker y JkRole, que solo existen en esas cajas.
    property bool jkPressed: false  // :pressed (puntero o Espacio)
    function jkSyncPressed() { jkPressed = (jkTap !== null && jkTap.pressed) || jkKeyDown || (jkBlocker !== null && jkBlocker.pressed) }
    readonly property bool jkSides: jkBorderTop >= 0 || jkBorderRight >= 0 || jkBorderBottom >= 0 || jkBorderLeft >= 0
    // Ancho de borde de cada lado: 0 en las cajas sin borde; con borde, Jk.flexDecorations
    // los enlaza a jkBorderTop… o a jkBorderWidth (bit D_BORDER de jkDecor).
    property real jkBorderTopW: 0
    property real jkBorderRightW: 0
    property real jkBorderBottomW: 0
    property real jkBorderLeftW: 0

    // -- como hijo de otro contenedor ---------------------------------------
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false
    // El tamaño viene de fuera aunque coincida con el natural (raíz de la ventana, fila de <List>).
    property bool jkSizedW: false
    property bool jkSizedH: false
    // Caja exterior de un componente (<Panel flex={1} />): su único hijo la ocupa entera.
    property bool jkFill: false
    // Algún hijo crece (flex). Lo calcula el motor en cada pasada (un binding recorrería
    // todos los hijos cada vez que se añade uno). Con jkFill, el compilador lo fija también.
    property bool fillMain: false

    // -- motor (flex.js) ----------------------------------------------------
    readonly property bool jkIsFlex: true
    property Item jkLay: null  // donde van los hijos (lo fija JkFlex o JkQtBox)
    readonly property bool jkScrollable: jkOverflow === "auto" || jkOverflow === "scroll"
    property real jkMinW: 0
    property Item jkScroller: null
    property Item jkSideItem: null
    property Item jkShadowItem: null
    property Item jkBlocker: null
    property bool jkBorderBound: false  // jkBorder*W ya enlazados (Jk.flexDecorations)
    // Texto heredado y variables propias: el contexto propio (si la caja fija algo de eso)
    // o el de su contenedor (JkContext.qml).
    property QtObject jkOwnCtx: null
    // Componente cuya raíz es esta caja: clases puestas en la etiqueta (" a b "), que
    // activan las reglas del componente que las combinan con su clase (.boton.primary).
    property string jkInClass: ""
    property Item jkRemote: null  // su JkRemote: flex.js la coloca donde está él
    // Propiedades de hijo de <flex> poco usadas; las cajas las tienen declaradas para que
    // se puedan fijar desde la etiqueta de un componente (JkRemote.qml).
    property int jkOrder: 0
    property real jkShrink: NaN
    property real jkBasis: -2
    property real jkBasisPct: 0
    property real jkWidthPct: 0
    property real jkHeightPct: 0
    property int jkAutoMargin: 0
    property string jkPosition: ""   // position: "", "relative", "absolute", "fixed"
    property var jkTop
    property var jkRight
    property var jkBottom
    property var jkLeft
    readonly property QtObject jkCtx: jkOwnCtx ? jkOwnCtx : Jk.ctxOf(box)
    property Item jkOutlineItem: null
    // Creados solo si hacen falta (Jk.flexDecorations): JkHover, JkTap, JkRole, JkTranslate.
    property QtObject jkHover: null
    property QtObject jkTap: null
    property QtObject jkRoleItem: null
    property QtObject jkTranslate: null
    // Qué decoraciones necesita la caja (bits de Jk.D_*): al cambiar, se crean las que falten.
    readonly property int jkDecor: (jkSides ? 1 : 0) | (jkShadow ? 2 : 0) | (jkOutlineWidth > 0 ? 4 : 0)
        | (jkPosition === "absolute" || jkPosition === "fixed" ? 8 : 0) | (jkScrollable ? 16 : 0)
        | (jkClickable || jkTrackHover || jkCursor >= 0 ? 32 : 0) | (jkClickable || jkTrackPress ? 64 : 0)
        | (jkAs !== "box" ? 128 : 0) | (jkTx !== 0 || jkTy !== 0 ? 256 : 0) | (jkSides || jkBorderWidth > 0 ? 512 : 0)

    // on:click: el contenedor entero se puede pulsar (tarjetas, filas de lista)
    property bool jkClickable: false
    property bool hovered: false  // lo fija JkHover
    // Activación: clic, Espacio/Intro según el papel, lector de pantalla o pruebas. Avisa a
    // on:click (events.py) con la posición del clic (x < 0: sin puntero, desde el teclado).
    signal clicked()
    property real jkClickX: -1
    property real jkClickY: -1
    property int jkClickButton: Qt.LeftButton
    function jkActivate(x, y, button) {
        jkClickX = x
        jkClickY = y
        jkClickButton = button
        clicked()
        jkClickX = -1
    }
    onClicked: if (jkOn && jkOn.click !== undefined) jkevents.click(box, jkClickX, jkClickY, jkClickButton)

    // -- eventos y accesibilidad (fase 3 de docs/flex.md) ---------------------
    // Eventos con propagación: {tipo: id del manejador} y el puente de la plantilla (events.py).
    property var jkOn: null
    property QtObject jkBridge: null
    property string jkRole: ""            // as: "" = automático (button con on:click, si no box)
    readonly property string jkAs: jkRole !== "" ? jkRole : jkClickable ? "button" : "box"
    property int jkTabIndex: -2           // tabindex: 0 en el orden de Tab, -1 solo por código; -2 sin fijar
    property bool disabled: false
    enabled: !disabled
    property bool jkPointerEvents: true   // pointer-events: none -> false
    property bool jkHidden: false         // visibility: hidden (ocupa su sitio sin verse)
    // Eventos que no son on:click (esos se leen de jkOn al hacer clic): el compilador lo activa.
    property bool jkListen: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    // Solo con el motor de <flex> (jkEngine): un layout de Qt lee los Layout.* por su cuenta.
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, box, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    // Resaltado por defecto al pasar el ratón, salvo que una regla :hover diga cómo se ve.
    color: jkHidden ? "transparent" : jkClickable && !jkTrackHover && hovered ? Qt.tint(jkBackground, jktheme.hover) : jkBackground
    radius: jkRadius
    // Con un papel interactivo (o on:click) se usa con el teclado: Tab para llegar, Espacio o Intro para pulsar.
    // Foco con papel interactivo y anillo de foco (si ninguna regla fija outline): los fija JkRole.
    property bool jkKeyFocus: false
    property bool jkFocusRing: false
    border.color: jkFocusRing ? jktheme.primary : jkBorderColor
    border.width: jkHidden ? 0 : jkFocusRing ? 2 : jkSides ? 0 : jkBorderWidth
    clip: jkOverflow === "hidden"
    activeFocusOnTab: jkTabIndex >= 0 || (jkTabIndex === -2 && jkAs !== "box" && ["button", "link", "checkbox", "switch"].indexOf(jkAs) >= 0)
    // Papel interactivo (accesibilidad y teclado) y manejadores del puntero: JkRole, JkHover y
    // JkTap, creados solo si la caja los usa (ver jkDecor).

    // flex.js es una biblioteca sin imports: los objetos adjuntos (Layout.*, LayoutMirroring)
    // se leen desde aquí.
    function jkLayoutOf(c) { return c.Layout }
    function jkMirrored() { return LayoutMirroring.enabled }

    onJkDecorChanged: Jk.flexDecorations(box)
    // jkListen fijado desde la etiqueta de un componente (JkRemote): cuando ya están jkOn y jkBridge.
    // Qt.callLater puede llegar con la caja ya destruida (página cerrada): sin contexto, ni jkevents.
    function jkRegister() { if (jkListen && typeof jkevents !== "undefined") jkevents.listen(box) }
    onJkListenChanged: Qt.callLater(jkRegister)
    Component.onCompleted: {
        if (jkDecor) Jk.flexDecorations(box)
        if (jkListen) jkevents.listen(box)
    }
}
