# Hallazgos: gestor de proyectos (reto 6)

Construido solo con la API pública, sin QML propio, a partir del código del reto 3. Lo que faltaba y entraba en el alcance del núcleo se añadió o se corrigió durante el reto; lo demás queda como propuesta.

Gravedad: **Bloquea** (no se podía hacer o salía mal), **Molesta** (había que dar un rodeo), **Detalle**.

## Antes de empezar: navegación básica en el núcleo

El reto estaba en espera de `janelkit-router`. Al revisar el alcance se separó lo fundamental, que va al núcleo, del enrutado, que sigue siendo un proyecto aparte ([alcance.md](../../../docs/alcance.md)). Se añadió al núcleo antes de construir la aplicación:

- `sections()` y `<Sections>`: secciones paralelas que se conservan, cada una con su pila;
- `navigation()`: la pila desde cualquier página;
- `await nav.push(...)` con `nav.back(valor)`;
- Alt+← y el botón «atrás» del ratón;
- `before_leave`;
- `{#hidden}` (con `{:else}` y transiciones) y `<Pages transition:…>`.

Con eso, la tabla «Por qué necesita un enrutador» del reto queda así:

| Necesidad | Cómo se hizo |
|---|---|
| Rutas con parámetros | Props al apilar (`nav.push(Proyecto, ident=pid)`). No hay una dirección que guardar o compartir: es del enrutador |
| Atrás y adelante | Atrás sí (botón, Alt+←, botón del ratón). Adelante no: es del enrutador |
| Enlaces profundos | `abrir_tarjeta` en `App.janel` (10 líneas): `secciones.show(...)`, `await nav.reset(...)` y `push`, o solo enfocar si el proyecto ya está abierto |
| Secciones paralelas con su pila | `sections(proyectos=..., personas=..., trabajo=...)` |
| Conservar una vista al volver | Las secciones y la página de debajo se conservan; las pestañas, con `{#hidden}` |
| Salir con cambios sin guardar | `before_leave` en Detalle, Ajustes y Persona (también al cerrar la ventana) |
| La misma ruta en otra ventana | Sin hacer (ver abajo) |
| Restaurar la última vista | Sin hacer: es del enrutador |

## Resueltos en el núcleo durante el reto

| # | Qué intenté | Qué pasó | Gravedad | Solución |
|---|---|---|---|---|
| 1 | Cambiar de pestaña con un tablero de 200 tarjetas, o de sección | 239 ms por pestaña y 83 ms por sección; ocultar costaba más que mostrar. Al ocultar, cada caja del subárbol se recolocaba sin contar a sus hijos, que ya eran invisibles: tamaño natural 0. Las filas de una `<List>` medían 0 y la lista creaba **todas** (de 8 a 51 por columna); al mostrar las volvía a soltar. Afectaba a `{#hidden}`, a las secciones y a la página de debajo de una pila | Bloquea (fallo) | Una caja `<flex>` oculta no se recoloca: se queda como estaba y se coloca al volver a verse (`flex.js`, `JkFlex.qml`). Pestaña: 239 → 5 ms; sección: 83 → 6 ms; renombrar a una persona: 25 → 13 ms. Prueba `test_hidden_subtree_keeps_its_layout_and_catches_up_when_shown` (sin el arreglo falla) |
| 2 | Probar «¿Dar de baja?» aceptando el diálogo con `app.answer_dialog(True)` | Con PySide6 6.12 fallaba al leer `buttons` (`Can't find converter for QFlags<…>`). Sin esa lectura, el diálogo llega como un `QPlatformDialogHelper` y el clic se tomaba por «Cancelar». Ninguna prueba aceptaba un `confirm` | Bloquea (fallo) | `dialogs` marca cada diálogo con su tipo (`dialogs.kind(d)`) e `inspect` lo usa. Prueba `test_answer_dialog_accepts_or_cancels_a_confirm` |
| 3 | Pasar la suite con las pruebas del Kanban y del gestor | Las del Kanban fallaban después de las del gestor: las dos apps tienen `services/tablero.py`, y `mount` dejaba en `sys.modules` el primero que se importaba (y su carpeta en `sys.path`) | Molesta (fallo) | Al salir de `mount` se olvidan los módulos de la carpeta de la app. Prueba `test_apps_with_modules_of_the_same_name_do_not_mix` |
| 4 | Ir de «Mi trabajo» a una tarjeta con un detalle sin guardar abierto | `nav.reset(Proyectos)` no decía si se había salido: si el detalle pedía quedarse, el `push` siguiente apilaba el proyecto igualmente | Molesta | `pop`, `back`, `replace` y `reset` se pueden esperar: `True` si se salió, `False` si un `before_leave` lo impidió. Prueba `test_leaving_can_be_awaited_to_chain_navigation` |
| 5 | Abrir y cerrar proyectos | Avisos `ReferenceError: jkevents is not defined` en `JkBox.qml`: un `Qt.callLater` llegaba con la página ya destruida | Detalle (fallo) | La función comprueba que el contexto sigue ahí |
| 6 | Mover una tarjeta con la sección Personas abierta detrás | 26 ms en vez de 11: la lista de personas, oculta, seguía recalculando «N tarjetas» fila a fila (cada fila recorría los 10 proyectos). Lo oculto conservaba su estado y también sus enlaces activos | Molesta | **Lo que no se ve espera** (`reactivity.Gate`): los efectos de plantilla de `{#hidden}`, de las secciones que no se muestran y de las páginas de debajo se aplazan y se ejecutan una vez al volver a verse. Los `effect`, temporizadores y tareas del script siguen. Con el recuento fila a fila de antes, mover pasa de 26 a 8,6 ms y renombrar de 14 a 2,4 ms. La app conserva el `computed` (sigue ayudando cuando la lista se ve: buscar, 12 → 6,5 ms). Pruebas en `tests/test_hidden_gate.py` |
| 12 | Crear una columna; ver Proyectos con más fichas de las que caben a lo ancho | No había forma de crear columnas: «+ Columna» estaba fuera de la ventana. La página medía lo que su contenido (todas las fichas o columnas en una fila: 1602 px en una ventana de 1280), y la lateral se aplastaba. Tampoco ocupaba el alto: columnas de 276 px y la lista de Personas de 200 px en una ventana de 850 | Bloquea (fallo) | Dos causas en `JkPages`: el `StackLayout` no estiraba la página (no tenía `Layout.fill*`) y daba como mínimo su ancho natural, que el motor no podía rebajar porque no es una caja `<flex>`. Ahora `JkPages` lo coloca el motor (`flex.js`, `arrangePages`): la página llena el contenedor, su mínimo es el contenido de la página visible, y su raíz puede ajustarlo con `width`, `height`, `max-width`, `margin` (`0 auto` la centra) y `align-self`. Pruebas `test_a_page_fits_its_window_and_its_scrolling_grid_wraps` (sin el arreglo, el botón queda en x=2710 en una ventana de 800) y `test_the_root_of_a_page_adjusts_its_place_with_css` |
| 13 | La rejilla de proyectos con `flex-wrap: wrap` y `overflow: auto` | No bajaba a otra fila: el contenido desplazable tomaba su ancho natural y todo quedaba en una línea | Molesta (fallo) | Con `wrap`, las líneas se cortan al tamaño de la caja y se desplaza en el otro eje, como en CSS (`flex.js`). La misma prueba lo comprueba |

## Pendientes (propuestas)

| # | Qué intenté | Qué pasó | Gravedad | Propuesta |
|---|---|---|---|---|
| 7 | Medir la memoria al abrir y cerrar proyectos | Con `inspect` y `processEvents()` parecía una fuga (+190 MB por vuelta): fuera de `exec()`, Qt no entrega los `deleteLater` de las filas y páginas retiradas. Entregándolos, se queda estable (~195 MB tras 4 vueltas de 10 proyectos) | Molesta | `MountedApp.process()` podría entregar los borrados diferidos, para que las pruebas y mediciones vean lo mismo que la app real |
| 8 | `as="navigation"` en la barra lateral | No existe: la lista de papeles no tiene regiones de referencia (navegación, principal, búsqueda) | Detalle | Se usa `region`. Añadir `navigation`, `main` y `search` |
| 9 | La pestaña «Tablero» y la rejilla de columnas con `label="Tablero"` | `inspect.find` encontraba dos (un lector de pantalla tampoco las distinguiría) | Detalle | Es de la app (renombrada a «Columnas del tablero»). El error de `find` ya lo dice bien |
| 10 | Cerrar el detalle con cambios desde el menú contextual de otra tarjeta | El detalle se recrea (`{#key}`) sin preguntar: `before_leave` solo cubre páginas y ventanas | Detalle | Que `{#key}`/`{#if}` puedan consultar los `before_leave` de lo que retiran, o un `ask_to_leave()` público para hacerlo a mano |
| 11 | Atrás y adelante, rutas que guardar o compartir, restaurar la última vista | Fuera del núcleo | Prevista | `janelkit-router`, que ahora puede apoyarse en `PageStack`, `Sections` y `before_leave` |
| 14 | `border: 2px dashed` en el hueco de «Añadir columna» | Solo hay bordes `solid`: avisa («border no válido») y no dibuja el borde. El aviso no se ve con `inspect`, que guarda los avisos sin imprimirlos | Detalle | Se usa `solid`. Admitir `dashed`/`dotted` (QML no los tiene: habría que dibujarlos) |

## Lo que queda del plan

| Parte del plan | Por qué no está |
|---|---|
| Pestaña **Lista** (tabla ordenable y editable, vencidas) | Tiempo: es una tabla con `<List>` y `<flex>`, como la del reto 1 |
| **Ajustes del proyecto:** etiquetas y columnas (la «de hecho»), exportar | Tiempo: las operaciones existen en `tablero.py`; falta la interfaz |
| **Ajustes generales** (tema, archivo, pasos de deshacer) | Tiempo |
| **Otra ventana** con un proyecto | Sin probar: `open_window(Proyecto, ident=...)` debería funcionar sobre los mismos datos, pero `navigation()` en esa ventana no tiene pila. Hace falta decidir si una ventana abierta así lleva su propia pila |

## Mediciones

Windows 11, Python 3.13, PySide6 6.12, sin ventana (`offscreen`), ventana de 1400 × 850, 10 proyectos de 4 × 50 tarjetas (2000) y 300 personas (`python bench.py`). Cada tiempo va desde la acción hasta que el hilo de la interfaz sincroniza el fotograma (eventos, Python, polish y disposición), sin el dibujado.

Las mediciones anteriores al hallazgo 12 se hicieron con las páginas sin llenar la ventana: columnas de 276 px (28 tarjetas creadas al abrir un proyecto) y la lista de Personas de 200 px (11 filas). Ahora miden 639 y 661 px (45 tarjetas y 21 filas): se crea casi el doble y los tiempos suben en proporción; el coste por fila o tarjeta no ha cambiado.

| Medida | Objetivo | Resultado |
|---|---|---|
| Montar la aplicación | — | 187 ms |
| Abrir un proyecto (200 tarjetas, 45 creadas) | < 150 ms | p50 127 ms, máx 181 ms la primera vez; p50 132 ms después |
| Volver a Proyectos | < 30 ms | p50 12 ms |
| Cambiar de pestaña | < 100 ms | p50 7,4 ms, máx 13 ms (antes del hallazgo 1: 239 ms) |
| Cambiar de sección | < 100 ms | p50 9,6 ms, máx 18 ms (antes: 83 ms) |
| Cada pulsación en la búsqueda de Personas (21 filas a la vista) | < 16 ms | p50 13,9 ms, **máx 32 ms** (no cumple en el peor caso: pasar de 1 resultado a los 300 crea las 21 filas de golpe) |
| Renombrar a una persona (se ve en todo) | — | p50 3,9 ms (antes del hallazgo 6: 14 ms) |
| Mover una tarjeta / deshacer | — | p50 10 ms / 4,9 ms (antes del hallazgo 6: 26 / 25 ms) |
| Memoria al abrir y cerrar los 10 proyectos 4 veces | No crece | 219 → 233, 236, 238, 238 MB |

Del resto de «Hecho cuando»:

- **Enlaces de «Mi trabajo»:** llevan a la vista correcta (probado). Adelante y la segunda ventana no están (hallazgo 11 y «Lo que queda del plan»).
- **Deshacer:** toda acción de datos se puede deshacer (tablero, proyectos, personas, miembros).
- **Teclado:** secciones (Ctrl+1/2/3), atrás (Alt+←), tablero (lo del reto 3) y deshacer. La rejilla de proyectos y las listas se recorren con Tab, no con flechas.
