// Texto de FluxUI: color del tema, ajuste de línea y comportamiento de bloque en columnas.
// format: "plain" (por defecto) | "markdown" | "html". Los enlaces emiten on:link o,
// si nadie lo escucha, se abren en el navegador.
import QtQuick
import QtQuick.Layouts
import "fx.js" as Fx

// Text y no Label (de Controls): un Label cuesta ~2 KB más por texto. Lo único que daba,
// la fuente de la ventana, se fija aquí con la del tema.
Text {
    id: label
    font.family: fxtheme.font_family
    font.pixelSize: fxtheme.font_size
    property int fxFlex: 0
    property string fxSelfAlign: ""
    property bool fxSelfStretch: false
    property color fxColor: fxtheme.text
    property string format: "plain"
    property bool fxLinkHandled: false
    property bool selectable: false  // se puede seleccionar y copiar (FxTextSelect)
    // Fondo y borde (etiquetas, contadores): transparentes salvo que el estilo los fije.
    property color fxBackground: "transparent"
    property color fxBorderColor: "transparent"
    property real fxBorderWidth: 0
    property real fxRadius: 0
    // Texto heredado de las cajas que lo contienen (FxContext, FxTextInherit). fxOwn: lo que
    // fija el propio texto (" color size "), que gana a lo heredado.
    readonly property QtObject fxCtx: Fx.ctxOf(label)
    property string fxOwn: ""
    property var fxInherit: null  // {clave: FxTextInherit}
    readonly property string fxCtxKeys: fxCtx ? fxCtx.keys : ""
    onFxCtxKeysChanged: Fx.textInherit(label)
    // Fondo y borde (FxTextBox), mano sobre los enlaces (FxTextLinks) y selección (FxTextSelect):
    // solo si se usan.
    readonly property int fxDecor: (fxBackground.a > 0 || fxBorderWidth > 0 ? 1 : 0) | (format !== "plain" ? 2 : 0) | (selectable ? 4 : 0)
    property Item fxBack: null  // FxTextBox
    property QtObject fxLinks: null
    property Item fxSelect: null
    onFxDecorChanged: Fx.textDecorations(label)
    Component.onCompleted: {
        if (fxCtxKeys) Fx.textInherit(label)
        if (fxDecor) Fx.textDecorations(label)
    }

    Layout.fillWidth: Fx.fillWidth(parent, fxFlex, fxSelfStretch, true, fxSelfAlign)
    Layout.fillHeight: Fx.fillHeight(parent, fxFlex, fxSelfStretch, fxSelfAlign)
    Layout.alignment: Fx.alignment(parent, fxSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var fxHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool fxTouch: parent !== null && parent.fxEngine === true && Fx.touch(parent, label, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        fxFlex, fxSelfAlign, fxSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Fx.resized(parent)
    onImplicitHeightChanged: Fx.resized(parent)

    color: fxSelect && fxSelect.visible ? "transparent" : fxColor  // con selectable, lo dibuja la copia
    linkColor: fxtheme.primary
    wrapMode: Text.Wrap
    readonly property bool fxWraps: wrapMode !== Text.NoWrap  // puede estrecharse en una fila
    textFormat: format === "markdown" ? Text.MarkdownText
        : format === "html" ? Text.RichText
        : Text.PlainText
    onLinkActivated: (link) => { if (!fxLinkHandled) Qt.openUrlExternally(link) }
}
