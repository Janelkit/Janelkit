// Contexto de estilo de una caja (fase 4 de docs/flex.md): el texto que heredan los
// <Text> de dentro (color, fuente, alineación…) y las variables propias (--x). Solo lo
// tienen las cajas que fijan algo de eso; las demás usan el de su contenedor (jkCtx).
// Cada valor es el de la caja (jkT_*, jkV_*) o, si no lo fija, el del contexto de fuera.
// Solo las variables se calculan aquí; el texto, en el <Text> que lo usa.
import QtQuick
import "jk.js" as Jk

QtObject {
    property Item box: null
    property var names: []  // variables propias que define la caja (sin --)
    readonly property QtObject up: box ? Jk.ctxOf(box) : null

    // Claves de texto que fija esta caja o alguna de fuera (Jk.ctxKeys); el valor de cada una
    // lo busca el <Text> que lo hereda (Jk.inherited), subiendo por `up`.
    readonly property string keys: Jk.ctxKeys(box, up)
    readonly property var rVars: Jk.vars(up ? up.rVars : null, box, names)
}
