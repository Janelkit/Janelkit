// Casilla de verificación de FluxUI.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

CheckBox {
    id: control
    property color fxColor: fxtheme.text
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, false)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    spacing: 8
    hoverEnabled: true

    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: fxtheme.radius_sm
        color: control.checked ? fxtheme.primary : fxtheme.surface
        border.color: control.checked || control.visualFocus ? fxtheme.primary : fxtheme.border
        border.width: control.visualFocus ? 2 : 1
        opacity: control.enabled ? 1 : 0.55

        Text {
            anchors.centerIn: parent
            text: "✓"
            visible: control.checked
            color: fxtheme.on_primary
            font.pixelSize: 13
            font.bold: true
        }
    }

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.fxColor
        opacity: control.enabled ? 1 : 0.55
        leftPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
    }
}
