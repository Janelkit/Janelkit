// Componente usado con atributos en su etiqueta (<Tarjeta class="celda" on:click=...>),
// cuya raíz es una caja: los atributos se aplican a esa raíz con Binding (hijos de este
// objeto), sin caja exterior. Ver "Componentes construidos sobre <flex>" en docs/flex.md.
// flex.js coloca la raíz donde está este Repeater (jkRemote), también al reordenar filas.
import QtQuick

Repeater {
    id: remote
    readonly property bool jkSkip: true  // no ocupa sitio en <flex>
    readonly property Item jkRoot: count > 0 ? itemAt(0) : null
    default property list<QtObject> jkBindings
    onJkRootChanged: if (jkRoot) jkRoot.jkRemote = remote
}
