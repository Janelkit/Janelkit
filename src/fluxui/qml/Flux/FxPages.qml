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

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, pages, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)
}
