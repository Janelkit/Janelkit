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
        property bool fxWasAtTop: true
        Connections {
            target: view.model
            ignoreUnknownSignals: true
            function onRowsAboutToBeInserted() { view.fxWasAtTop = view.atYBeginning }
            function onRowsInserted() { if (view.fxWasAtTop) view.positionViewAtBeginning() }
        }
    }
}
