// Contenedor de páginas de JanelKit (<Pages stack={nav} />): muestra la página de arriba de la pila.
// Las páginas las crea Python (janelkit.pages) y las añade como hijas. Las coloca el motor
// de <flex> (flex.js, arrangePages): la visible ocupa todo el contenedor, salvo que su
// raíz diga otra cosa con CSS (width, height, max-width, margin, margin: 0 auto,
// align-self), como un bloque en una columna. Un StackLayout no admitía márgenes ni
// alineación.
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk
import "flex.js" as Flex

Item {
    id: pages
    property int currentIndex: -1
    readonly property int count: children.length
    // Atrás con Alt+← o el botón «atrás» del ratón: lo que no atendió un elemento de
    // dentro llega aquí (la pila más interna primero). Python decide si se puede volver.
    property bool jkCanGoBack: false
    signal jkBack()
    // <Pages transition:slide>: la página que entra se anima. Python pone la dirección
    // (1 adelante, -1 atrás, 0 otra) y aumenta jkShown cada vez que cambia la visible.
    property string jkTransition: ""
    property int jkTransitionMs: 200
    property int jkDirection: 0
    property int jkShown: 0
    onJkShownChanged: {
        const page = jkTransition && currentIndex >= 0 ? children[currentIndex] : null
        if (!page) return
        Flex.measure(pages)  // ya en su sitio: la animación termina donde la colocó el motor
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
        NumberAnimation { id: jkEnterOpacity; property: "opacity"; to: 1; duration: pages.jkTransitionMs; easing.type: Easing.OutCubic }
        NumberAnimation { id: jkEnterSlide; property: "x"; duration: pages.jkTransitionMs; easing.type: Easing.OutCubic }
        NumberAnimation { id: jkEnterScale; target: jkEnterSlide.target; property: "scale"; to: 1; duration: pages.jkTransitionMs; easing.type: Easing.OutCubic }
    }
    Keys.onPressed: (event) => {
        if (jkCanGoBack && ((event.key === Qt.Key_Left && (event.modifiers & Qt.AltModifier)) || event.key === Qt.Key_Back)) {
            event.accepted = true
            jkBack()
        }
    }
    TapHandler {
        acceptedButtons: Qt.BackButton
        enabled: pages.jkCanGoBack
        onTapped: pages.jkBack()
    }
    property int jkFlex: 1

    // -- como contenedor de sus páginas (protocolo de flex.js) ------------------
    // Las raíces de las páginas avisan aquí de sus cambios (Jk.touch, Jk.resized).
    readonly property Item jkBox: pages
    readonly property bool jkEngine: true
    readonly property bool jkHorizontal: false
    readonly property int jkAlign: 0
    readonly property bool jkPages: true
    readonly property var jkState: ({ queued: false, busy: false, stale: false })
    // Al encoger su fila, el mínimo es el contenido de la página visible (lo calcula
    // arrangePages), no su ancho natural: si no, una página con una rejilla que se
    // reparte en filas, o un tablero desplazable, no se estrecharía con la ventana.
    property real jkMinW: 0
    // Variables CSS y texto heredado: los de fuera (Jk.ctxOf se detiene en un jkBox).
    readonly property QtObject jkCtx: Jk.ctxOf(pages)
    function jkLayoutOf(c) { return c.Layout }
    onWidthChanged: Flex.schedule(pages)
    onHeightChanged: Flex.schedule(pages)
    // Solo se ve la página actual, ya (no al colocarse): quien cambia de página lo lee enseguida.
    function jkShowCurrent() {
        for (let i = 0; i < children.length; ++i) children[i].visible = i === currentIndex
        Flex.schedule(pages)
    }
    onCurrentIndexChanged: jkShowCurrent()
    onChildrenChanged: jkShowCurrent()
    onVisibleChanged: if (visible && jkState.stale) Flex.schedule(pages)
    onJkMinWChanged: Jk.resized(parent)
    Component.onCompleted: Flex.layoutNow(pages)
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, pages, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)
}
