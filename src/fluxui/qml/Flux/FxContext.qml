// Contexto de estilo de una caja (fase 4 de docs/flex.md): el texto que heredan los
// <Text> de dentro (color, fuente, alineación…) y las variables propias (--x). Solo lo
// tienen las cajas que fijan algo de eso; las demás usan el de su contenedor (fxCtx).
// Cada valor es el de la caja (fxT_*, fxV_*) o, si no lo fija, el del contexto de fuera.
// Solo las variables se calculan aquí; el texto, en el <Text> que lo usa.
import QtQuick
import "fx.js" as Fx

QtObject {
    property Item box: null
    property var names: []  // variables propias que define la caja (sin --)
    readonly property QtObject up: box ? Fx.ctxOf(box) : null

    // Claves de texto que fija esta caja o alguna de fuera (Fx.ctxKeys); el valor de cada una
    // lo busca el <Text> que lo hereda (Fx.inherited), subiendo por `up`.
    readonly property string keys: Fx.ctxKeys(box, up)
    readonly property var rVars: Fx.vars(up ? up.rVars : null, box, names)
}
