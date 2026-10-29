// Motor de disposición de <flex> (y de Column/Row, que son atajos de <flex>).
//
// Un subconjunto del algoritmo flexbox de CSS: dirección, salto de línea (wrap),
// separaciones, márgenes (también `auto`), grow/shrink/basis, order, align-items,
// align-self, align-content, justify-content (también space-*), mín./máx. y %.
//
// Cuándo se calcula: un cambio que afecta a la disposición (tamaño del contenedor,
// tamaño natural de un hijo, un hijo que aparece…) pone su contenedor en una cola.
// La cola se vacía en la fase de "polish" de Qt Quick, justo antes de dibujar el
// fotograma (JkPolisher, en Python), o en la siguiente vuelta del bucle de eventos
// si la ventana no va a dibujar. Así nunca se ve un fotograma a medio colocar, y
// muchos cambios seguidos cuestan una sola pasada.
//
// Lo que se lee de cada hijo (protocolo de los elementos de JanelKit):
//   - implicitWidth/implicitHeight: tamaño natural. El ancho natural no depende del
//     ancho asignado (un texto lo da sin cortar); el alto natural sí (texto que se corta).
//   - Layout.preferred*/minimum*/maximum*/fill*/*Margin: tamaño, límites y márgenes
//     (los mismos que entiende un layout de Qt).
//   - jkFlex (grow), jkSelfAlign, jkSelfStretch; y, si el compilador los declara,
//     jkOrder, jkShrink, jkBasis, jkBasisPct, jkWidthPct, jkHeightPct, jkAutoMargin.
//   - jkSkip (Repeater: no ocupa sitio) y visible.
// Cada elemento avisa a su contenedor con Jk.touch(parent, item, ...) en un binding que
// depende de todo lo anterior (salvo el tamaño natural: Jk.resized en sus manejadores),
// así que no hace falta conectar señales hijo a hijo. Lo leído de cada hijo se guarda
// en su jkHints hasta que avisa: una pasada solo vuelve a leer tamaños naturales.
.pragma library
// Bucles con índice (no for…of): en el motor JS de Qt son varias veces más rápidos,
// y Set/Map buscan de forma lineal. Esto se ejecuta en cada pasada de disposición.

const AUTO_TOP = 1, AUTO_RIGHT = 2, AUTO_BOTTOM = 4, AUTO_LEFT = 8
const MAX_ROUNDS = 64
const SKIP = { skip: true }

let queue = []
// El estado de cada caja va en un objeto JS (jkState) que se modifica sin reasignarlo:
// touch() se llama dentro de bindings, y escribir ahí una propiedad QML leída sería un
// bucle. (Set y Map no sirven: en el motor JS de Qt buscan de forma lineal.)
function queued(box) { const st = box.jkState; return !!st && st.queued }
function busy(box) { const st = box.jkState; return !!st && st.busy }
let polishers = []
let requested = false
let flushing = false

// -- cola --------------------------------------------------------------------
function registerPolisher(p) {
    if (polishers.indexOf(p) < 0) polishers.push(p)
    if (queue.length) p.request()
}

function unregisterPolisher(p) {
    const i = polishers.indexOf(p)
    if (i >= 0) polishers.splice(i, 1)
}

function schedule(box) {
    const st = box ? box.jkState : undefined
    if (!st || st.queued || st.busy) return
    st.queued = true
    queue.push(box)
    if (flushing || requested) return
    requested = true
    for (let i = 0; i < polishers.length; ++i) polishers[i].request()
    Qt.callLater(flush)
}

// Un hijo (`item`) cambió algo que afecta a la disposición: `p` es su padre (el `lay`
// de un contenedor flex, o cualquier otro objeto, que se ignora). Lo que se guardó de
// ese hijo deja de valer.
function touch(p, item) {
    const box = p ? p.jkBox : undefined
    if (!box) return true
    item.jkHints = null
    schedule(box)
    return true
}

// Cambió un tamaño natural o algo del propio contenedor: solo hay que volver a colocar.
function resized(p) {
    if (p && p.jkBox) schedule(p.jkBox)
    return true
}

// Al terminar de crearse, un contenedor se coloca ya: quien lo crea (una lista, un
// layout de Qt) lee su tamaño natural enseguida, sin esperar al siguiente fotograma.
// Dentro de otro <flex> no hace falta: lo coloca su contenedor, ya con su tamaño.
function layoutNow(box) {
    const p = box.parent
    if (p && p.jkBox) schedule(box)
    else if (!busy(box)) layout(box)
}

function depth(item) {
    let n = 0
    for (let p = item.parent; p; p = p.parent) n++
    return n
}

function flush() {
    if (flushing) return
    flushing = true
    requested = false
    try {
        for (let round = 0; queue.length && round < MAX_ROUNDS; ++round) {
            const batch = queue
            queue = []
            // De fuera adentro: cada contenedor coloca en la misma pasada a los de dentro
            // que siguen pendientes (ver `place` y `measure`), ya con su tamaño final.
            // Si un tamaño natural cambia, el de fuera vuelve a la cola (otra vuelta).
            const order = batch.map((b) => ({ box: b, depth: depth(b) }))
            order.sort((a, b) => a.depth - b.depth)
            for (let i = 0; i < order.length; ++i)
                if (queued(order[i].box)) layout(order[i].box)
        }
        if (queue.length) {
            console.warn("JanelKit: la disposición no se estabiliza (¿un tamaño que depende de sí mismo?)")
            for (let i = 0; i < queue.length; ++i) if (queue[i].jkState) queue[i].jkState.queued = false
            queue = []
        }
    } finally {
        flushing = false
    }
}

// -- lectura de los hijos ----------------------------------------------------
function num(v, d) {
    return v === undefined || v === null || isNaN(v) ? d : v
}

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(v, hi))
}

// Lo que no cambia de una pasada a otra (hasta que el hijo avisa con touch).
function hintsOf(c, box) {
    let h = c.jkHints
    if (h) return h
    if (c.jkSkip === true) return SKIP
    const L = box.jkLayoutOf(c)
    const auto = num(c.jkAutoMargin, 0)
    const self = c.jkSelfAlign
    h = {
        skip: false,
        order: num(c.jkOrder, 0),
        auto: auto,
        // márgenes en coordenadas físicas (los `auto` valen 0 y se reparten aparte)
        ml: auto & AUTO_LEFT ? 0 : num(L.leftMargin, 0),
        mr: auto & AUTO_RIGHT ? 0 : num(L.rightMargin, 0),
        mt: auto & AUTO_TOP ? 0 : num(L.topMargin, 0),
        mb: auto & AUTO_BOTTOM ? 0 : num(L.bottomMargin, 0),
        pw: num(L.preferredWidth, -1),
        ph: num(L.preferredHeight, -1),
        wp: num(c.jkWidthPct, 0),
        hp: num(c.jkHeightPct, 0),
        minW: num(L.minimumWidth, 0),
        maxW: num(L.maximumWidth, Infinity),
        minH: num(L.minimumHeight, 0),
        maxH: num(L.maximumHeight, Infinity),
        fillW: L.fillWidth === true,
        fillH: L.fillHeight === true,
        flex: num(c.jkFlex, 0),
        shrink: num(c.jkShrink, NaN),
        basis: num(c.jkBasis, -2),
        basisPct: num(c.jkBasisPct, 0),
        selfAlign: self === undefined ? "" : self,
        selfStretch: c.jkSelfStretch === true,
        scrollable: c.jkScrollable === true,
        isFlex: c.jkIsFlex === true,
        pages: c.jkPages === true,  // <Pages>/<Sections>: su mínimo es el de la página visible
        wraps: c.jkWraps === true,
        // Usa :first-child o :last-child (el compilador declara jkFirst y jkLast).
        marks: typeof c.jkFirst === "boolean",
        // position: "" (en el flujo), "relative", "absolute" o "fixed"
        pos: c.jkPosition === undefined || c.jkPosition === "static" ? "" : c.jkPosition,
    }
    if (h !== undefined && c.jkHints !== undefined) c.jkHints = h
    return h
}

// Datos de un hijo para esta pasada, en los ejes del contenedor (horizontal o no).
// El objeto se reutiliza de una pasada a otra (h.it): crear miles de objetos por
// fotograma hace que el recolector de basura de JS pare la interfaz.
function itemOf(c, h, box, horiz, innerW, innerH) {
    let it = h.it
    if (!it) {
        it = {
            c: null, h: null, index: 0, order: 0, auto: 0,
            grow: 0, shrink: 1, basis: 0, basisFixed: -1, hypo: 0, pref: 0, floor: 0, size: 0, target: 0,
            minMain: 0, maxMain: Infinity, minCross: 0, maxCross: Infinity, frozen: false,
            cross: 0, natCross: 0, crossPos: 0, mainPos: 0,
            ml: 0, mr: 0, mt: 0, mb: 0, mS: 0, mE: 0, cS: 0, cE: 0,
            autoMS: false, autoME: false, autoCS: false, autoCE: false,
            pw: -1, ph: -1, minW: 0, maxW: Infinity, minH: 0, maxH: Infinity,
            fillW: false, fillH: false, selfAlign: "", selfStretch: false, stretch: false,
        }
        if (h !== SKIP && c.jkHints === h) h.it = it
    }
    it.c = c; it.h = h
    it.order = h.order; it.auto = h.auto
    it.shrink = 1; it.size = 0; it.frozen = false; it.cross = 0; it.natCross = 0
    it.ml = h.ml; it.mr = h.mr; it.mt = h.mt; it.mb = h.mb
    // Tamaño preferido explícito (px o %), o -1 si es el natural.
    it.pw = h.wp > 0 ? innerW * h.wp / 100 : h.pw
    it.ph = h.hp > 0 ? innerH * h.hp / 100 : h.ph
    it.minW = h.minW; it.maxW = h.maxW; it.minH = h.minH; it.maxH = h.maxH
    it.fillW = h.fillW; it.fillH = h.fillH
    it.selfAlign = h.selfAlign; it.selfStretch = h.selfStretch
    const fillMain = horiz ? h.fillW : h.fillH
    it.grow = h.flex > 0 ? h.flex : (fillMain ? 1 : 0)
    if (!isNaN(h.shrink)) it.shrink = h.shrink
    else if (box.jkLegacy) it.shrink = it.grow > 0 ? 1 : 0  // como los layouts de Qt: solo encoge lo que crece
    // Basis: flex: N es `N 1 0` (parte de cero); flex-basis/jkBasis la fija.
    if (h.basis >= 0) it.basisFixed = h.basis
    else if (h.basisPct > 0) it.basisFixed = (horiz ? innerW : innerH) * h.basisPct / 100
    else if (h.flex > 0 && h.basis !== -1) it.basisFixed = 0
    else it.basisFixed = -1
    return it
}

// Ancho natural (sin cortar) y alto natural para el ancho que tenga.
function prefW(it) { return it.pw >= 0 ? it.pw : it.c.implicitWidth }
function prefH(it) { return it.ph >= 0 ? it.ph : it.c.implicitHeight }

// Mínimo automático en el eje principal al encoger (min-width/min-height: auto de CSS).
function autoMin(it, horiz, legacy) {
    const h = it.h
    const explicit = horiz ? it.minW : it.minH
    if (explicit > 0) return explicit
    if (legacy || h.scrollable) return 0
    if (!horiz) return prefH(it)               // en columna no se encoge por debajo del contenido
    if (h.isFlex) return it.c.jkQt === true ? qtMinW(it.c) : it.c.jkMinW
    if (h.pages) return pagesMinW(it.c)
    if (h.wraps) return 0                      // texto que se corta: puede estrecharse
    return prefW(it)
}

// Mínimo de contenido en ancho de una caja con layout de Qt (JkQtBox): lo que flex.js
// calcularía para ella (ver `minContent` en arrange). Solo se pide al encoger una fila.
function qtMinW(box) {
    const lay = box.jkLay
    const horiz = box.direction === "row" || box.direction === "row-reverse"
    const legacy = box.jkLegacy === true
    let m = 0, n = 0
    const kids = lay ? lay.children : []
    for (let i = 0; i < kids.length; ++i) {
        const c = kids[i]
        const h = hintsOf(c, box)
        // Dentro de un layout de Qt los hijos no avisan (Jk.touch): no se guarda nada.
        if (c.jkHints === h) c.jkHints = null
        if (h.skip || !c.visible) continue
        const it = itemOf(c, h, box, horiz, 0, 0)
        const v = autoMin(it, true, legacy) + it.ml + it.mr
        if (horiz) m += v
        else m = Math.max(m, v)
        n++
    }
    if (horiz) m += pad(box.columnGap, box.gap) * Math.max(0, n - 1)
    return m + pad(box.leftPadding, box.padding) + pad(box.rightPadding, box.padding) + box.jkBorderLeftW + box.jkBorderRightW
}

// Mínimo de contenido en ancho de <Pages>/<Sections>: el de su página visible (con
// <Sections>, la de la pila visible; JkPages.jkMinW), con la página ya colocada.
function pagesMinW(pages) {
    measure(pages)
    return pages.jkMinW
}

// padding y gap por lado sin fijar (NaN): los generales (como Jk.pad).
function pad(own, all) {
    return isNaN(own) ? all : own
}

// -- disposición -------------------------------------------------------------
function layout(box) {
    const st = box.jkState
    if (!st) return
    st.queued = false
    // Oculta (ella o algo por encima: {#hidden}, otra pestaña, una página de debajo): se
    // queda como estaba y se coloca al volver a verse (JkFlex.onVisibleChanged). Si no,
    // ocultar un subárbol lo recolocaría entero sin contar a sus hijos (todos invisibles):
    // tamaños 0, y una lista de dentro crearía todas sus filas.
    if (!box.visible) {
        st.stale = true
        return
    }
    st.stale = false
    if (box.jkPages === true) {
        st.busy = true
        try { arrangePages(box) } finally { st.busy = false }
        return
    }
    const lay = box.jkLay
    // Un contenedor que se está destruyendo (fila retirada) ya no tiene sus funciones.
    if (!lay || typeof box.jkMirrored !== "function") return
    st.busy = true
    try {
        const r = arrange(box, lay, result)
        // Todavía ocupado: si el tamaño de la caja sigue al natural, cambiará con esto, y
        // ya se ha colocado contando con él. El contenedor de fuera sí vuelve a la cola.
        box.jkMinW = r.minW
        box.fillMain = box.jkFill || r.grows
        box.implicitWidth = r.w
        box.implicitHeight = r.h
    } finally {
        st.busy = false
    }
}

const result = { w: 0, h: 0, minW: 0, grows: false }

// <Pages>/<Sections> (JkPages): solo se ve una página, y su raíz se coloca como un bloque
// en una columna: ocupa todo el contenedor salvo que fije su tamaño (width, height,
// max-width…) o align-self; los márgenes `auto` reparten lo que sobra (margin: 0 auto
// la centra).
function arrangePages(pages) {
    const kids = pages.children, cur = pages.currentIndex
    const page = cur >= 0 && cur < kids.length ? kids[cur] : null  // JkPages ya oculta las demás
    if (!page) {
        pages.jkMinW = 0
        pages.implicitWidth = 0
        pages.implicitHeight = 0
        return
    }
    const h = hintsOf(page, pages)
    const W = pages.width, H = pages.height
    const availW = Math.max(0, W - h.ml - h.mr), availH = Math.max(0, H - h.mt - h.mb)
    const self = h.selfAlign, aligned = self === "start" || self === "center" || self === "end"
    let w = h.fillW && !aligned ? availW : h.pw >= 0 ? h.pw : h.wp > 0 ? W * h.wp / 100 : page.implicitWidth
    w = clamp(w, h.minW, h.maxW)
    place(page, w, null)  // el alto natural depende del ancho
    let hh = h.fillH ? availH : h.ph >= 0 ? h.ph : h.hp > 0 ? H * h.hp / 100 : page.implicitHeight
    hh = clamp(hh, h.minH, h.maxH)
    place(page, null, hh)
    const freeW = Math.max(0, availW - w), freeH = Math.max(0, availH - hh)
    const a = h.auto
    let x = h.ml
    if ((a & AUTO_LEFT) && (a & AUTO_RIGHT)) x += freeW / 2
    else if (a & AUTO_LEFT) x += freeW
    else if (!(a & AUTO_RIGHT) && self === "center") x += freeW / 2
    else if (!(a & AUTO_RIGHT) && self === "end") x += freeW
    let y = h.mt
    if ((a & AUTO_TOP) && (a & AUTO_BOTTOM)) y += freeH / 2
    else if (a & AUTO_TOP) y += freeH
    page.x = x
    page.y = y
    const content = h.pw >= 0 ? h.pw : typeof page.jkMinW === "number" ? page.jkMinW : 0
    pages.jkMinW = Math.max(content, h.minW) + h.ml + h.mr
    pages.implicitWidth = (h.pw >= 0 ? h.pw : page.implicitWidth) + h.ml + h.mr
    pages.implicitHeight = (h.ph >= 0 ? h.ph : page.implicitHeight) + h.mt + h.mb
}

function arrange(box, lay, out) {
    const dir = box.direction
    const horiz = dir === "row" || dir === "row-reverse"
    const reverse = dir === "row-reverse" || dir === "column-reverse"
    const legacy = box.jkLegacy === true
    const wrap = box.wrap === true
    const bt = box.jkBorderTopW, br = box.jkBorderRightW, bb = box.jkBorderBottomW, bl = box.jkBorderLeftW
    const pd = box.padding
    const padL = pad(box.leftPadding, pd) + bl, padR = pad(box.rightPadding, pd) + br
    const padT = pad(box.topPadding, pd) + bt, padB = pad(box.bottomPadding, pd) + bb
    const padMain = horiz ? padL + padR : padT + padB
    const padCross = horiz ? padT + padB : padL + padR
    const rowGap = pad(box.rowGap, box.gap), columnGap = pad(box.columnGap, box.gap)
    const mainGap = horiz ? columnGap : rowGap
    const crossGap = horiz ? rowGap : columnGap

    // ¿El tamaño viene de fuera o sigue al natural? Si sigue al natural, el espacio
    // disponible es el que pide el contenido (no se encoge ni se reparte nada).
    const scroll = box.jkScrollable === true
    const boxW = box.width, boxH = box.height
    const sizedW = box.jkSizedW === true || Math.abs(boxW - box.implicitWidth) >= 0.5
    const sizedH = box.jkSizedH === true || Math.abs(boxH - box.implicitHeight) >= 0.5
    const innerW = Math.max(0, boxW - padL - padR)
    const innerH = Math.max(0, boxH - padT - padB)
    // Desplazable: el contenido sigue a su tamaño natural en el eje principal; con wrap,
    // las líneas se cortan a la caja y se desplaza en el transversal (como en CSS).
    const mainDefinite = (horiz ? sizedW : sizedH) && (!scroll || wrap)
    const crossDefinite = horiz ? sizedH : sizedW
    let mainAvail = horiz ? innerW : innerH
    const crossAvail = horiz ? innerH : innerW

    // Hijos que ocupan sitio, en su orden.
    const kids = lay.children
    const items = []
    let ordered = false
    let outside = null  // position absolute o fixed: fuera del flujo
    let relative = false
    for (let i = 0; i < kids.length; ++i) {
        let c = kids[i]
        let h = hintsOf(c, box)
        if (h.skip) {
            // JkRemote (componente con atributos en su etiqueta): su raíz va en su sitio.
            // Al reordenar filas, Qt mueve el Repeater de cada fila pero no lo que este creó.
            const r = c.jkRoot
            if (!r || r.parent !== lay) continue
            c = r
            h = hintsOf(c, box)
        } else if (c.jkRemote && c.jkRemote.parent === lay) {
            continue  // se coloca donde está su JkRemote
        }
        if (!c.visible) continue
        if (h.pos === "absolute" || h.pos === "fixed") {
            (outside || (outside = [])).push(c)
            continue
        }
        if (h.pos === "relative") relative = true
        if (h.isFlex && (horiz || !crossDefinite)) measure(c)  // se lee su ancho natural
        const it = itemOf(c, h, box, horiz, innerW, innerH)
        it.index = i
        if (it.order !== 0) ordered = true
        items.push(it)
    }
    // :first-child y :last-child: en el orden del documento, entre los hijos visibles.
    for (let k = 0; k < items.length; ++k) {
        const it = items[k]
        if (!it.h.marks) continue
        const first = k === 0, last = k === items.length - 1
        if (it.c.jkFirst !== first) it.c.jkFirst = first
        if (it.c.jkLast !== last) it.c.jkLast = last
    }
    if (ordered) items.sort((a, b) => a.order - b.order || a.index - b.index)

    const alignItems = box.alignItems
    const crossAlign = (it) => {
        if (it.selfAlign) return it.selfAlign
        if (alignItems) return alignItems
        return horiz ? "center" : "start"      // Column/Row: como los layouts de Qt
    }
    const stretches = (it) => {
        if (it.selfStretch) return true
        if (it.selfAlign && it.selfAlign !== "stretch") return false
        if (horiz ? it.fillH : it.fillW) return true
        // align-items: stretch estira lo que no tiene tamaño propio en ese eje
        if (alignItems === "stretch" || it.selfAlign === "stretch") return (horiz ? it.ph : it.pw) < 0
        return false
    }

    // Márgenes en los ejes del contenedor.
    for (let k = 0; k < items.length; ++k) {
        const it = items[k]
        it.mS = horiz ? it.ml : it.mt
        it.mE = horiz ? it.mr : it.mb
        it.cS = horiz ? it.mt : it.ml
        it.cE = horiz ? it.mb : it.mr
        it.autoMS = (it.auto & (horiz ? AUTO_LEFT : AUTO_TOP)) !== 0
        it.autoME = (it.auto & (horiz ? AUTO_RIGHT : AUTO_BOTTOM)) !== 0
        it.autoCS = (it.auto & (horiz ? AUTO_TOP : AUTO_LEFT)) !== 0
        it.autoCE = (it.auto & (horiz ? AUTO_BOTTOM : AUTO_RIGHT)) !== 0
        it.minMain = horiz ? it.minW : it.minH
        it.maxMain = horiz ? it.maxW : it.maxH
        it.minCross = horiz ? it.minH : it.minW
        it.maxCross = horiz ? it.maxH : it.maxW
        it.stretch = stretches(it)
        // En columna con ancho propio, un hijo flex que no se estira toma su ancho natural:
        // hay que colocarlo antes de leerlo (su aviso llegaría con esta caja ocupada).
        if (!horiz && crossDefinite && !it.stretch && it.h.isFlex) measure(it.c)
    }

    // En columna el ancho (eje transversal) se fija antes que el alto: el alto
    // natural de un texto depende de su ancho.
    if (!horiz) {
        // Sin ancho propio, la columna mide lo que su hijo más ancho.
        let guess = crossAvail
        if (!crossDefinite) {
            guess = 0
            for (let k = 0; k < items.length; ++k) { const it = items[k]; guess = Math.max(guess, clamp(prefW(it), it.minCross, it.maxCross) + it.cS + it.cE) }
        }
        for (let k = 0; k < items.length; ++k) {
            const it = items[k]
            const room = Math.max(0, guess - it.cS - it.cE)
            const w = it.stretch && !wrap ? room : Math.min(prefW(it), room)
            it.cross = clamp(w, it.minCross, it.maxCross)
            place(it.c, it.cross, null)
        }
    }

    // Tamaño hipotético en el eje principal.
    let naturalMain = 0
    for (let k = 0; k < items.length; ++k) {
        const it = items[k]
        const pref = horiz ? prefW(it) : prefH(it)
        it.pref = clamp(pref, it.minMain, it.maxMain)
        const b = it.basisFixed >= 0 ? it.basisFixed : pref
        it.basis = b
        it.hypo = clamp(b, it.minMain, it.maxMain)
        it.floor = Math.max(it.minMain, autoMin(it, horiz, legacy))
        naturalMain += it.pref + it.mS + it.mE
    }
    naturalMain += mainGap * Math.max(0, items.length - 1)
    if (!mainDefinite) mainAvail = Math.max(scroll ? mainAvail : 0, naturalMain)

    // Líneas.
    const lines = []
    let line = []
    let used = 0
    for (let k = 0; k < items.length; ++k) {
        const it = items[k]
        const outer = it.hypo + it.mS + it.mE
        if (wrap && line.length && used + mainGap + outer > mainAvail + 0.5) {
            lines.push(line)
            line = []
            used = 0
        }
        used += (line.length ? mainGap : 0) + outer
        line.push(it)
    }
    if (line.length || !lines.length) lines.push(line)

    // Tamaños flexibles, posición en el eje principal y tamaño transversal de cada línea.
    const lineCross = []
    for (let _ln5 = 0; _ln5 < lines.length; ++_ln5) {
        const ln = lines[_ln5]
        resolveFlexible(ln, mainAvail, mainGap)
        for (let k = 0; k < ln.length; ++k) {
            const it = ln[k]
            if (horiz) {
                place(it.c, it.size, null)
                it.cross = null
            } else {
                place(it.c, null, it.size)
            }
        }
        // Tamaño transversal natural de cada elemento (en fila: alto para su ancho).
        let maxCross = 0
        for (let k = 0; k < ln.length; ++k) {
            const it = ln[k]
            if (horiz) it.natCross = clamp(prefH(it), it.minCross, it.maxCross)
            else it.natCross = it.cross
            maxCross = Math.max(maxCross, it.natCross + it.cS + it.cE)
        }
        lineCross.push(maxCross)
        positionMain(ln, mainAvail, mainGap, box.justifyContent)
    }

    // align-content: reparto del espacio transversal entre líneas.
    let crossUsed = crossGap * Math.max(0, lines.length - 1)
    for (let _lc20 = 0; _lc20 < lineCross.length; ++_lc20) { const lc = lineCross[_lc20]; crossUsed += lc }
    let crossStart = 0, crossBetween = crossGap
    if (lines.length === 1 && !wrap) {
        if (crossDefinite) lineCross[0] = Math.max(crossAvail, 0)
    } else if (crossDefinite) {
        const free = crossAvail - crossUsed
        const ac = box.alignContent || "stretch"
        const n = lines.length
        if (free > 0) {
            if (ac === "stretch") { for (let i = 0; i < n; ++i) lineCross[i] += free / n }
            else if (ac === "center") crossStart = free / 2
            else if (ac === "end") crossStart = free
            else if (ac === "space-between") { if (n > 1) crossBetween += free / (n - 1) }
            else if (ac === "space-around") { crossBetween += free / n; crossStart = free / n / 2 }
            else if (ac === "space-evenly") { crossBetween += free / (n + 1); crossStart = free / (n + 1) }
        }
    }

    // Tamaño y posición en el eje transversal.
    let cursor = crossStart
    for (let li = 0; li < lines.length; ++li) {
        const ln = lines[li]
        const lc = lineCross[li]
        let maxBase = 0
        for (let k = 0; k < ln.length; ++k)
            if (crossAlign(ln[k]) === "baseline") maxBase = Math.max(maxBase, ln[k].cS + num(ln[k].c.baselineOffset, 0))
        for (let k = 0; k < ln.length; ++k) {
            const it = ln[k]
            const room = Math.max(0, lc - it.cS - it.cE)
            if (horiz) {
                it.cross = it.stretch && !it.autoCS && !it.autoCE ? clamp(room, it.minCross, it.maxCross) : it.natCross
                place(it.c, null, it.cross)
            } else if (it.stretch && wrap && it.cross !== clamp(room, it.minCross, it.maxCross)) {
                it.cross = clamp(room, it.minCross, it.maxCross)
                place(it.c, it.cross, null)
            }
            const free = lc - it.cross - it.cS - it.cE
            let pos
            const a = crossAlign(it)
            if (it.autoCS && it.autoCE) pos = it.cS + Math.max(0, free) / 2
            else if (it.autoCS) pos = it.cS + Math.max(0, free)
            else if (it.autoCE) pos = it.cS
            else if (it.stretch || a === "start" || a === "stretch") pos = it.cS
            else if (a === "end") pos = lc - it.cross - it.cE
            else if (a === "center") pos = it.cS + free / 2
            else if (a === "baseline") pos = maxBase - num(it.c.baselineOffset, 0)
            else pos = it.cS
            it.crossPos = cursor + pos
        }
        cursor += lc + crossBetween
    }

    // Coordenadas finales dentro del contenedor.
    const mirror = box.jkMirrored() === true
    for (let k = 0; k < items.length; ++k) {
        const it = items[k]
        const mainSize = it.size
        let mp = it.mainPos
        if (reverse) mp = mainAvail - mp - mainSize
        let x, y, w, h
        if (horiz) { x = mp; y = it.crossPos; w = mainSize; h = it.cross }
        else { x = it.crossPos; y = mp; w = it.cross; h = mainSize }
        if (mirror) x = (horiz ? mainAvail : crossAvail) - x - w
        it.c.x = padL + x
        it.c.y = padT + y
    }
    // position: relative: se desplaza desde su sitio sin mover a los demás.
    if (relative) {
        for (let k = 0; k < items.length; ++k) {
            const it = items[k]
            if (it.h.pos !== "relative") continue
            const l = edge(it.c.jkLeft, innerW), r = edge(it.c.jkRight, innerW)
            const t = edge(it.c.jkTop, innerH), b = edge(it.c.jkBottom, innerH)
            it.c.x += !isNaN(l) ? l : !isNaN(r) ? -r : 0
            it.c.y += !isNaN(t) ? t : !isNaN(b) ? -b : 0
        }
    }
    if (outside) for (let k = 0; k < outside.length; ++k) placeOutside(outside[k], box, lay, padL, padT)

    // Tamaño natural del contenedor y del contenido.
    let natCross = 0
    if (wrap && mainDefinite) {
        natCross = crossGap * Math.max(0, lines.length - 1)
        for (let li = 0; li < lines.length; ++li) {
            let m = 0
            for (let k = 0; k < lines[li].length; ++k) { const it = lines[li][k]; m = Math.max(m, it.natCross + it.cS + it.cE) }
            natCross += m
        }
    } else {
        for (let k = 0; k < items.length; ++k) {
            const it = items[k]
            const nc = horiz ? it.natCross : clamp(prefW(it), it.minCross, it.maxCross)
            natCross = Math.max(natCross, nc + it.cS + it.cE)
        }
    }
    // Mínimo de contenido en ancho (lo usa un contenedor de fuera al encoger).
    let minContent = 0
    for (let k = 0; k < items.length; ++k) {
        const it = items[k]
        const m = autoMin(it, true, legacy) + it.ml + it.mr
        if (horiz && !wrap) minContent += m
        else minContent = Math.max(minContent, m)
    }
    if (horiz && !wrap) minContent += mainGap * Math.max(0, items.length - 1)

    const contentMain = naturalMain
    const w = (horiz ? contentMain : natCross) + padL + padR
    const h = (horiz ? natCross : contentMain) + padT + padB
    if (scroll && wrap) {
        lay.width = horiz ? boxW : Math.max(boxW, w)
        lay.height = horiz ? Math.max(boxH, h) : boxH
    } else if (scroll) {
        lay.width = horiz ? Math.max(innerW, mainAvail) + padL + padR : boxW
        lay.height = horiz ? boxH : Math.max(innerH, mainAvail) + padT + padB
    }
    let grows = false
    for (let k = 0; k < items.length; ++k) { const it = items[k]; if (it.h.flex > 0) grows = true }
    out.w = w
    out.h = h
    out.minW = scroll ? padL + padR : minContent + padL + padR
    out.grows = grows
    return out
}

// -- position: absolute y fixed ------------------------------------------------
// top/left…: número (px) o texto "50%" (del tamaño del bloque contenedor); NaN si no se fija.
function edge(v, size) {
    if (v === undefined || v === null || v === "") return NaN
    if (typeof v === "number") return v
    const s = String(v).trim()
    const n = parseFloat(s)
    if (isNaN(n)) return NaN
    return s.endsWith("%") ? size * n / 100 : n
}

// Bloque contenedor: la caja antecesora más cercana con position (su interior, dentro
// del borde) o, si no hay, o con position: fixed, toda la ventana.
function containingBlock(c) {
    let top = c
    if (c.jkPosition === "absolute") {
        for (let p = c.parent; p; p = p.parent) {
            if (p.jkLay && p.jkPosition && p.jkPosition !== "static") {
                const bl = p.jkBorderLeftW, bt = p.jkBorderTopW
                return { item: p, x: bl, y: bt, w: p.width - bl - p.jkBorderRightW, h: p.height - bt - p.jkBorderBottomW }
            }
        }
    }
    while (top.parent) top = top.parent
    return { item: top, x: 0, y: 0, w: top.width, h: top.height }
}

// Coloca un hijo fuera del flujo: tamaño propio o el que dejan left y right (top y
// bottom), y posición respecto a su bloque contenedor. Sin top/left/right/bottom se
// queda al principio del contenedor (su sitio "estático", simplificado).
function placeOutside(c, box, lay, padL, padT) {
    const h = hintsOf(c, box)
    const cb = containingBlock(c)
    const l = edge(c.jkLeft, cb.w), r = edge(c.jkRight, cb.w)
    const t = edge(c.jkTop, cb.h), b = edge(c.jkBottom, cb.h)
    if (h.isFlex) measure(c)
    // width: 100% llega como fillWidth (el compilador lo usa para los layouts de Qt): fuera del flujo es el 100 %.
    let w = h.wp > 0 ? cb.w * h.wp / 100 : h.fillW ? cb.w : h.pw
    if (w < 0) w = !isNaN(l) && !isNaN(r) ? cb.w - l - r - h.ml - h.mr : c.implicitWidth
    place(c, clamp(w, h.minW, h.maxW), null)
    let ht = h.hp > 0 ? cb.h * h.hp / 100 : h.fillH ? cb.h : h.ph
    if (ht < 0) ht = !isNaN(t) && !isNaN(b) ? cb.h - t - b - h.mt - h.mb : c.implicitHeight
    place(c, null, clamp(ht, h.minH, h.maxH))
    const o = cb.item.mapToItem(lay, cb.x, cb.y)
    if (!isNaN(l)) c.x = o.x + l + h.ml
    else if (!isNaN(r)) c.x = o.x + cb.w - r - c.width - h.mr
    else c.x = padL + h.ml
    if (!isNaN(t)) c.y = o.y + t + h.mt
    else if (!isNaN(b)) c.y = o.y + cb.h - b - c.height - h.mb
    else c.y = padT + h.mt
}

// Un hijo flex pendiente se coloca antes de leer su tamaño natural.
function measure(c) {
    const st = c.jkState
    if (st && (st.queued || st.stale) && !st.busy) layout(c)
    else if (c.jkQt === true) settleQt(c)
}

// Asigna tamaño a un hijo y, si es otro contenedor flex que ha quedado pendiente,
// lo coloca ya: así su alto natural está al día cuando se lee.
function place(c, w, h) {
    if (w !== null) c.width = w
    if (h !== null) c.height = h
    const st = c.jkState
    if (st && (st.queued || st.stale) && !st.busy) layout(c)
    else if (c.jkQt === true) settleQt(c)
}

// Una caja con layout de Qt se coloca en su propio polish, más tarde: aquí se coloca ya
// (ensurePolished), y también lo pendiente de dentro, para que su alto natural esté al
// día cuando se lea. Si no, cada cambio de ancho daba vueltas de más (en la rejilla de
// apps/examples/flex, de 17 a 40 ms por fotograma, con fotogramas de casi 3 s).
function settleQt(box) {
    const lay = box.jkLay
    if (!lay) return
    lay.ensurePolished()
    let changed = false
    const kids = lay.children
    for (let i = 0; i < kids.length; ++i) {
        const k = kids[i]
        const st = k.jkState
        if (st && st.queued && !st.busy) {
            layout(k)
            changed = true
        } else if (k.jkDeep === true && k.visible) {
            const h = k.implicitHeight, w = k.implicitWidth
            settleQt(k)
            changed = changed || h !== k.implicitHeight || w !== k.implicitWidth
        }
    }
    if (changed) lay.ensurePolished()
}

// Reparto del espacio libre de una línea (CSS Flexbox §9.7, simplificado).
function resolveFlexible(ln, avail, gap) {
    let outer = gap * Math.max(0, ln.length - 1)
    for (let k = 0; k < ln.length; ++k) {
        const it = ln[k]
        it.size = it.hypo
        it.frozen = false
        outer += it.mS + it.mE
    }
    let sumHypo = 0
    for (let k = 0; k < ln.length; ++k) { const it = ln[k]; sumHypo += it.hypo }
    const growing = avail - outer - sumHypo > 0
    for (let k = 0; k < ln.length; ++k) {
        const it = ln[k]
        if (growing ? it.grow <= 0 : (it.shrink <= 0 || it.hypo <= it.floor)) {
            it.frozen = true
            it.size = growing ? it.hypo : Math.max(it.hypo, it.floor)
        }
    }
    for (let guard = 0; guard < ln.length + 1; ++guard) {
        let free = avail - outer
        let factors = 0
        let open = 0
        for (let k = 0; k < ln.length; ++k) {
            const it = ln[k]
            if (it.frozen) free -= it.size
            else {
                free -= it.basis
                factors += growing ? it.grow : it.shrink * it.basis
                open++
            }
        }
        if (!open) break
        let violation = 0
        for (let k = 0; k < ln.length; ++k) {
            const it = ln[k]
            if (it.frozen) continue
            let target
            if (growing) target = it.basis + (factors > 0 ? free * it.grow / factors : 0)
            else target = it.basis + (factors > 0 ? free * it.shrink * it.basis / factors : 0)
            const lo = growing ? it.minMain : it.floor
            const fixed = clamp(target, lo, it.maxMain)
            violation += fixed - target
            it.size = fixed
            it.target = target
        }
        if (Math.abs(violation) < 0.01) break
        for (let k = 0; k < ln.length; ++k) {
            const it = ln[k]
            if (it.frozen) continue
            if ((violation > 0 && it.size > it.target) || (violation < 0 && it.size < it.target)) it.frozen = true
        }
    }
    for (let k = 0; k < ln.length; ++k) { const it = ln[k]; it.size = Math.max(0, it.size) }
}

function positionMain(ln, avail, gap, justify) {
    let used = gap * Math.max(0, ln.length - 1)
    let autos = 0
    for (let k = 0; k < ln.length; ++k) {
        const it = ln[k]
        used += it.size + it.mS + it.mE
        if (it.autoMS) autos++
        if (it.autoME) autos++
    }
    let free = avail - used
    let start = 0, between = gap, autoShare = 0
    if (autos && free > 0) {
        autoShare = free / autos
        free = 0
    }
    const n = ln.length
    if (free > 0 || justify === "center" || justify === "end") {
        if (justify === "end") start = free
        else if (justify === "center") start = free / 2
        else if (justify === "space-between") { if (n > 1) between += free / (n - 1) }
        else if (justify === "space-around") { between += free / n; start = free / n / 2 }
        else if (justify === "space-evenly") { between += free / (n + 1); start = free / (n + 1) }
    } else if (free < 0 && (justify === "space-around" || justify === "space-evenly")) {
        start = free / 2
    }
    let pos = start
    for (let k = 0; k < ln.length; ++k) {
        const it = ln[k]
        pos += it.mS + (it.autoMS ? autoShare : 0)
        it.mainPos = pos
        pos += it.size + it.mE + (it.autoME ? autoShare : 0) + between
    }
}
