// Reglas de disposición compartidas por los controles de FluxUI.
// `p` es el layout padre (el `lay` de una caja): expone fxBox (la caja), fxHorizontal,
// fxAlign (align-items) y fxStretch (align-items: stretch); el del motor de <flex>,
// además, fxEngine.
.pragma library
.import "flex.js" as Flex

const ALIGN_LEFT = 0x1, ALIGN_RIGHT = 0x2, ALIGN_HCENTER = 0x4
const ALIGN_TOP = 0x20, ALIGN_BOTTOM = 0x40, ALIGN_VCENTER = 0x80

function inLayout(p) {
    return !!p && p.fxHorizontal !== undefined
}

// `block`: el elemento ocupa todo el ancho de una columna salvo que el
// contenedor fije una alineación (como un bloque en CSS). `self` (align-self) gana:
// con start, center o end no se estira en el eje transversal.
function fillWidth(p, flex, selfStretch, block, self) {
    if (!inLayout(p)) return false
    if (p.fxBox.fxFill) return true
    if (p.fxHorizontal) return flex > 0
    if (selfStretch) return true
    if (self && self !== "stretch") return false
    return p.fxStretch || (block && !p.fxAlign)
}

function fillHeight(p, flex, selfStretch, self) {
    if (!inLayout(p)) return false
    if (p.fxBox.fxFill) return true
    if (!p.fxHorizontal) return flex > 0
    if (selfStretch) return true
    if (self && self !== "stretch") return false
    return p.fxStretch
}

function alignment(p, self) {
    if (!inLayout(p)) return 0
    const h = p.fxHorizontal
    if (self === "start") return h ? ALIGN_TOP : ALIGN_LEFT
    if (self === "center") return h ? ALIGN_VCENTER : ALIGN_HCENTER
    if (self === "end") return h ? ALIGN_BOTTOM : ALIGN_RIGHT
    return p.fxAlign
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

// padding y gap por lado sin fijar (NaN): los de padding y gap. Así una caja no paga
// un binding por lado.
function pad(own, all) {
    return isNaN(own) ? all : own
}

// Separación en el eje principal de un contenedor (`lay`): la heredan las cajas implícitas.
function mainGap(lay) {
    const b = lay.fxBox
    return pad(lay.fxHorizontal ? b.columnGap : b.rowGap, b.gap)
}

// -- <flex> (motor en flex.js) ------------------------------------------------

// Binding de cada elemento: depende de todo lo que afecta a su sitio en el
// contenedor (salvo el tamaño natural, ver resized) y, al cambiar, lo pone en la
// cola de disposición. Devuelve true.
// `item` es el propio elemento: lo que el motor guardó de él deja de valer.
function touch(p, item) {
    return Flex.touch(p, item)
}

// Cambió el tamaño natural (o algo del contenedor): solo hay que volver a colocar.
function resized(p) {
    return Flex.resized(p)
}

// align-items de un contenedor flex como banderas Qt.Align* (las leen los
// controles en Fx.alignment cuando su contenedor es un layout de Qt).
function alignFlags(align, horizontal) {
    if (align === "start") return horizontal ? ALIGN_TOP : ALIGN_LEFT
    if (align === "center") return horizontal ? ALIGN_VCENTER : ALIGN_HCENTER
    if (align === "end") return horizontal ? ALIGN_BOTTOM : ALIGN_RIGHT
    return 0
}

// Lo que una caja solo crea si lo usa: bordes por lado, sombra, contorno, bloqueo del
// puntero, desplazamiento (overflow: auto), manejadores del puntero (on:click, :hover,
// :pressed, cursor), papel interactivo (accesibilidad y teclado) y translate().
// FxBox.fxDecor dice qué hace falta; al cambiar, se llama a flexDecorations.
const D_SIDES = 1, D_SHADOW = 2, D_OUTLINE = 4, D_BLOCKER = 8, D_SCROLL = 16
const D_HOVER = 32, D_TAP = 64, D_ROLE = 128, D_TRANSLATE = 256
let hoverComponent = null
let tapComponent = null
let roleComponent = null
let translateComponent = null
let sidesComponent = null
let scrollerComponent = null
let shadowComponent = null
let outlineComponent = null
let blockerComponent = null

function component(cached, file) {
    if (cached) return cached
    const c = Qt.createComponent(Qt.resolvedUrl(file))
    if (c.status === 3) console.warn(c.errorString())
    return c
}

function flexDecorations(box) {
    const d = box.fxDecor
    if (d & D_HOVER && !box.fxHover) {
        hoverComponent = component(hoverComponent, "FxHover.qml")
        box.fxHover = hoverComponent.createObject(box, { box: box })
    }
    if (d & D_TAP && !box.fxTap) {
        tapComponent = component(tapComponent, "FxTap.qml")
        box.fxTap = tapComponent.createObject(box, { box: box })
    }
    if (d & D_ROLE && !box.fxRoleItem) {
        roleComponent = component(roleComponent, "FxRole.qml")
        box.fxRoleItem = roleComponent.createObject(box, { box: box })
    }
    if (d & D_TRANSLATE && !box.fxTranslate) {
        translateComponent = component(translateComponent, "FxTranslate.qml")
        box.fxTranslate = translateComponent.createObject(box, { box: box })
        box.transform = [box.fxTranslate]
    }
    if (box.fxSides && !box.fxSideItem) {
        sidesComponent = component(sidesComponent, "FxSides.qml")
        box.fxSideItem = sidesComponent.createObject(box, { box: box })
    }
    if (box.fxShadow && !box.fxShadowItem) {
        shadowComponent = component(shadowComponent, "FxShadow.qml")
        box.fxShadowItem = shadowComponent.createObject(box, { box: box })
    }
    if (box.fxOutlineWidth > 0 && !box.fxOutlineItem) {
        outlineComponent = component(outlineComponent, "FxOutline.qml")
        box.fxOutlineItem = outlineComponent.createObject(box, { box: box })
    }
    if ((box.fxPosition === "absolute" || box.fxPosition === "fixed") && !box.fxBlocker) {
        blockerComponent = component(blockerComponent, "FxBlocker.qml")
        box.fxBlocker = blockerComponent.createObject(box, { box: box })
    }
    if (box.fxScrollable && !box.fxScroller) {
        scrollerComponent = component(scrollerComponent, "FxScroller.qml")
        const s = scrollerComponent.createObject(box, { box: box })
        box.fxLay.parent = s.contentItem
        box.fxScroller = s
    }
}

// :focus-within: ¿`focused` (el elemento con el foco de la ventana) es `item` o está dentro?
function within(item, focused) {
    for (let p = focused; p; p = p.parent)
        if (p === item) return true
    return false
}

// -- position: absolute y fixed (flex.js) --------------------------------------------
// Lee lo que decide dónde va un elemento con position absolute o fixed: la posición de
// sus antecesores hasta su bloque contenedor y el tamaño de este. Al usarse en un
// binding, el elemento se vuelve a colocar cuando algo de eso cambia.
function positionDeps(item) {
    const pos = item.fxPosition
    if (pos !== "absolute" && pos !== "fixed") return 0
    let s = 0
    for (let p = item.parent; p; p = p.parent) {
        s += p.x + p.y
        if (pos === "absolute" && p.fxLay && p.fxPosition && p.fxPosition !== "static") return s + p.width + p.height
        if (!p.parent) return s + p.width + p.height
    }
    return s
}

// -- contexto de estilo: texto heredado y variables propias (FxContext.qml) ---------
// El contexto más cercano por encima de `item` (el de su caja), o null.
function ctxOf(item) {
    for (let p = item.parent; p; p = p.parent) {
        if (p.fxBox) return p.fxBox.fxCtx
        if (p.fxCtx !== undefined) return p.fxCtx
    }
    return null
}

// Variables visibles en una caja: las de fuera más las suyas (fxV_<nombre>).
function vars(up, box, names) {
    if (!box || !names || names.length === 0) return up
    const out = {}
    if (up) for (const k in up) out[k] = up[k]
    for (let i = 0; i < names.length; ++i) {
        const v = box["fxV_" + names[i]]
        if (v !== undefined) out[names[i]] = v
    }
    return out
}

// var(--nombre, otro): la variable más cercana; si no hay, `fallback` y, si tampoco, `dflt`.
function cssVar(ctx, name, fallback, dflt) {
    const vs = ctx ? ctx.rVars : null
    const v = vs ? vs[name] : undefined
    if (v !== undefined) return v
    return fallback === undefined ? dflt : fallback
}

// Fondo y borde de un <Text>, y la mano sobre sus enlaces: solo los que los usan (FxText.fxDecor).
let textBoxComponent = null
let textLinksComponent = null
function textDecorations(label) {
    if (label.fxDecor & 1 && !label.background) {
        textBoxComponent = component(textBoxComponent, "FxTextBox.qml")
        label.background = textBoxComponent.createObject(label, { label: label })
    }
    if (label.fxDecor & 2 && !label.fxLinks) {
        textLinksComponent = component(textLinksComponent, "FxTextLinks.qml")
        label.fxLinks = textLinksComponent.createObject(label, { label: label })
    }
}

let inheritComponent = null
// Un <Text> con contexto recibe el texto heredado (FxTextInherit.qml), solo entonces.
function textInherit(label) {
    if (!label.fxCtx || label.fxInherit) return
    inheritComponent = component(inheritComponent, "FxTextInherit.qml")
    label.fxInherit = inheritComponent.createObject(label, { target: label })
}

// style={{...}}: valores que llegan de Python como texto CSS o números.
function cssPx(v, dflt) {
    if (typeof v === "number") return v
    if (typeof v !== "string" || v.trim().endsWith("%") || v.trim() === "") return dflt
    const n = parseFloat(v)
    return isNaN(n) ? dflt : n
}
function cssPct(v) {
    if (typeof v !== "string" || !v.trim().endsWith("%")) return 0
    const n = parseFloat(v)
    return isNaN(n) ? 0 : n
}
function cssColor(v) {
    return v === undefined || v === null || v === "" ? "transparent" : v
}
