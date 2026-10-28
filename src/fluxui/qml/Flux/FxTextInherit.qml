// Un valor de texto heredado (color, tamaño…) aplicado a un <Text>: el de la caja más
// cercana que lo fija (FxContext). Fx.textInherit crea uno por clave que alguna caja de
// fuera declara; mientras ninguna lo fije, el <Text> conserva el suyo.
import QtQuick
import "fx.js" as Fx

Binding {
    property string key
    value: Fx.inherited(target ? target.fxCtx : null, key)
    // No `value !== undefined`: en Qt 6.8, value no avisa al cambiar y `when` no se reevaluaría.
    when: Fx.inherited(target ? target.fxCtx : null, key) !== undefined
}
