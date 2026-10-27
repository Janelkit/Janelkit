// Aplica a un <Text> el texto heredado de su contexto (FxContext). FxText lo crea solo
// cuando tiene contexto: los textos fuera de una caja con estilo de texto no pagan nada.
// Lo que el propio <Text> fija (fxOwn, lo anota el compilador) gana a lo heredado.
import QtQuick

Item {
    id: root
    property Item target: null
    readonly property QtObject ctx: target ? target.fxCtx : null
    readonly property string own: target ? target.fxOwn : ""
    visible: false

    function inherits(value, name) { return root.ctx !== null && value !== undefined && own.indexOf(" " + name + " ") < 0 }

    Binding { target: root.target; property: "fxColor"; when: root.inherits(root.ctx ? root.ctx.rColor : undefined, "color"); value: root.ctx ? root.ctx.rColor : "black" }
    Binding { target: root.target; property: "font.family"; when: root.inherits(root.ctx ? root.ctx.rFamily : undefined, "family"); value: root.ctx ? root.ctx.rFamily : "" }
    Binding { target: root.target; property: "font.pixelSize"; when: root.inherits(root.ctx ? root.ctx.rSize : undefined, "size"); value: root.ctx ? root.ctx.rSize : 0 }
    Binding { target: root.target; property: "font.weight"; when: root.inherits(root.ctx ? root.ctx.rWeight : undefined, "weight"); value: root.ctx ? root.ctx.rWeight : 0 }
    Binding { target: root.target; property: "font.italic"; when: root.inherits(root.ctx ? root.ctx.rItalic : undefined, "italic"); value: root.ctx ? root.ctx.rItalic : false }
    Binding { target: root.target; property: "font.letterSpacing"; when: root.inherits(root.ctx ? root.ctx.rLetterSpacing : undefined, "letterSpacing"); value: root.ctx ? root.ctx.rLetterSpacing : 0 }
    Binding { target: root.target; property: "font.capitalization"; when: root.inherits(root.ctx ? root.ctx.rCapitalization : undefined, "capitalization"); value: root.ctx ? root.ctx.rCapitalization : 0 }
    Binding { target: root.target; property: "horizontalAlignment"; when: root.inherits(root.ctx ? root.ctx.rAlign : undefined, "align"); value: root.ctx ? root.ctx.rAlign : 0 }
    Binding { target: root.target; property: "lineHeight"; when: root.inherits(root.ctx ? root.ctx.rLineHeight : undefined, "lineHeight"); value: root.ctx ? root.ctx.rLineHeight : 1 }
    Binding { target: root.target; property: "wrapMode"; when: root.inherits(root.ctx ? root.ctx.rWrap : undefined, "wrap"); value: root.ctx ? root.ctx.rWrap : 0 }
    Binding { target: root.target; property: "elide"; when: root.inherits(root.ctx ? root.ctx.rElide : undefined, "elide"); value: root.ctx ? root.ctx.rElide : 0 }
}
