// Texto de JanelKit: color del tema, ajuste de línea y comportamiento de bloque en columnas.
// format: "plain" (por defecto) | "markdown" | "html". Los enlaces emiten on:link o,
// si nadie lo escucha, se abren en el navegador.
import QtQuick
import QtQuick.Layouts
import "jk.js" as Jk

// Text y no Label (de Controls): un Label cuesta ~2 KB más por texto. Lo único que daba,
// la fuente de la ventana, se fija aquí con la del tema.
Text {
    id: label
    font.family: jktheme.font_family
    font.pixelSize: jktheme.font_size
    property int jkFlex: 0
    property string jkSelfAlign: ""
    property bool jkSelfStretch: false
    property color jkColor: jktheme.text
    property string format: "plain"
    property bool jkLinkHandled: false
    property bool selectable: false  // se puede seleccionar y copiar (JkTextSelect)
    // Fondo y borde (etiquetas, contadores): transparentes salvo que el estilo los fije.
    property color jkBackground: "transparent"
    property color jkBorderColor: "transparent"
    property real jkBorderWidth: 0
    property real jkRadius: 0
    // Texto heredado de las cajas que lo contienen (JkContext, JkTextInherit). jkOwn: lo que
    // fija el propio texto (" color size "), que gana a lo heredado.
    readonly property QtObject jkCtx: Jk.ctxOf(label)
    property string jkOwn: ""
    property var jkInherit: null  // {clave: JkTextInherit}
    readonly property string jkCtxKeys: jkCtx ? jkCtx.keys : ""
    onJkCtxKeysChanged: Jk.textInherit(label)
    // Fondo y borde (JkTextBox), mano sobre los enlaces (JkTextLinks) y selección (JkTextSelect):
    // solo si se usan.
    readonly property int jkDecor: (jkBackground.a > 0 || jkBorderWidth > 0 ? 1 : 0) | (format !== "plain" ? 2 : 0) | (selectable ? 4 : 0)
    property Item jkBack: null  // JkTextBox
    property QtObject jkLinks: null
    property Item jkSelect: null
    onJkDecorChanged: Jk.textDecorations(label)
    Component.onCompleted: {
        if (jkCtxKeys) Jk.textInherit(label)
        if (jkDecor) Jk.textDecorations(label)
    }

    Layout.fillWidth: Jk.fillWidth(parent, jkFlex, jkSelfStretch, true, jkSelfAlign)
    Layout.fillHeight: Jk.fillHeight(parent, jkFlex, jkSelfStretch, jkSelfAlign)
    Layout.alignment: Jk.alignment(parent, jkSelfAlign)
    // Avisa a su contenedor <flex> de lo que cambia su sitio (flex.js).
    property var jkHints: null  // lo que el motor de <flex> guardó de este elemento
    readonly property bool jkTouch: parent !== null && parent.jkEngine === true && Jk.touch(parent, label, visible,
        Layout.preferredWidth, Layout.preferredHeight, Layout.minimumWidth, Layout.minimumHeight,
        Layout.maximumWidth, Layout.maximumHeight, Layout.fillWidth, Layout.fillHeight,
        Layout.leftMargin, Layout.topMargin, Layout.rightMargin, Layout.bottomMargin,
        jkFlex, jkSelfAlign, jkSelfStretch)
    // El tamaño natural, con manejadores: leerlo en un binding puede recalcular el texto
    // dentro del propio binding (Qt lo toma por un bucle).
    onImplicitWidthChanged: Jk.resized(parent)
    onImplicitHeightChanged: Jk.resized(parent)

    color: jkSelect && jkSelect.visible ? "transparent" : jkColor  // con selectable, lo dibuja la copia
    linkColor: jktheme.primary
    wrapMode: Text.Wrap
    readonly property bool jkWraps: wrapMode !== Text.NoWrap  // puede estrecharse en una fila
    textFormat: format === "markdown" ? Text.MarkdownText
        : format === "html" ? Text.RichText
        : Text.PlainText
    onLinkActivated: (link) => { if (!jkLinkHandled) Qt.openUrlExternally(link) }
}
