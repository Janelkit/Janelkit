// Control deslizante de JanelKit. En una columna ocupa todo el ancho.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

Slider {
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
    to: 100
    hoverEnabled: true

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 180
        implicitHeight: 4
        width: control.availableWidth
        height: implicitHeight
        radius: 2
        color: jktheme.border
        opacity: control.enabled ? 1 : 0.55

        Rectangle {
            // visualPosition ya va al revés en derecha a izquierda: el relleno sale del borde derecho.
            x: control.mirrored ? control.visualPosition * parent.width : 0
            width: (control.mirrored ? 1 - control.visualPosition : control.visualPosition) * parent.width
            height: parent.height
            radius: 2
            color: jktheme.primary
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 18
        implicitHeight: 18
        radius: 9
        color: control.pressed ? Qt.tint(jktheme.surface, jktheme.pressed) : jktheme.surface
        border.color: jktheme.primary
        border.width: control.visualFocus ? 3 : 2
        opacity: control.enabled ? 1 : 0.55
    }
}
