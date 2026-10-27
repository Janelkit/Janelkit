// Column con el motor de <flex> (flex.js): la usa el compilador cuando la columna o sus
// hijos usan algo que un layout de Qt no sabe hacer (ver FxColumn.qml). Valores por
// defecto de siempre: los bloques (texto, cajas) ocupan el ancho, los controles se
// quedan a la izquierda y solo encoge lo que tiene flex.
FxFlex {
    direction: "column"
    alignItems: ""
    fxLegacy: true
}
