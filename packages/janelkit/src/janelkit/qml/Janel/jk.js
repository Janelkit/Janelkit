// Reglas de disposición compartidas por los controles de JanelKit.
// `p` es el layout padre (el `lay` de una caja): expone jkBox (la caja), jkHorizontal,
// jkAlign (align-items) y jkStretch (align-items: stretch); el del motor de <flex>,
// además, jkEngine.
.pragma library
.import "flex.js" as Flex

const ALIGN_LEFT = 0x1, ALIGN_RIGHT = 0x2, ALIGN_HCENTER = 0x4
const ALIGN_TOP = 0x20, ALIGN_BOTTOM = 0x40, ALIGN_VCENTER = 0x80

function inLayout(p) {
    return !!p && p.jkHorizontal !== undefined
}

// `block`: el elemento ocupa todo el ancho de una columna salvo que el
// contenedor fije una alineación (como un bloque en CSS). `self` (align-self) gana:
// con start, center o end no se estira en el eje transversal.
function fillWidth(p, flex, selfStretch, block, self) {
    // La raíz de una página llena su <Pages> salvo que fije su tamaño (width, height: el
    // compilador pone entonces Layout.fill* a false); align-self la decide arrangePages.
    if (p && p.jkPages === true) return true
    if (!inLayout(p)) return false
    if (p.jkBox.jkFill) return true
    if (p.jkHorizontal) return flex > 0
    if (selfStretch) return true
    if (self && self !== "stretch") return false
    return p.jkStretch || (block && !p.jkAlign)
}

function fillHeight(p, flex, selfStretch, self) {
    if (p && p.jkPages === true) return true
    if (!inLayout(p)) return false
    if (p.jkBox.jkFill) return true
    if (!p.jkHorizontal) return flex > 0
    if (selfStretch) return true
    if (self && self !== "stretch") return false
    return p.jkStretch
}

function alignment(p, self) {
    if (!inLayout(p)) return 0
    const h = p.jkHorizontal
    if (self === "start") return h ? ALIGN_TOP : ALIGN_LEFT
    if (self === "center") return h ? ALIGN_VCENTER : ALIGN_HCENTER
    if (self === "end") return h ? ALIGN_BOTTOM : ALIGN_RIGHT
    return p.jkAlign
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
// relativa -> respecto a la carpeta del .janel (`base`).
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
    const b = lay.jkBox
    return pad(lay.jkHorizontal ? b.columnGap : b.rowGap, b.gap)
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
// controles en Jk.alignment cuando su contenedor es un layout de Qt).
function alignFlags(align, horizontal) {
    if (align === "start") return horizontal ? ALIGN_TOP : ALIGN_LEFT
    if (align === "center") return horizontal ? ALIGN_VCENTER : ALIGN_HCENTER
    if (align === "end") return horizontal ? ALIGN_BOTTOM : ALIGN_RIGHT
    return 0
}

// Lo que una caja solo crea si lo usa: bordes por lado, sombra, contorno, bloqueo del
// puntero, desplazamiento (overflow: auto), manejadores del puntero (on:click, :hover,
// :pressed, cursor), papel interactivo (accesibilidad y teclado) y translate().
// JkBox.jkDecor dice qué hace falta; al cambiar, se llama a flexDecorations.
const D_SIDES = 1, D_SHADOW = 2, D_OUTLINE = 4, D_BLOCKER = 8, D_SCROLL = 16
const D_HOVER = 32, D_TAP = 64, D_ROLE = 128, D_TRANSLATE = 256, D_BORDER = 512
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
    const d = box.jkDecor
    if (d & D_HOVER && !box.jkHover) {
        hoverComponent = component(hoverComponent, "JkHover.qml")
        box.jkHover = hoverComponent.createObject(box, { box: box })
    }
    if (d & D_TAP && !box.jkTap) {
        tapComponent = component(tapComponent, "JkTap.qml")
        box.jkTap = tapComponent.createObject(box, { box: box })
    }
    if (d & D_ROLE && !box.jkRoleItem) {
        roleComponent = component(roleComponent, "JkRole.qml")
        box.jkRoleItem = roleComponent.createObject(box, { box: box })
    }
    if (d & D_TRANSLATE && !box.jkTranslate) {
        translateComponent = component(translateComponent, "JkTranslate.qml")
        box.jkTranslate = translateComponent.createObject(box, { box: box })
        box.transform = [box.jkTranslate]
    }
    if (d & D_BORDER && !box.jkBorderBound) {
        box.jkBorderBound = true
        box.jkBorderTopW = Qt.binding(function () { return box.jkBorderTop >= 0 ? box.jkBorderTop : box.jkBorderWidth })
        box.jkBorderRightW = Qt.binding(function () { return box.jkBorderRight >= 0 ? box.jkBorderRight : box.jkBorderWidth })
        box.jkBorderBottomW = Qt.binding(function () { return box.jkBorderBottom >= 0 ? box.jkBorderBottom : box.jkBorderWidth })
        box.jkBorderLeftW = Qt.binding(function () { return box.jkBorderLeft >= 0 ? box.jkBorderLeft : box.jkBorderWidth })
    }
    if (box.jkSides && !box.jkSideItem) {
        sidesComponent = component(sidesComponent, "JkSides.qml")
        box.jkSideItem = sidesComponent.createObject(box, { box: box })
    }
    if (box.jkShadow && !box.jkShadowItem) {
        shadowComponent = component(shadowComponent, "JkShadow.qml")
        box.jkShadowItem = shadowComponent.createObject(box, { box: box })
    }
    if (box.jkOutlineWidth > 0 && !box.jkOutlineItem) {
        outlineComponent = component(outlineComponent, "JkOutline.qml")
        box.jkOutlineItem = outlineComponent.createObject(box, { box: box })
    }
    if ((box.jkPosition === "absolute" || box.jkPosition === "fixed") && !box.jkBlocker) {
        blockerComponent = component(blockerComponent, "JkBlocker.qml")
        box.jkBlocker = blockerComponent.createObject(box, { box: box })
    }
    if (box.jkScrollable && !box.jkScroller) {
        scrollerComponent = component(scrollerComponent, "JkScroller.qml")
        const s = scrollerComponent.createObject(box, { box: box })
        box.jkLay.parent = s.contentItem
        box.jkScroller = s
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
    const pos = item.jkPosition
    if (pos !== "absolute" && pos !== "fixed") return 0
    let s = 0
    for (let p = item.parent; p; p = p.parent) {
        s += p.x + p.y
        if (pos === "absolute" && p.jkLay && p.jkPosition && p.jkPosition !== "static") return s + p.width + p.height
        if (!p.parent) return s + p.width + p.height
    }
    return s
}

// -- contexto de estilo: texto heredado y variables propias (JkContext.qml) ---------
// El contexto más cercano por encima de `item` (el de su caja), o null.
function ctxOf(item) {
    for (let p = item.parent; p; p = p.parent) {
        if (p.jkBox) return p.jkBox.jkCtx
        if (p.jkCtx !== undefined) return p.jkCtx
    }
    return null
}

// Variables visibles en una caja: las de fuera más las suyas (jkV_<nombre>).
function vars(up, box, names) {
    if (!box || !names || names.length === 0) return up
    const out = {}
    if (up) for (const k in up) out[k] = up[k]
    for (let i = 0; i < names.length; ++i) {
        const v = box["jkV_" + names[i]]
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

// Fondo y borde de un <Text>, y la mano sobre sus enlaces: solo los que los usan (JkText.jkDecor).
let textBoxComponent = null
let textLinksComponent = null
let textSelectComponent = null
function textDecorations(label) {
    if (label.jkDecor & 1 && !label.jkBack) {
        textBoxComponent = component(textBoxComponent, "JkTextBox.qml")
        label.jkBack = textBoxComponent.createObject(label, { label: label })
    }
    if (label.jkDecor & 2 && !label.jkLinks) {
        textLinksComponent = component(textLinksComponent, "JkTextLinks.qml")
        label.jkLinks = textLinksComponent.createObject(label, { label: label })
    }
    if (label.jkSelect) {
        label.jkSelect.visible = (label.jkDecor & 4) !== 0
    } else if (label.jkDecor & 4) {
        textSelectComponent = component(textSelectComponent, "JkTextSelect.qml")
        label.jkSelect = textSelectComponent.createObject(label, { label: label })
    }
}

// Texto heredable: clave de jkT_<clave> en las cajas -> propiedad del <Text>.
const TEXT_PROPS = {
    color: "jkColor", family: "font.family", size: "font.pixelSize", weight: "font.weight",
    italic: "font.italic", letterSpacing: "font.letterSpacing", capitalization: "font.capitalization",
    align: "horizontalAlignment", lineHeight: "lineHeight", wrap: "wrapMode", elide: "elide",
}

// Claves de texto que fija la caja de un contexto o alguna de fuera (" color size "), en un
// orden fijo: solo cambia si cambia el conjunto. El compilador declara jkT_<clave> solo en
// las cajas cuyo estilo la fija.
function ctxKeys(box, up) {
    const outer = up ? up.keys : ""
    let out = ""
    for (const k in TEXT_PROPS)
        if (outer.indexOf(" " + k + " ") >= 0 || (box && ("jkT_" + k) in box)) out += " " + k + " "
    return out
}

// El valor heredado de `key`: el de la caja más cercana que lo fija; undefined si ninguna.
function inherited(ctx, key) {
    const name = "jkT_" + key
    for (let c = ctx; c; c = c.up) {
        const v = c.box ? c.box[name] : undefined
        if (v !== undefined) return v
    }
    return undefined
}

let inheritComponent = null
// Un <Text> con contexto recibe un JkTextInherit (un Binding) por cada clave que alguna caja
// de fuera fija y él no (jkOwn): los demás textos y las demás claves no pagan nada. Si el
// texto cambia de sitio se añaden las que falten; las que ya no hay no aplican nada.
function textInherit(label) {
    const keys = label.jkCtx ? label.jkCtx.keys : ""
    if (!keys) return
    const have = label.jkInherit || {}
    let added = false
    for (const k in TEXT_PROPS) {
        if (have[k] || keys.indexOf(" " + k + " ") < 0 || label.jkOwn.indexOf(" " + k + " ") >= 0) continue
        inheritComponent = component(inheritComponent, "JkTextInherit.qml")
        have[k] = inheritComponent.createObject(label, { target: label, property: TEXT_PROPS[k], key: k })
        added = true
    }
    if (added) label.jkInherit = have
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
