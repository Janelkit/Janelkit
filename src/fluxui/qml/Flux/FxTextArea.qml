// Texto de varias líneas de FluxUI. Crece con el contenido; envuélvelo en <Scroll> si hace falta.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

TextArea {
    id: control
    property color fxColor: fxtheme.text
    property color fxBackground: fxtheme.surface
    property color fxBorderColor: fxtheme.border
    property real fxBorderWidth: 1
    property real fxRadius: fxtheme.radius
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    // Valor que llega de Python. `text` lo edita el usuario; solo sus cambios emiten userEdited.
    property string fxValue: ""
    signal userEdited(string text)

    onFxValueChanged: if (text !== fxValue) text = fxValue
    onTextChanged: if (text !== fxValue) userEdited(text)
    Component.onCompleted: if (text !== fxValue) text = fxValue

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
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
    Accessible.name: placeholderText  // el atributo label la sustituye

    color: fxColor
    placeholderTextColor: fxtheme.text_muted
    selectionColor: fxtheme.primary
    selectedTextColor: fxtheme.on_primary
    wrapMode: TextEdit.Wrap
    padding: 10
    hoverEnabled: true

    background: Rectangle {
        implicitWidth: 180
        implicitHeight: 80
        radius: control.fxRadius
        color: control.fxBackground
        border.color: control.activeFocus ? fxtheme.primary : control.fxBorderColor
        border.width: control.activeFocus ? 2 : control.fxBorderWidth
        opacity: control.enabled ? 1 : 0.55
    }
}
