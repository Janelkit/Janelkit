// Texto de varias líneas de JanelKit. Crece con el contenido; envuélvelo en <Scroll> si hace falta.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "jk.js" as Jk

TextArea {
    id: control
    property color jkColor: jktheme.text
    property color jkBackground: jktheme.surface
    property color jkBorderColor: jktheme.border
    property real jkBorderWidth: 1
    property real jkRadius: jktheme.radius
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false
    // Valor que llega de Python. `text` lo edita el usuario; solo sus cambios emiten userEdited.
    property string jkValue: ""
    signal userEdited(string text)

    onJkValueChanged: if (text !== jkValue) text = jkValue
    onTextChanged: if (text !== jkValue) userEdited(text)
    Component.onCompleted: {
        if (text !== jkValue) text = jkValue
        if (jkListen) jkevents.listen(control)
    }

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
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
    Accessible.name: placeholderText  // el atributo label la sustituye

    color: jkColor
    placeholderTextColor: jktheme.text_muted
    selectionColor: jktheme.primary
    selectedTextColor: jktheme.on_primary
    wrapMode: TextEdit.Wrap
    padding: 10
    hoverEnabled: true

    background: Rectangle {
        implicitWidth: 180
        implicitHeight: 80
        radius: control.jkRadius
        color: control.jkBackground
        border.color: control.activeFocus ? jktheme.primary : control.jkBorderColor
        border.width: control.activeFocus ? 2 : control.jkBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }
}
