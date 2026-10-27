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
    if (p.fxFill) return true
    if (p.fxHorizontal) return flex > 0
    return selfStretch || p.fxStretch || (block && !p.fxAlign)
}

function fillHeight(p, flex, selfStretch) {
    if (!inLayout(p)) return false
    if (p.fxFill) return true
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

// Opciones de Select, RadioGroup y Tabs: textos sueltos o {label, value}.
function options(list) {
    const out = []
    if (!list) return out
    for (let i = 0; i < list.length; ++i) {
        const o = list[i]
        if (o !== null && typeof o === "object" && o.label !== undefined)
            out.push({ label: String(o.label), value: o.value === undefined ? o.label : o.value })
        else
            out.push({ label: String(o), value: o })
    }
    return out
}

// Rutas de imagen: absoluta (Windows o Unix) -> file:, con esquema (http:, qrc:, data:) -> tal cual,
// relativa -> respecto a la carpeta del .flux (`base`).
function resolveUrl(base, src) {
    if (!src) return ""
    if (/^[A-Za-z]:[\\/]/.test(src)) return "file:///" + src.replace(/\\/g, "/")
    if (src.startsWith("/")) return "file://" + src
    if (/^[A-Za-z][A-Za-z0-9+.-]+:/.test(src)) return src
    const b = String(base)
    return b + (b.endsWith("/") ? "" : "/") + src
}

// flex como en CSS (`flex: N 1 0`): en el eje principal, cada hijo con flex N recibe
// N partes del espacio que dejan libre los demás. El contenedor calcula el tamaño
// de una parte (fxFlexUnit) solo si su propio tamaño viene de fuera; si depende
// del contenido, se devuelve -1 (tamaño natural) para no crear bucles.
function basis(p, flex, horizontalAxis) {
    if (!inLayout(p) || flex <= 0 || p.fxHorizontal !== horizontalAxis || p.fxFill || !(p.fxFlexUnit > 0)) return -1
    return p.fxFlexUnit * flex
}

function flexUnit(lay, horizontal, available) {
    let fixed = 0, total = 0, n = 0
    const kids = lay.children
    for (let i = 0; i < kids.length; ++i) {
        const c = kids[i]
        if (!c.visible) continue
        const flex = c.fxFlex
        const size = horizontal ? c.width : c.height
        if (flex > 0) { total += flex; n++; continue }
        if (flex === undefined && size === 0) continue  // Repeater y similares: no ocupan sitio
        fixed += size
        n++
    }
    if (total === 0) return 0
    return Math.max(0, available - fixed - lay.spacing * Math.max(0, n - 1)) / total
}
