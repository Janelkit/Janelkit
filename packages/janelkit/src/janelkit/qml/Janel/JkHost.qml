// Tipo de las propiedades que reciben un anfitrión de Python (janelkit.ext.Host):
// `property JkHost stack` en un elemento .qml hace que <Elemento stack={nav} /> conecte el
// elemento con `nav` (el runtime llama a nav.attach). En QML la propiedad queda vacía.
import QtQml

QtObject {}
