// Texto de FluxUI: color del tema, ajuste de línea y comportamiento de bloque en columnas.
// format: "plain" (por defecto) | "markdown" | "html". Los enlaces emiten on:link o,
// si nadie lo escucha, se abren en el navegador.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "fx.js" as Fx

Label {
    id: label
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    property color fxColor: fxtheme.text
    property string format: "plain"
    property bool fxLinkHandled: false
    // Fondo y borde (etiquetas, contadores): transparentes salvo que el estilo los fije.
    property color fxBackground: "transparent"
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    property real fxRadius: 0
    // Texto heredado de las cajas que lo contienen (FxContext, FxTextInherit). fxOwn: lo que
    // fija el propio texto (" color size "), que gana a lo heredado.
    readonly property QtObject fxCtx: Fx.ctxOf(label)
    property string fxOwn: ""
    property Item fxInherit: null
    onFxCtxChanged: Fx.textInherit(label)
    Component.onCompleted: Fx.textInherit(label)
    background: Rectangle {
        visible: label.fxBackground.a > 0 || label.fxBorderWidth > 0
        color: label.fxBackground
        border.color: label.fxBorderColor
        border.width: label.fxBorderWidth
        radius: label.fxRadius
    }

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch)
    Layout.preferredWidth: Fx.basis(parent, fxFlex, true)
    Layout.preferredHeight: Fx.basis(parent, fxFlex, false)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: Fx.touch(parent, label, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)

    color: fxColor
    linkColor: fxtheme.primary
    wrapMode: Text.Wrap
    readonly property bool fxWraps: wrapMode !== Text.NoWrap  // puede estrecharse en una fila
    textFormat: format === "markdown" ? Text.MarkdownText
        : format === "html" ? Text.RichText
        : Text.PlainText
    onLinkActivated: (link) => { if (!fxLinkHandled) Qt.openUrlExternally(link) }

    // Mano sobre los enlaces (el texto en sí no captura el ratón).
    HoverHandler {
        enabled: label.format !== "plain"
        cursorShape: label.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
}
