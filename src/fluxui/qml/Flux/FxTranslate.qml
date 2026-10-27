// transform: translate() de una caja. Lo crea Fx.flexDecorations solo si se desplaza.
import QtQuick

Translate {
    property Item box: null
    x: box ? box.fxTx : 0
    y: box ? box.fxTy : 0
}
