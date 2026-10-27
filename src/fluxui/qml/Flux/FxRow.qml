// Row: una fila dispuesta por un layout de Qt (FxQtBox), la vía rápida. Si la fila o
// sus hijos usan algo que el layout no sabe hacer, el compilador pone FxFlexRow, con el
// motor de <flex>. Mismos valores por defecto en las dos: los hijos se centran en
// vertical y solo encoge lo que tiene flex.
FxQtBox {
    direction: "row"
    alignItems: ""
    fxLegacy: true
}
