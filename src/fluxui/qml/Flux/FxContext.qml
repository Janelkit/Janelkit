// Contexto de estilo de una caja (fase 4 de docs/flex.md): el texto que heredan los
// <Text> de dentro (color, fuente, alineación…) y las variables propias (--x). Solo lo
// tienen las cajas que fijan algo de eso; las demás usan el de su contenedor (fxCtx).
// Cada valor es el de la caja (fxT_*, fxV_*) o, si no lo fija, el del contexto de fuera.
import QtQuick
import "fx.js" as Fx

QtObject {
    property Item box: null
    property var names: []  // variables propias que define la caja (sin --)
    readonly property QtObject up: box ? Fx.ctxOf(box) : null

    readonly property var rColor: box && box.fxT_color !== undefined ? box.fxT_color : up ? up.rColor : undefined
    readonly property var rFamily: box && box.fxT_family !== undefined ? box.fxT_family : up ? up.rFamily : undefined
    readonly property var rSize: box && box.fxT_size !== undefined ? box.fxT_size : up ? up.rSize : undefined
    readonly property var rWeight: box && box.fxT_weight !== undefined ? box.fxT_weight : up ? up.rWeight : undefined
    readonly property var rItalic: box && box.fxT_italic !== undefined ? box.fxT_italic : up ? up.rItalic : undefined
    readonly property var rLetterSpacing: box && box.fxT_letterSpacing !== undefined ? box.fxT_letterSpacing : up ? up.rLetterSpacing : undefined
    readonly property var rCapitalization: box && box.fxT_capitalization !== undefined ? box.fxT_capitalization : up ? up.rCapitalization : undefined
    readonly property var rAlign: box && box.fxT_align !== undefined ? box.fxT_align : up ? up.rAlign : undefined
    readonly property var rLineHeight: box && box.fxT_lineHeight !== undefined ? box.fxT_lineHeight : up ? up.rLineHeight : undefined
    readonly property var rWrap: box && box.fxT_wrap !== undefined ? box.fxT_wrap : up ? up.rWrap : undefined
    readonly property var rElide: box && box.fxT_elide !== undefined ? box.fxT_elide : up ? up.rElide : undefined
    readonly property var rVars: Fx.vars(up ? up.rVars : null, box, names)
}
