// Vídeo de JanelKit: muestra un Frames (janelkit/video.py) en una JkVideoSurface
// (qt_backend/video_surface.py: el fotograma como textura de Qt Quick, sin QtMultimedia).
// source: la parte Qt del Frames (attach/detach de la superficie).
// fit: "contain" (por defecto) | "cover" | "fill".
// La superficie y `overlay` ocupan el rectángulo de la imagen que se ve (jkContent): los
// hijos van en una caja <flex> con position: relative de ese tamaño, así que sus
// porcentajes (left: 25%) son de la imagen, no del elemento.
// Eventos de puntero (on:click, on:pointermove…): los entrega qt_backend/events.py, como en
// las cajas, y les añade image_x/image_y a partir de `jkSurface`.
import QtQuick
import QtQuick.Layouts
import JanelEngine
import "jk.js" as Jk

Item {
    id: video
    property var source: null
    property string fit: "contain"
    default property alias content: overlay.content
    Accessible.role: Accessible.Animation
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    implicitWidth: 320
    implicitHeight: 240
    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, false, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, video, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    clip: fit === "cover"

    // Dónde se ve la imagen: todo el elemento sin fotograma o con "fill"; si no, centrada y
    // escalada sin deformar, entera ("contain", con bandas) o llenándolo ("cover", recortada).
    readonly property real jkScale: output.sourceWidth <= 0 || output.sourceHeight <= 0 ? 0
        : fit === "cover" ? Math.max(width / output.sourceWidth, height / output.sourceHeight)
        : Math.min(width / output.sourceWidth, height / output.sourceHeight)
    readonly property rect jkContent: jkScale === 0 || fit === "fill" ? Qt.rect(0, 0, width, height)
        : Qt.rect((width - output.sourceWidth * jkScale) / 2, (height - output.sourceHeight * jkScale) / 2,
            output.sourceWidth * jkScale, output.sourceHeight * jkScale)

    // La superficie ocupa justo la imagen con cualquier `fit`: events.py pasa de su
    // rectángulo a píxeles de la imagen (image_x, image_y).
    readonly property Item jkSurface: output

    JkVideoSurface {
        id: output
        x: video.jkContent.x
        y: video.jkContent.y
        width: video.jkContent.width
        height: video.jkContent.height
    }

    JkFlex {
        id: overlay
        jkPosition: "relative"
        x: video.jkContent.x
        y: video.jkContent.y
        width: video.jkContent.width
        height: video.jkContent.height
    }

    // El Frames que se muestra: se engancha a la superficie y se suelta al cambiar o al destruirse.
    property var jkAttached: null
    function jkAttach() {
        if (jkAttached === source)
            return
        if (jkAttached)
            jkAttached.detach(output)
        jkAttached = source
        if (source)
            source.attach(output)
    }
    onSourceChanged: jkAttach()
    Component.onDestruction: if (jkAttached) jkAttached.detach(output)

    // -- eventos (como en JkBox) ---------------------
    // {tipo: id del manejador} y el puente de la plantilla; los fija el compilador.
    property var jkOn: null
    property QtObject jkBridge: null
    // Eventos que no son on:click (esos se leen de jkOn al hacer clic).
    property bool jkListen: false
    // on:click: lo emite este TapHandler (solo el ratón: <video> no se activa con el teclado).
    property bool jkClickable: false
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
    onClicked: if (jkOn && jkOn.click !== undefined) jkevents.click(video, jkClickX, jkClickY, jkClickButton)
    TapHandler {
        enabled: video.jkClickable
        acceptedButtons: Qt.LeftButton
        onTapped: (eventPoint, button) => video.jkActivate(eventPoint.position.x, eventPoint.position.y, button)
    }
    // Qt.callLater puede llegar con el vídeo ya destruido: sin contexto, ni jkevents.
    function jkRegister() { if (jkListen && typeof jkevents !== "undefined") jkevents.listen(video) }
    onJkListenChanged: Qt.callLater(jkRegister)

    Component.onCompleted: {
        jkAttach()
        if (jkListen) jkevents.listen(video)
    }
}
