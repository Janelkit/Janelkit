// Columna con desplazamiento vertical. Por defecto ocupa el espacio libre (flex: 1).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

ScrollView {
    id: sv
    default property alias content: col.content
    property alias gap: col.gap
    property alias innerPadding: col.padding
    property alias innerTopPadding: col.topPadding
    property alias innerRightPadding: col.rightPadding
    property alias innerBottomPadding: col.bottomPadding
    property alias innerLeftPadding: col.leftPadding
    property alias alignItems: col.alignItems
    property alias justifyContent: col.justifyContent
    property color jkBackground: "transparent"
    property real jkRadius: 0
    property color jkBorderColor: "transparent"
    property real jkBorderWidth: 0
    property int jkFlex: 1
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)

    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight
    readonly property bool jkScrollable: true
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, sv, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)
    contentWidth: availableWidth
    clip: true
    background: Rectangle {
        color: sv.jkBackground
        radius: sv.jkRadius
        border.color: sv.jkBorderColor
        border.width: sv.jkBorderWidth
    }

    JkFlexColumn {
        id: col
        width: sv.availableWidth
        jkSizedW: true
    }

    // Desplazamiento desde el código y avisos, como en <List>.
    // follow: empieza abajo y, si el usuario está abajo, se queda abajo aunque crezca el contenido.
    property bool follow: false
    signal reachedTop()
    signal reachedBottom()
    // on:scroll: como mucho una vez por fotograma, {"top", "bottom", "y", "height"}.
    signal scrolled(var info)
    property bool jkScrollHandled: false
    readonly property Flickable jkFlick: contentItem
    property bool jkStick: true
    property bool jkPositioning: false

    function jkEmitScroll() {
        const f = jkFlick
        scrolled({ top: f.atYBeginning, bottom: f.atYEnd, y: f.contentY - f.originY, height: f.contentHeight })
    }
    function jkSetY(y) {
        const f = jkFlick
        jkPositioning = true
        f.contentY = Math.max(f.originY, Math.min(y, f.originY + f.contentHeight - f.height))
        jkPositioning = false
        jkPositioningLater.stop()
        jkStick = f.atYEnd
    }
    // Para ref: zona.scroll_to_start(), scroll_to_end(), scroll_to(ref de un elemento de dentro).
    function scrollToStart() { jkSetY(jkFlick.originY) }
    function scrollToEnd() { jkSetY(jkFlick.originY + jkFlick.contentHeight); jkStick = true }
    function scrollTo(target) {
        const f = jkFlick
        const top = target.mapToItem(f.contentItem, 0, 0).y
        if (top < f.contentY) jkSetY(top)
        else if (top + target.height > f.contentY + f.height) jkSetY(top + target.height - f.height)
    }

    Connections {
        target: sv.jkFlick
        function onContentYChanged() {
            if (sv.follow && !sv.jkPositioning && (!jkPositioningLater.running || sv.jkFlick.moving))
                sv.jkStick = sv.jkFlick.atYEnd
            if (sv.jkScrollHandled) jkScrollLater.start()
        }
        function onContentHeightChanged() {
            if (sv.follow && sv.jkStick && !sv.jkPositioning) jkPositioningLater.restart()
            if (sv.jkScrollHandled) jkScrollLater.start()
        }
        function onHeightChanged() {
            if (sv.follow && sv.jkStick && !sv.jkPositioning) jkPositioningLater.restart()
        }
        function onAtYBeginningChanged() {
            if (sv.jkFlick.atYBeginning && sv.jkFlick.contentHeight > sv.jkFlick.height) sv.reachedTop()
        }
        function onAtYEndChanged() {
            if (sv.jkFlick.atYEnd && sv.jkFlick.contentHeight > sv.jkFlick.height) sv.reachedBottom()
        }
    }
    // Temporizadores (y no Qt.callLater): mueren con la zona si se destruye antes.
    Timer { id: jkPositioningLater; interval: 0; onTriggered: sv.scrollToEnd() }
    Timer { id: jkScrollLater; interval: 0; onTriggered: sv.jkEmitScroll() }
}
