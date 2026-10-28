// Transición de entrada/salida de FluxUI (transition:fade, in:scale, out:slide…).
// La genera el compilador como hijo invisible de la raíz de un bloque {#if}/{#each}/{#key}.
// Entrada: al crearse. Salida: cuando el puente (fx) emite leave(); Python retira la fila
// cuando termina la animación. En {#hidden} (toggle): entra y sale cuando cambia `shown`,
// y es quien cambia `visible` de la raíz (al terminar la salida).
import QtQuick

Item {
    id: t
    visible: false
    width: 0
    height: 0

    property Item target: null
    property QtObject bridge: null
    property string enterKind: ""   // "" = sin animación de entrada
    property string leaveKind: ""
    property int enterMs: 200
    property int leaveMs: 200
    property bool toggle: false
    property bool shown: true
    readonly property real fxOffset: 12  // desplazamiento de slide, en píxeles

    onShownChanged: {
        if (!toggle || !target) return
        if (shown) {
            leave.stop()
            target.visible = true
            if (enterKind) { prepare(enterKind); enter.start() }
            else { target.opacity = 1; target.scale = 1; shift.y = 0 }
        } else {
            enter.stop()
            if (leaveKind) leave.start()
            else target.visible = false
        }
    }

    Translate { id: shift }

    function prepare(kind) {
        if (!target) return
        if (kind === "fade" || kind === "slide" || kind === "scale") target.opacity = 0
        if (kind === "scale") target.scale = 0.92
        if (kind === "slide") {
            target.transform = [shift]
            shift.y = -fxOffset
        }
    }

    Component.onCompleted: {
        if (enterKind && target) {
            prepare(enterKind)
            enter.start()
        }
    }

    Connections {
        target: t.bridge
        ignoreUnknownSignals: true
        function onLeave() { if (t.leaveKind && t.target) leave.start() }
    }

    ParallelAnimation {
        id: enter
        NumberAnimation { target: t.target; property: "opacity"; to: 1; duration: t.enterMs; easing.type: Easing.OutCubic }
        NumberAnimation { target: t.target; property: "scale"; to: 1; duration: t.enterMs; easing.type: Easing.OutCubic }
        NumberAnimation { target: shift; property: "y"; to: 0; duration: t.enterMs; easing.type: Easing.OutCubic }
    }

    ParallelAnimation {
        id: leave
        NumberAnimation { target: t.target; property: "opacity"; to: 0; duration: t.leaveMs; easing.type: Easing.InCubic }
        NumberAnimation {
            target: t.target; property: "scale"; duration: t.leaveMs; easing.type: Easing.InCubic
            to: t.leaveKind === "scale" ? 0.92 : 1
        }
        NumberAnimation {
            target: shift; property: "y"; duration: t.leaveMs; easing.type: Easing.InCubic
            to: t.leaveKind === "slide" ? -t.fxOffset : 0
        }
        onStarted: if (t.leaveKind === "slide" && t.target) t.target.transform = [shift]
        onFinished: if (t.toggle && !t.shown && t.target) t.target.visible = false
    }
}
