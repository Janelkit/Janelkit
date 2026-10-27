// Papel interactivo de una caja (as="button", on:click…): lo que la anuncia a los lectores
// de pantalla y la activa con el teclado. Lo crea Fx.flexDecorations solo si la caja
// tiene un papel distinto de "box"; las demás no pagan nada de esto.
import QtQuick

QtObject {
    id: role
    property Item box: null
    readonly property string kind: box ? box.fxAs : "box"
    readonly property bool spaceActivates: ["button", "checkbox", "switch", "tab", "menuitem", "option"].indexOf(kind) >= 0
    readonly property bool enterActivates: ["button", "link", "tab", "menuitem", "option"].indexOf(kind) >= 0

    readonly property Binding fxRoleBinding: Binding {
        target: role.box ? role.box.Accessible : null
        property: "role"
        value: ({
            "box": Accessible.Button, "button": Accessible.Button, "link": Accessible.Link,
            "checkbox": Accessible.CheckBox, "switch": Accessible.CheckBox, "tab": Accessible.PageTab,
            "menuitem": Accessible.MenuItem, "option": Accessible.ListItem, "listitem": Accessible.ListItem,
            "list": Accessible.List, "menu": Accessible.PopupMenu, "tablist": Accessible.PageTabList,
            "dialog": Accessible.Dialog, "heading": Accessible.Heading, "region": Accessible.Pane,
        })[role.kind] || Accessible.Grouping
    }
    readonly property Binding fxIgnoredBinding: Binding {
        target: role.box ? role.box.Accessible : null
        property: "ignored"
        value: role.kind === "box"
    }
    // checkable, checked y selected los añade el compilador solo a las cajas que los usan.
    readonly property Connections fxAccessible: Connections {
        target: role.box ? role.box.Accessible : null
        function onPressAction() { if (role.kind !== "box") role.box.fxActivate(-1, -1, Qt.LeftButton) }
        function onToggleAction() { if (role.box.Accessible.checkable) role.box.fxActivate(-1, -1, Qt.LeftButton) }
    }
    // Como un botón: Intro pulsa al momento; Espacio, al soltarlo (mientras tanto, :pressed).
    readonly property Connections fxKeys: Connections {
        target: role.box ? role.box.Keys : null
        function onPressed(event) {
            if (event.key === Qt.Key_Space && role.spaceActivates) {
                if (!event.isAutoRepeat) role.box.fxKeyDown = true
                event.accepted = true
            } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && role.enterActivates) {
                role.box.fxActivate(-1, -1, Qt.LeftButton)
                event.accepted = true
            }
        }
        function onReleased(event) {
            if (event.key === Qt.Key_Space && role.box.fxKeyDown && !event.isAutoRepeat) {
                role.box.fxKeyDown = false
                role.box.fxActivate(-1, -1, Qt.LeftButton)
                event.accepted = true
            }
        }
    }
    readonly property Connections fxFocus: Connections {
        target: role.box
        function onActiveFocusChanged() { if (!role.box.activeFocus) role.box.fxKeyDown = false }
    }
}
