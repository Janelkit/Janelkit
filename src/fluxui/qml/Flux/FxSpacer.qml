// Espacio flexible: empuja a los hermanos hacia los extremos del contenedor.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

Item {
    property int fxFlex: 1
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, false)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
}
