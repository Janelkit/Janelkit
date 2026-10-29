// Vídeo de JanelKit: muestra un Frames (janelkit/video.py) con un VideoOutput de Qt.
// source: la parte Qt del Frames (attach/detach de un QVideoSink).
// fit: "contain" (por defecto) | "cover" | "fill".
// Los hijos van en `overlay`: una caja <flex> con position: relative del tamaño exacto de la
// imagen que se ve, así que sus porcentajes (left: 25%) son de la imagen, no del elemento.
import QtQuick
import QtQuick.Layouts
import QtMultimedia
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

    VideoOutput {
        id: output
        anchors.fill: parent
        fillMode: video.fit === "cover" ? VideoOutput.PreserveAspectCrop
            : video.fit === "fill" ? VideoOutput.Stretch
            : VideoOutput.PreserveAspectFit
    }

    JkFlex {
        id: overlay
        jkPosition: "relative"
        x: output.contentRect.x
        y: output.contentRect.y
        width: output.contentRect.width
        height: output.contentRect.height
    }

    // El Frames que se muestra: se engancha al sink de la vista y se suelta al cambiar o al destruirse.
    property var jkAttached: null
    function jkAttach() {
        if (jkAttached === source)
            return
        if (jkAttached)
            jkAttached.detach(output.videoSink)
        jkAttached = source
        if (source)
            source.attach(output.videoSink)
    }
    onSourceChanged: jkAttach()
    Component.onCompleted: jkAttach()
    Component.onDestruction: if (jkAttached) jkAttached.detach(output.videoSink)
}
