// Lista virtualizada de FluxUI: solo existen las filas visibles (más un margen).
// La genera <List>{#each ...}{/each}</List>. Por defecto ocupa el espacio libre (flex: 1).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

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
    property color fxBackground: "transparent"
    property real fxRadius: 0
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    property int fxFlex: 1
    // <List animate>: las filas aparecen, desaparecen y se recolocan con animación.
    property bool animate: false
    readonly property int fxAnimMs: 180
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    // <List follow>: empieza abajo, sigue a las filas nuevas si ya se estaba abajo y,
    // al insertar arriba (historial), mantiene en su sitio lo que se está viendo.
    property bool follow: false
    signal reachedTop()
    signal reachedBottom()
    // on:scroll: como mucho una vez por fotograma, {"top", "bottom", "y", "height"}.
    signal scrolled(var info)
    property bool fxScrollHandled: false
    function fxEmitScroll() {
        scrolled({ top: view.atYBeginning, bottom: view.atYEnd, y: view.contentY - view.originY, height: view.contentHeight })
    }

    // Para ref: lista.scroll_to_end(), scroll_to_start(), scroll_to(indice).
    function scrollToStart() { view.fxPosition(() => view.positionViewAtBeginning()) }
    function scrollToEnd() { view.fxToEnd() }
    function scrollTo(index) { view.fxPosition(() => view.positionViewAtIndex(index, ListView.Contain)) }

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    implicitWidth: 200
    implicitHeight: 200

    Rectangle {
        anchors.fill: parent
        color: root.fxBackground
        radius: root.fxRadius
        border.color: root.fxBorderColor
        border.width: root.fxBorderWidth
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
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: root.fxAnimMs; easing.type: Easing.OutCubic }
        }
        remove: Transition {
            enabled: root.animate
            NumberAnimation { property: "opacity"; to: 0; duration: root.fxAnimMs; easing.type: Easing.InCubic }
        }
        move: Transition {
            enabled: root.animate
            NumberAnimation { properties: "x,y"; duration: root.fxAnimMs; easing.type: Easing.OutCubic }
        }
        displaced: Transition {
            enabled: root.animate
            NumberAnimation { properties: "x,y"; duration: root.fxAnimMs; easing.type: Easing.OutCubic }
        }

        // ListView se queda anclado a las filas que ya mostraba: si se inserta algo
        // arriba estando al principio, la fila nueva quedaría fuera de la vista.
        // Con follow ese anclaje es justo lo que se quiere (cargar historial).
        property bool fxWasAtTop: true
        // follow: si el usuario está abajo, la vista se queda abajo aunque crezca el contenido.
        property bool fxStick: true
        property bool fxPositioning: false
        property int fxAnchorIndex: -1
        property real fxAnchorOffset: 0

        function fxToEnd() {
            fxPosition(() => positionViewAtEnd())
            fxStick = true
        }
        function fxRestoreAnchor() {
            const index = fxAnchorIndex
            fxAnchorIndex = -1
            if (index < 0 || index >= count) return
            fxPosition(() => {
                positionViewAtIndex(index, ListView.Beginning)
                const item = itemAtIndex(index)
                if (item) contentY = item.y - fxAnchorOffset
            })
        }
        // Colocación pedida por código: cancela la que estuviera pendiente (follow).
        function fxPosition(how) {
            fxPositioning = true
            forceLayout()
            how()
            fxPositioning = false
            fxPositioningLater.stop()
            fxStick = atYEnd
        }

        Connections {
            target: view.model
            ignoreUnknownSignals: true
            function onRowsAboutToBeInserted(parent, first, last) {
                view.fxWasAtTop = view.atYBeginning
                view.fxAnchorIndex = -1
                if (root.follow && !view.fxStick) {
                    // La fila que está arriba de la vista y a qué altura se ve, para devolverla a su sitio.
                    const index = view.indexAt(view.contentX + 1, view.contentY + 1)
                    const item = index >= 0 ? view.itemAtIndex(index) : null
                    if (item && first <= index) {
                        view.fxAnchorIndex = index
                        view.fxAnchorOffset = item.y - view.contentY
                    }
                }
            }
            function onRowsInserted(parent, first, last) {
                if (root.follow) {
                    if (view.fxStick) fxPositioningLater.restart()
                    else if (view.fxAnchorIndex >= 0) {
                        // Después de que el propio ListView procese la inserción.
                        view.fxAnchorIndex += last - first + 1
                        fxAnchorLater.restart()
                    }
                }
                else if (view.fxWasAtTop) view.positionViewAtBeginning()
            }
            function onModelReset() { if (root.follow && view.fxStick) fxPositioningLater.restart() }
        }
        onContentYChanged: {
            if (root.follow && !fxPositioning && (!fxPositioningLater.running || moving)) fxStick = atYEnd
            if (root.fxScrollHandled) fxScrollLater.start()
        }
        onContentHeightChanged: {
            if (root.follow && fxStick && !fxPositioning) fxPositioningLater.restart()
            if (root.fxScrollHandled) fxScrollLater.start()
        }
        onHeightChanged: if (root.follow && fxStick && !fxPositioning) fxPositioningLater.restart()
        // Las filas nuevas cambian de altura al crearse: se recoloca al final una vez asentadas.
        // Temporizadores (y no Qt.callLater): mueren con la lista si se destruye antes.
        Timer { id: fxPositioningLater; interval: 0; onTriggered: view.fxToEnd() }
        Timer { id: fxAnchorLater; interval: 0; onTriggered: view.fxRestoreAnchor() }
        Timer { id: fxScrollLater; interval: 0; onTriggered: root.fxEmitScroll() }

        onAtYBeginningChanged: if (atYBeginning && count > 0 && contentHeight > height) root.reachedTop()
        onAtYEndChanged: if (atYEnd && count > 0 && contentHeight > height) root.reachedBottom()
    }
}
