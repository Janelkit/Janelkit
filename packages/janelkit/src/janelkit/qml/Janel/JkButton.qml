// Botón de JanelKit. variant: "default" | "primary" | "danger" | "ghost".
// jkIcon: imagen a la izquierda del texto (ruta relativa al .janel, absoluta o URL), a escala de la fuente.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

Button {
    id: control
    property string variant: "default"
    readonly property bool jkGhost: variant === "ghost" || flat
    property color jkBackground: jkGhost ? "transparent"
        : variant === "primary" ? jktheme.primary
        : variant === "danger" ? jktheme.danger
        : jktheme.surface
    property color jkColor: jkGhost ? jktheme.text
        : variant === "primary" ? jktheme.on_primary
        : variant === "danger" ? jktheme.on_danger
        : jktheme.text
    property color jkBorderColor: variant === "default" && !jkGhost ? jktheme.border : "transparent"
    property real jkBorderWidth: 1
    property real jkRadius: jktheme.radius
    property string jkIcon: ""  // `icon` ya es el grupo icon.* de Button
    property url jkBase: ""  // carpeta del .janel (la fija el compilador)
    property bool disabled: false
    enabled: !disabled
    property bool jkTrackHover: false  // con title: hovered ya lo da el propio botón
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, false, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, control, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)
    Accessible.name: text  // el atributo label la sustituye

    padding: 8
    leftPadding: 14
    rightPadding: 14
    hoverEnabled: true

    contentItem: Item {
        id: jkContent
        readonly property real iconSize: Math.round(jkLabel.fontInfo.pixelSize * 1.25)
        readonly property real iconSpace: jkIconImage.visible ? iconSize + (jkLabel.visible ? 6 : 0) : 0
        implicitWidth: iconSpace + (jkLabel.visible ? jkLabel.implicitWidth : 0)
        implicitHeight: Math.max(jkLabel.implicitHeight, jkIconImage.visible ? iconSize : 0)

        Row {
            anchors.centerIn: parent
            spacing: 6
            Image {
                id: jkIconImage
                visible: control.jkIcon !== ""
                anchors.verticalCenter: parent.verticalCenter
                source: Jk.resolveUrl(control.jkBase, control.jkIcon)
                width: jkContent.iconSize
                height: jkContent.iconSize
                sourceSize: Qt.size(jkContent.iconSize, jkContent.iconSize)
                fillMode: Image.PreserveAspectFit
                smooth: true
                opacity: control.enabled ? 1 : 0.55
            }
            Text {
                id: jkLabel
                visible: text !== "" || !jkIconImage.visible
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, Math.max(0, jkContent.width - jkContent.iconSpace))
                text: control.text
                font: control.font
                color: control.jkColor
                opacity: control.enabled ? 1 : 0.55
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }

    background: Rectangle {
        implicitWidth: control.jkGhost ? 0 : 64  // los botones fantasma (iconos, emojis) pueden ser estrechos
        implicitHeight: 34
        radius: control.jkRadius
        color: control.down ? Qt.tint(control.jkBackground, jktheme.pressed)
            : control.hovered ? Qt.tint(control.jkBackground, jktheme.hover)
            : control.jkBackground
        border.color: control.visualFocus ? jktheme.primary : control.jkBorderColor
        border.width: control.visualFocus ? 2 : control.jkBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }
}
