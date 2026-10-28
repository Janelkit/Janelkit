// Barra de progreso de JanelKit: value entre 0 y max (por defecto 1). indeterminate: en curso, sin cifra.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

ProgressBar {
    id: control
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, control, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    from: 0
    to: 1

    background: Rectangle {
        implicitWidth: 180
        implicitHeight: 6
        radius: 3
        color: jktheme.border
    }

    contentItem: Item {
        implicitHeight: 6
        clip: true

        Rectangle {
            visible: !control.indeterminate
            // visualPosition ya va al revés en derecha a izquierda: el relleno sale del borde derecho.
            x: control.mirrored ? control.visualPosition * parent.width : 0
            width: (control.mirrored ? 1 - control.visualPosition : control.visualPosition) * parent.width
            height: parent.height
            radius: 3
            color: jktheme.primary
        }

        Rectangle {
            id: runner
            visible: control.indeterminate
            width: parent.width * 0.3
            height: parent.height
            radius: 3
            color: jktheme.primary
            NumberAnimation on x {
                running: control.indeterminate && control.visible
                from: -runner.width
                to: control.width
                duration: 1100
                loops: Animation.Infinite
            }
        }
    }
}
