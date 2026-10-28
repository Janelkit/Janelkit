// Row con el motor de <flex> (flex.js): la usa el compilador cuando la fila o sus hijos
// usan algo que un layout de Qt no sabe hacer (ver JkRow.qml). Valores por defecto de
// siempre: los hijos se centran en vertical y solo encoge lo que tiene flex.
JkFlex {
    direction: "row"
    alignItems: ""
    jkLegacy: true
}
