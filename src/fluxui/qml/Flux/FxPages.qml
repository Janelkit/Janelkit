// Contenedor de páginas de FluxUI (<Pages stack={nav} />): muestra la página de arriba de la pila.
// Las páginas las crea Python (fluxui.pages) y las añade como hijas. Las coloca el motor
// de <flex> (flex.js, arrangePages): la visible ocupa todo el contenedor, salvo que su
// raíz diga otra cosa con CSS (width, height, max-width, margin, margin: 0 auto,
// align-self), como un bloque en una columna. Un StackLayout no admitía márgenes ni
// alineación.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx
import "flex.js" as Flex

Item {
    id: pages
    property int currentIndex: -1
    readonly property int count: children.length
    // Atrás con Alt+← o el botón «atrás» del ratón: lo que no atendió un elemento de
    // dentro llega aquí (la pila más interna primero). Python decide si se puede volver.
    property bool fxCanGoBack: false
    signal fxBack()
    // <Pages transition:slide>: la página que entra se anima. Python pone la dirección
    // (1 adelante, -1 atrás, 0 otra) y aumenta fxShown cada vez que cambia la visible.
    property string fxTransition: ""
    property int fxTransitionMs: 200
    property int fxDirection: 0
    property int fxShown: 0
    onFxShownChanged: {
        const page = fxTransition && currentIndex >= 0 ? children[currentIndex] : null
        if (!page) return
        Flex.measure(pages)  // ya en su sitio: la animación termina donde la colocó el motor
        fxEnterOpacity.target = page
        fxEnterSlide.target = page
        fxEnterSlide.to = page.x
        page.opacity = 0
        page.x += fxTransition === "slide" ? fxDirection * 24 : 0
        page.scale = fxTransition === "scale" ? 0.96 : 1
        fxEnter.restart()
    }
    ParallelAnimation {
        id: fxEnter
        NumberAnimation { id: fxEnterOpacity; property: "opacity"; to: 1; duration: pages.fxTransitionMs; easing.type: Easing.OutCubic }
        NumberAnimation { id: fxEnterSlide; property: "x"; duration: pages.fxTransitionMs; easing.type: Easing.OutCubic }
        NumberAnimation { id: fxEnterScale; target: fxEnterSlide.target; property: "scale"; to: 1; duration: pages.fxTransitionMs; easing.type: Easing.OutCubic }
    }
    Keys.onPressed: (event) => {
        if (fxCanGoBack && ((event.key === Qt.Key_Left && (event.modifiers & Qt.AltModifier)) || event.key === Qt.Key_Back)) {
            event.accepted = true
            fxBack()
        }
    }
    TapHandler {
        acceptedButtons: Qt.BackButton
        enabled: pages.fxCanGoBack
        onTapped: pages.fxBack()
    }
    property int fxFlex: 1

    // -- como contenedor de sus páginas (protocolo de flex.js) ------------------
    // Las raíces de las páginas avisan aquí de sus cambios (Fx.touch, Fx.resized).
    readonly property Item fxBox: pages
    readonly property bool fxEngine: true
    readonly property bool fxHorizontal: false
    readonly property int fxAlign: 0
    readonly property bool fxPages: true
    readonly property var fxState: ({ queued: false, busy: false, stale: false })
    // Al encoger su fila, el mínimo es el contenido de la página visible (lo calcula
    // arrangePages), no su ancho natural: si no, una página con una rejilla que se
    // reparte en filas, o un tablero desplazable, no se estrecharía con la ventana.
    property real fxMinW: 0
    // Variables CSS y texto heredado: los de fuera (Fx.ctxOf se detiene en un fxBox).
    readonly property QtObject fxCtx: Fx.ctxOf(pages)
    function fxLayoutOf(c) { return c.Layout }
    onWidthChanged: Flex.schedule(pages)
    onHeightChanged: Flex.schedule(pages)
    // Solo se ve la página actual, ya (no al colocarse): quien cambia de página lo lee enseguida.
    function fxShowCurrent() {
        for (let i = 0; i < children.length; ++i) children[i].visible = i === currentIndex
        Flex.schedule(pages)
    }
    onCurrentIndexChanged: fxShowCurrent()
    onChildrenChanged: fxShowCurrent()
    onVisibleChanged: if (visible && fxState.stale) Flex.schedule(pages)
    onFxMinWChanged: Fx.resized(parent)
    Component.onCompleted: Flex.layoutNow(pages)
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, pages, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)
}
