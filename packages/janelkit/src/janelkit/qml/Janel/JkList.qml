// Lista virtualizada de JanelKit: solo existen las filas visibles (más un margen).
// La genera <List>{#each ...}{/each}</List>. Por defecto ocupa el espacio libre (flex: 1).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

Item {
    id: root
    property alias model: view.model
    property alias delegate: view.delegate
    property alias gap: view.spacing
    property alias count: view.count
    readonly property alias view: view
    property real innerPadding: 0
    property real innerTopPadding: innerPadding
    property real innerRightPadding: innerPadding
    property real innerBottomPadding: innerPadding
    property real innerLeftPadding: innerPadding
    property color jkBackground: "transparent"
    property real jkRadius: 0
    property color jkBorderColor: "transparent"
    property real jkBorderWidth: 0
    property int jkFlex: 1
    readonly property bool jkScrollable: true
    // <List animate>: las filas aparecen, desaparecen y se recolocan con animación.
    property bool animate: false
    readonly property int jkAnimMs: 180
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false
    // <List follow>: empieza abajo, sigue a las filas nuevas si ya se estaba abajo y,
    // al insertar arriba (historial), mantiene en su sitio lo que se está viendo.
    property bool follow: false
    signal reachedTop()
    signal reachedBottom()
    // on:scroll: como mucho una vez por fotograma, {"top", "bottom", "y", "height"}.
    signal scrolled(var info)
    property bool jkScrollHandled: false
    function jkEmitScroll() {
        scrolled({ top: view.atYBeginning, bottom: view.atYEnd, y: view.contentY - view.originY, height: view.contentHeight })
    }

    // Para ref: lista.scroll_to_end(), scroll_to_start(), scroll_to(indice).
    function scrollToStart() { view.jkPosition(() => view.positionViewAtBeginning()) }
    function scrollToEnd() { view.jkToEnd() }
    function scrollTo(index) { view.jkPosition(() => view.positionViewAtIndex(index, ListView.Contain)) }

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, root, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    implicitWidth: 200
    implicitHeight: 200

    Rectangle {
        anchors.fill: parent
        color: root.jkBackground
        radius: root.jkRadius
        border.color: root.jkBorderColor
        border.width: root.jkBorderWidth
    }

    ListView {
        id: view
        anchors.fill: parent
        anchors.topMargin: root.innerTopPadding
        anchors.rightMargin: root.innerRightPadding
        anchors.bottomMargin: root.innerBottomPadding
        anchors.leftMargin: root.innerLeftPadding
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        add: Transition {
            enabled: root.animate
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: root.jkAnimMs; easing.type: Easing.OutCubic }
        }
        remove: Transition {
            enabled: root.animate
            NumberAnimation { property: "opacity"; to: 0; duration: root.jkAnimMs; easing.type: Easing.InCubic }
        }
        move: Transition {
            enabled: root.animate
            NumberAnimation { properties: "x,y"; duration: root.jkAnimMs; easing.type: Easing.OutCubic }
        }
        displaced: Transition {
            enabled: root.animate
            NumberAnimation { properties: "x,y"; duration: root.jkAnimMs; easing.type: Easing.OutCubic }
        }

        // ListView se queda anclado a las filas que ya mostraba: si se inserta algo
        // arriba estando al principio, la fila nueva quedaría fuera de la vista.
        // Con follow ese anclaje es justo lo que se quiere (cargar historial).
        property bool jkWasAtTop: true
        // follow: si el usuario está abajo, la vista se queda abajo aunque crezca el contenido.
        property bool jkStick: true
        property bool jkPositioning: false
        property int jkAnchorIndex: -1
        property real jkAnchorOffset: 0

        function jkToEnd() {
            jkPosition(() => positionViewAtEnd())
            jkStick = true
        }
        function jkRestoreAnchor() {
            const index = jkAnchorIndex
            jkAnchorIndex = -1
            if (index < 0 || index >= count) return
            jkPosition(() => {
                positionViewAtIndex(index, ListView.Beginning)
                const item = itemAtIndex(index)
                if (item) contentY = item.y - jkAnchorOffset
            })
        }
        // Colocación pedida por código: cancela la que estuviera pendiente (follow).
        function jkPosition(how) {
            jkPositioning = true
            forceLayout()
            how()
            jkPositioning = false
            jkPositioningLater.stop()
            jkStick = atYEnd
        }

        Connections {
            target: view.model
            ignoreUnknownSignals: true
            function onRowsAboutToBeInserted(parent, first, last) {
                view.jkWasAtTop = view.atYBeginning
                view.jkAnchorIndex = -1
                if (root.follow && !view.jkStick) {
                    // La fila que está arriba de la vista y a qué altura se ve, para devolverla a su sitio.
                    const index = view.indexAt(view.contentX + 1, view.contentY + 1)
                    const item = index >= 0 ? view.itemAtIndex(index) : null
                    if (item && first <= index) {
                        view.jkAnchorIndex = index
                        view.jkAnchorOffset = item.y - view.contentY
                    }
                }
            }
            function onRowsInserted(parent, first, last) {
                if (root.follow) {
                    if (view.jkStick) jkPositioningLater.restart()
                    else if (view.jkAnchorIndex >= 0) {
                        // Después de que el propio ListView procese la inserción.
                        view.jkAnchorIndex += last - first + 1
                        jkAnchorLater.restart()
                    }
                }
                else if (view.jkWasAtTop) view.positionViewAtBeginning()
            }
            // Muchos cambios a la vez (reordenar una tabla) llegan como un reinicio del modelo:
            // ListView volvería al principio. Se conserva la posición: la fila que estaba arriba
            // de la vista (por su número, como en un administrador de tareas) vuelve a su sitio.
            function onModelAboutToBeReset() {
                view.jkAnchorIndex = -1
                if (root.follow && view.jkStick) return
                const index = view.indexAt(view.contentX + 1, view.contentY + 1)
                const item = index > 0 ? view.itemAtIndex(index) : null
                if (item) {
                    view.jkAnchorIndex = index
                    view.jkAnchorOffset = item.y - view.contentY
                }
            }
            function onModelReset() {
                if (root.follow && view.jkStick) jkPositioningLater.restart()
                else if (view.jkAnchorIndex >= 0) jkAnchorLater.restart()  // después de que ListView procese el reinicio
            }
        }
        onContentYChanged: {
            if (root.follow && !jkPositioning && (!jkPositioningLater.running || moving)) jkStick = atYEnd
            if (root.jkScrollHandled) jkScrollLater.start()
        }
        onContentHeightChanged: {
            if (root.follow && jkStick && !jkPositioning) jkPositioningLater.restart()
            if (root.jkScrollHandled) jkScrollLater.start()
        }
        onHeightChanged: if (root.follow && jkStick && !jkPositioning) jkPositioningLater.restart()
        // Las filas nuevas cambian de altura al crearse: se recoloca al final una vez asentadas.
        // Temporizadores (y no Qt.callLater): mueren con la lista si se destruye antes.
        Timer { id: jkPositioningLater; interval: 0; onTriggered: view.jkToEnd() }
        Timer { id: jkAnchorLater; interval: 0; onTriggered: view.jkRestoreAnchor() }
        Timer { id: jkScrollLater; interval: 0; onTriggered: root.jkEmitScroll() }

        onAtYBeginningChanged: if (atYBeginning && count > 0 && contentHeight > height) root.reachedTop()
        onAtYEndChanged: if (atYEnd && count > 0 && contentHeight > height) root.reachedBottom()
    }
}
