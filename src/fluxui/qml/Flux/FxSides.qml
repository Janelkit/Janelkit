// Bordes por lado de un <flex> (border-top, border-left…). Lo crea Fx.flexDecorations
// solo cuando se usan. Con radio, los lados son rectos (sin curva en las esquinas).
import QtQuick

Item {
    property Item box: null
    readonly property bool fxDecoration: true  // events.py: no es destino del puntero
    anchors.fill: parent
    z: 1
    visible: box !== null && !box.fxHidden

    Rectangle {
        visible: width > 0 && height > 0
        width: parent.width
        height: box ? box.fxBorderTopW : 0
        color: box ? box.fxBorderTopColor : "transparent"
    }
    Rectangle {
        visible: width > 0 && height > 0
        y: parent.height - height
        width: parent.width
        height: box ? box.fxBorderBottomW : 0
        color: box ? box.fxBorderBottomColor : "transparent"
    }
    Rectangle {
        visible: width > 0 && height > 0
        width: box ? box.fxBorderLeftW : 0
        height: parent.height
        color: box ? box.fxBorderLeftColor : "transparent"
    }
    Rectangle {
        visible: width > 0 && height > 0
        x: parent.width - width
        width: box ? box.fxBorderRightW : 0
        height: parent.height
        color: box ? box.fxBorderRightColor : "transparent"
    }
}
