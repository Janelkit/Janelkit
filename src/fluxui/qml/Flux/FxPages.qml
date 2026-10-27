// Contenedor de páginas de FluxUI (<Pages stack={nav} />): muestra la página de arriba de la pila.
// Las páginas las crea Python (fluxui.pages) y las añade como hijas; StackLayout las ajusta al tamaño.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

StackLayout {
    id: pages
    property int fxFlex: 1
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
}
