// Texto de FluxUI: color del tema, ajuste de línea y comportamiento de bloque en columnas.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

Label {
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    property color fxColor: fxtheme.text

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)

    color: fxColor
    wrapMode: Text.Wrap
}
