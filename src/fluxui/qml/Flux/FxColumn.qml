// Column: una columna dispuesta por un layout de Qt (FxQtBox), la vía rápida. Si la
// columna o sus hijos usan algo que el layout no sabe hacer (wrap, order, márgenes auto,
// position…), el compilador pone FxFlexColumn, con el motor de <flex>. Mismos valores
// por defecto en las dos: los bloques (texto, cajas) ocupan el ancho, los controles se
// quedan a la izquierda y solo encoge lo que tiene flex.
FxQtBox {
    direction: "column"
    alignItems: ""
    fxLegacy: true
}
