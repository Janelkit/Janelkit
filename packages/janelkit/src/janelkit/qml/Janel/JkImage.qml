// Imagen de JanelKit. src: ruta relativa al .janel, ruta absoluta o URL (http:, qrc:, data:).
// fit: "contain" (por defecto) | "cover" | "fill" | "none".
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk

Image {
    id: image
    property string src: ""
    property url jkBase: ""  // carpeta del .janel (la fija el compilador)
    property string fit: "contain"
    property string alt: ""  // texto alternativo para lectores de pantalla
    Accessible.role: Accessible.Graphic
    Accessible.name: alt
    Accessible.ignored: alt === ""
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, false, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, image, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    source: Jk.resolveUrl(jkBase, src)
    fillMode: fit === "cover" ? Image.PreserveAspectCrop
        : fit === "fill" ? Image.Stretch
        : fit === "none" ? Image.Pad
        : Image.PreserveAspectFit
    clip: fit === "cover" || fit === "none"
    smooth: true
    mipmap: true
}
