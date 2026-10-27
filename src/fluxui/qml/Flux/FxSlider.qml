// Control deslizante de FluxUI. En una columna ocupa todo el ancho.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

Slider {
    id: control
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

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
        color: fxtheme.border
        opacity: control.enabled ? 1 : 0.55

        Rectangle {
            // visualPosition ya va al revés en derecha a izquierda: el relleno sale del borde derecho.
            x: control.mirrored ? control.visualPosition * parent.width : 0
            width: (control.mirrored ? 1 - control.visualPosition : control.visualPosition) * parent.width
            height: parent.height
            radius: 2
            color: fxtheme.primary
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 18
        implicitHeight: 18
        radius: 9
        color: control.pressed ? Qt.tint(fxtheme.surface, fxtheme.pressed) : fxtheme.surface
        border.color: fxtheme.primary
        border.width: control.visualFocus ? 3 : 2
        opacity: control.enabled ? 1 : 0.55
    }
}
