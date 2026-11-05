// Mazo: muestra uno de sus hijos, que ocupa todo el sitio. Es la base de los elementos que
// montan componentes desde Python (janelkit.ext.Host), como <Pages> y <Sections> de
// janelkit-router: el anfitrión crea los hijos con Container.mount y elige el visible con
// currentIndex. Los coloca el motor de <flex> (flex.js, arrangeDeck): el visible ocupa todo
// el mazo, salvo que su raíz diga otra cosa con CSS (width, height, max-width, margin,
// margin: 0 auto, align-self), como un bloque en una columna. Un StackLayout no admitía
// márgenes ni alineación.
//
// Público para paquetes (docs/arquitectura.md): currentIndex, count, jkTransition,
// jkTransitionMs, jkDirection, jkShown. Lo demás es interno.
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk
import "flex.js" as Flex

Item {
    id: deck
    property int currentIndex: -1
    readonly property int count: children.length
    // transition:slide en un elemento basado en JkDeck: el hijo que entra se anima. Python pone
    // la dirección (1 adelante, -1 atrás, 0 otra) y aumenta jkShown cada vez que cambia el visible.
    property string jkTransition: ""
    property int jkTransitionMs: 200
    property int jkDirection: 0
    property int jkShown: 0
    onJkShownChanged: {
        const page = jkTransition && currentIndex >= 0 ? children[currentIndex] : null
        if (!page) return
        Flex.measure(deck)  // ya en su sitio: la animación termina donde la colocó el motor
        jkEnterOpacity.target = page
        jkEnterSlide.target = page
        jkEnterSlide.to = page.x
        page.opacity = 0
        page.x += jkTransition === "slide" ? jkDirection * 24 : 0
        page.scale = jkTransition === "scale" ? 0.96 : 1
        jkEnter.restart()
    }
    ParallelAnimation {
        id: jkEnter
        NumberAnimation { id: jkEnterOpacity; property: "opacity"; to: 1; duration: deck.jkTransitionMs; easing.type: Easing.OutCubic }
        NumberAnimation { id: jkEnterSlide; property: "x"; duration: deck.jkTransitionMs; easing.type: Easing.OutCubic }
        NumberAnimation { id: jkEnterScale; target: jkEnterSlide.target; property: "scale"; to: 1; duration: deck.jkTransitionMs; easing.type: Easing.OutCubic }
    }
    property int jkFlex: 1

    // -- como contenedor de sus hijos (protocolo de flex.js) --------------------
    // Las raíces de los hijos avisan aquí de sus cambios (Jk.touch, Jk.resized).
    readonly property Item jkBox: deck
    readonly property bool jkEngine: true
    readonly property bool jkHorizontal: false
    readonly property int jkAlign: 0
    readonly property bool jkDeck: true
    readonly property var jkState: ({ queued: false, busy: false, stale: false })
    // Al encoger su fila, el mínimo es el contenido del hijo visible (lo calcula
    // arrangeDeck), no su ancho natural: si no, una página con una rejilla que se
    // reparte en filas, o un tablero desplazable, no se estrecharía con la ventana.
    property real jkMinW: 0
    // Variables CSS y texto heredado: los de fuera (Jk.ctxOf se detiene en un jkBox).
    readonly property QtObject jkCtx: Jk.ctxOf(deck)
    function jkLayoutOf(c) { return c.Layout }
    onWidthChanged: Flex.schedule(deck)
    onHeightChanged: Flex.schedule(deck)
    // Solo se ve el hijo actual, ya (no al colocarse): quien lo cambia lo lee enseguida.
    function jkShowCurrent() {
        for (let i = 0; i < children.length; ++i) children[i].visible = i === currentIndex
        Flex.schedule(deck)
    }
    onCurrentIndexChanged: jkShowCurrent()
    onChildrenChanged: jkShowCurrent()
    onVisibleChanged: if (visible && jkState.stale) Flex.schedule(deck)
    onJkMinWChanged: Jk.resized(parent)
    Component.onCompleted: Flex.layoutNow(deck)
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, deck, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)
}
