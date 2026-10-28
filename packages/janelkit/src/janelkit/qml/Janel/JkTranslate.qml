// transform: translate() de una caja. Lo crea Jk.flexDecorations solo si se desplaza.
import QtQuick

Translate {
    property Item box: null
    x: box ? box.jkTx : 0
    y: box ? box.jkTy : 0
}
