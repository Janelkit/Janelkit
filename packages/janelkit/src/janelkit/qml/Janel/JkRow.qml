// Row: una fila dispuesta por un layout de Qt (JkQtBox), la vía rápida. Si la fila o
// sus hijos usan algo que el layout no sabe hacer, el compilador pone JkFlexRow, con el
// motor de <flex>. Mismos valores por defecto en las dos: los hijos se centran en
// vertical y solo encoge lo que tiene flex.
JkQtBox {
    direction: "row"
    alignItems: ""
    jkLegacy: true
}
