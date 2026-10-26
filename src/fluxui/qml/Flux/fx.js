// Reglas de disposición compartidas por los controles de FluxUI.
// `p` es el layout padre: FxColumn/FxRow/FxScroll exponen fxHorizontal,
// fxAlign (align-items) y fxStretch (align-items: stretch).
.pragma library

const ALIGN_LEFT = 0x1, ALIGN_RIGHT = 0x2, ALIGN_HCENTER = 0x4
const ALIGN_TOP = 0x20, ALIGN_BOTTOM = 0x40, ALIGN_VCENTER = 0x80

function inLayout(p) {
    return !!p && p.fxHorizontal !== undefined
}

// `block`: el elemento ocupa todo el ancho de una columna salvo que el
// contenedor fije una alineación (como un bloque en CSS).
function fillWidth(p, flex, selfStretch, block) {
    if (!inLayout(p)) return false
    if (p.fxHorizontal) return flex > 0
    return selfStretch || p.fxStretch || (block && !p.fxAlign)
}

function fillHeight(p, flex, selfStretch) {
    if (!inLayout(p)) return false
    if (p.fxHorizontal) return selfStretch || p.fxStretch
    return flex > 0
}

function alignment(p, self) {
    if (!inLayout(p)) return 0
    const h = p.fxHorizontal
    if (self === "start") return h ? ALIGN_TOP : ALIGN_LEFT
    if (self === "center") return h ? ALIGN_VCENTER : ALIGN_HCENTER
    if (self === "end") return h ? ALIGN_BOTTOM : ALIGN_RIGHT
    return p.fxAlign
}

// true si algún hijo visible pide crecer en el eje principal (flex).
function anyFlex(children) {
    for (let i = 0; i < children.length; ++i)
        if (children[i].fxFlex > 0 && children[i].visible) return true
    return false
}
