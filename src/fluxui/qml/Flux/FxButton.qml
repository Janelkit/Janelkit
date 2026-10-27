// Botón de FluxUI. variant: "default" | "primary" | "danger" | "ghost".
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

Button {
    id: control
    property string variant: "default"
    readonly property bool fxGhost: variant === "ghost" || flat
    property color fxBackground: fxGhost ? "transparent"
        : variant === "primary" ? fxtheme.primary
        : variant === "danger" ? fxtheme.danger
        : fxtheme.surface
    property color fxColor: fxGhost ? fxtheme.text
        : variant === "primary" ? fxtheme.on_primary
        : variant === "danger" ? fxtheme.on_danger
        : fxtheme.text
    property color fxBorderColor: variant === "default" && !fxGhost ? fxtheme.border : "transparent"
    property real fxBorderWidth: 1
    property real fxRadius: fxtheme.radius
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
    readonly property bool fxTouch: Fx.touch(parent, control, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)
    Accessible.name: text  // el atributo label la sustituye

    padding: 8
    leftPadding: 14
    rightPadding: 14
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.fxColor
        opacity: control.enabled ? 1 : 0.55
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitWidth: control.fxGhost ? 0 : 64  // los botones fantasma (iconos, emojis) pueden ser estrechos
        implicitHeight: 34
        radius: control.fxRadius
        color: control.down ? Qt.tint(control.fxBackground, fxtheme.pressed)
            : control.hovered ? Qt.tint(control.fxBackground, fxtheme.hover)
            : control.fxBackground
        border.color: control.visualFocus ? fxtheme.primary : control.fxBorderColor
        border.width: control.visualFocus ? 2 : control.fxBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }
}
