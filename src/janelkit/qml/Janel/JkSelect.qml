// Lista desplegable de JanelKit.
// options: lista de textos o de {label, value}. value: el valor elegido.
// La selección del usuario se refleja al momento; si Python cambia `value`, manda Python.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

ComboBox {
    id: control
    property var options: []
    property var value: undefined
    property string placeholder: ""
    property color jkColor: jktheme.text
    property color jkBackground: jktheme.surface
    property color jkBorderColor: jktheme.border
    property real jkBorderWidth: 1
    property real jkRadius: jktheme.radius
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
    // on:keydown, on:keyup, on:focus, on:blur: los entrega events.py, como en <flex>
    // (propagación, event.prevent(), event.stop()). El compilador fija jkOn, jkBridge y jkListen.
    property var jkOn: null
    property QtObject jkBridge: null
    property bool jkListen: false
    function jkRegister() { if (jkListen && typeof jkevents !== "undefined") jkevents.listen(control) }
    onJkListenChanged: Qt.callLater(jkRegister)
    Accessible.name: currentIndex < 0 ? placeholder : currentText  // el atributo label la sustituye

    model: Jk.options(options)
    textRole: "label"
    valueRole: "value"
    displayText: currentIndex < 0 ? placeholder : currentText
    hoverEnabled: true

    function jkSync() { currentIndex = indexOfValue(value) }
    onValueChanged: jkSync()
    onModelChanged: jkSync()
    Component.onCompleted: {
        jkSync()
        if (jkListen) jkevents.listen(control)
    }

    contentItem: Text {
        leftPadding: control.mirrored ? control.indicator.width + 6 : 10
        rightPadding: control.mirrored ? 10 : control.indicator.width + 6
        text: control.displayText
        font: control.font
        color: control.currentIndex < 0 ? jktheme.text_muted : control.jkColor
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        opacity: control.enabled ? 1 : 0.55
    }

    indicator: Text {
        x: control.mirrored ? 10 : control.width - width - 10
        y: (control.height - height) / 2
        text: "▾"
        color: jktheme.text_muted
        font.pixelSize: 14
    }

    background: Rectangle {
        implicitWidth: 160
        implicitHeight: 34
        radius: control.jkRadius
        color: control.hovered ? Qt.tint(control.jkBackground, jktheme.hover) : control.jkBackground
        border.color: control.visualFocus || control.popup.visible ? jktheme.primary : control.jkBorderColor
        border.width: control.visualFocus ? 2 : control.jkBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }

    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: modelData.label
            font: control.font
            color: index === control.currentIndex ? jktheme.primary : jktheme.text
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { color: highlighted ? jktheme.hover : "transparent" }
    }

    popup: Popup {
        y: control.height + 2
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        padding: 4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
        }
        background: Rectangle {
            radius: control.jkRadius
            color: jktheme.surface
            border.color: jktheme.border
        }
    }
}
