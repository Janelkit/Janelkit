// Imagen de FluxUI. src: ruta relativa al .flux, ruta absoluta o URL (http:, qrc:, data:).
// fit: "contain" (por defecto) | "cover" | "fill" | "none".
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

Image {
    id: image
    property string src: ""
    property url fxBase: ""  // carpeta del .flux (la fija el compilador)
    property string fit: "contain"
    property string alt: ""  // texto alternativo para lectores de pantalla
    Accessible.role: Accessible.Graphic
    Accessible.name: alt
    Accessible.ignored: alt === ""
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, false)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: Fx.touch(parent, image, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)

    source: Fx.resolveUrl(fxBase, src)
    fillMode: fit === "cover" ? Image.PreserveAspectCrop
        : fit === "fill" ? Image.Stretch
        : fit === "none" ? Image.Pad
        : Image.PreserveAspectFit
    clip: fit === "cover" || fit === "none"
    smooth: true
    mipmap: true
}
