// Un valor de texto heredado (color, tamaño…) aplicado a un <Text>: el de la caja más
// cercana que lo fija (JkContext). Jk.textInherit crea uno por clave que alguna caja de
// fuera declara; mientras ninguna lo fije, el <Text> conserva el suyo.
import QtQuick
import "jk.js" as Jk

Binding {
    property string key
    // Si deja de haber valor (p. ej. al destruirse la vista, jkCtx pasa a null), `value`
    // cambia antes que `when`: sin el respaldo se aplicaría undefined a un color, con aviso.
    value: {
        const v = Jk.inherited(target ? target.jkCtx : null, key)
        return v !== undefined || !target ? v : target[property]
    }
    // No `value !== undefined`: en Qt 6.8, value no avisa al cambiar y `when` no se reevaluaría.
    when: Jk.inherited(target ? target.jkCtx : null, key) !== undefined
}
