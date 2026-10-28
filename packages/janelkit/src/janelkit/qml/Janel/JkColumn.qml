// Column: una columna dispuesta por un layout de Qt (JkQtBox), la vía rápida. Si la
// columna o sus hijos usan algo que el layout no sabe hacer (wrap, order, márgenes auto,
// position…), el compilador pone JkFlexColumn, con el motor de <flex>. Mismos valores
// por defecto en las dos: los bloques (texto, cajas) ocupan el ancho, los controles se
// quedan a la izquierda y solo encoge lo que tiene flex.
JkQtBox {
    direction: "column"
    alignItems: ""
    jkLegacy: true
}
