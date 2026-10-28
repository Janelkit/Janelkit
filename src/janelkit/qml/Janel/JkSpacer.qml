// Espacio flexible: empuja a los hermanos hacia los extremos del contenedor.
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk

Item {
    id: spacer
    property int jkFlex: 1
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, false, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, spacer, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)
}
