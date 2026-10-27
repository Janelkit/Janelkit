// Campo de texto de una línea de FluxUI.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

TextField {
    id: control
    property color fxColor: fxtheme.text
    property color fxBackground: fxtheme.surface
    property color fxBorderColor: fxtheme.border
    property real fxBorderWidth: 1
    property real fxRadius: fxtheme.radius
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    Accessible.name: placeholderText  // el atributo label la sustituye

    color: fxColor
    placeholderTextColor: fxtheme.text_muted
    selectionColor: fxtheme.primary
    selectedTextColor: fxtheme.on_primary
    padding: 8
    leftPadding: 10
    rightPadding: 10
    hoverEnabled: true

    background: Rectangle {
        implicitWidth: 180
        implicitHeight: 34
        radius: control.fxRadius
        color: control.fxBackground
        border.color: control.activeFocus ? fxtheme.primary : control.fxBorderColor
        border.width: control.activeFocus ? 2 : control.fxBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }
}
