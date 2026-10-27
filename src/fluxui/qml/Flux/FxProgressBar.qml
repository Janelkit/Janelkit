// Barra de progreso de FluxUI: value entre 0 y max (por defecto 1). indeterminate: en curso, sin cifra.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

ProgressBar {
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
    to: 1

    background: Rectangle {
        implicitWidth: 180
        implicitHeight: 6
        radius: 3
        color: fxtheme.border
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
            color: fxtheme.primary
        }

        Rectangle {
            id: runner
            visible: control.indeterminate
            width: parent.width * 0.3
            height: parent.height
            radius: 3
            color: fxtheme.primary
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
