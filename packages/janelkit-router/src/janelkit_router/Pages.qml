// <Pages stack={nav} />: muestra la página de arriba de una pila de janelkit_router.pages().
// Es un mazo de JanelKit (JkDeck): las páginas las crea Python (PageStack, con
// janelkit.ext.Container.mount) y la visible ocupa todo el sitio. Admite transition:.
import QtQuick
import Janel

JkDeck {
    id: pages
    property JkHost stack
    // Atrás con Alt+← o el botón «atrás» del ratón: lo que no atendió un elemento de
    // dentro llega aquí (la pila más interna primero). Python decide si se puede volver.
    property bool jkCanGoBack: false
    signal jkBack()
    Keys.onPressed: (event) => {
        if (jkCanGoBack && ((event.key === Qt.Key_Left && (event.modifiers & Qt.AltModifier)) || event.key === Qt.Key_Back)) {
            event.accepted = true
            jkBack()
        }
    }
    TapHandler {
        acceptedButtons: Qt.BackButton
        enabled: pages.jkCanGoBack
        onTapped: pages.jkBack()
    }
}
