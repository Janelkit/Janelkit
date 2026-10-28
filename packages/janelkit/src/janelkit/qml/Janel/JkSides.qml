// Bordes por lado de un <flex> (border-top, border-left…). Lo crea Jk.flexDecorations
// solo cuando se usan. Con radio, los lados son rectos (sin curva en las esquinas).
import QtQuick

Item {
    property Item box: null
    readonly property bool jkDecoration: true  // events.py: no es destino del puntero
    anchors.fill: parent
    z: 1
    visible: box !== null && !box.jkHidden

    Rectangle {
        visible: width > 0 && height > 0
        width: parent.width
        height: box ? box.jkBorderTopW : 0
        color: !box ? "transparent" : box.jkBorderTopColor !== undefined ? box.jkBorderTopColor : box.jkBorderColor
    }
    Rectangle {
        visible: width > 0 && height > 0
        y: parent.height - height
        width: parent.width
        height: box ? box.jkBorderBottomW : 0
        color: !box ? "transparent" : box.jkBorderBottomColor !== undefined ? box.jkBorderBottomColor : box.jkBorderColor
    }
    Rectangle {
        visible: width > 0 && height > 0
        width: box ? box.jkBorderLeftW : 0
        height: parent.height
        color: !box ? "transparent" : box.jkBorderLeftColor !== undefined ? box.jkBorderLeftColor : box.jkBorderColor
    }
    Rectangle {
        visible: width > 0 && height > 0
        x: parent.width - width
        width: box ? box.jkBorderRightW : 0
        height: parent.height
        color: !box ? "transparent" : box.jkBorderRightColor !== undefined ? box.jkBorderRightColor : box.jkBorderColor
    }
}
