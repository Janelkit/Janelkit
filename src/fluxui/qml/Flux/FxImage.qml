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

    source: Fx.resolveUrl(fxBase, src)
    fillMode: fit === "cover" ? Image.PreserveAspectCrop
        : fit === "fill" ? Image.Stretch
        : fit === "none" ? Image.Pad
        : Image.PreserveAspectFit
    clip: fit === "cover" || fit === "none"
    smooth: true
    mipmap: true
}
