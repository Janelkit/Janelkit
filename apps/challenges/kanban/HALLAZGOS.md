# Hallazgos: tablero Kanban (reto 3)

Construido solo con la API pública, sin QML propio. Lo que faltaba y entraba en el alcance del núcleo se añadió o se corrigió durante el reto; lo demás queda como propuesta.

Gravedad: **Bloquea** (no se podía hacer o salía mal), **Molesta** (había que dar un rodeo), **Detalle**.

## Resueltos en el núcleo durante el reto

| # | Qué intenté | Qué pasó | Gravedad | Solución |
|---|---|---|---|---|
| 1 | Arrastrar tarjetas entre columnas y dentro de una | No había arrastrar y soltar ([flex.md](../../../docs/flex.md) lo dejaba «para el reto Kanban») | Bloquea | `draggable` en `<flex>`; `on:dragstart`, `on:dragover`, `on:drop` y `on:dragend` con `DragEvent` (`.data` es cualquier objeto de Python, `.dropped`); `:dragging` y `:drag-over`; una imagen de la caja sigue al puntero; Escape cancela; una pulsación corta sigue siendo un clic, y soltar no es un clic. Va por el mismo enrutado que el resto de eventos (propagación, `prevent()`, `stop()`) |
| 2 | Clic derecho en la primera tarjeta de una columna | No llegaba `on:contextmenu`. El enrutado usaba `childAt` de Qt, que ignora `z`: en una `ListView`, un elemento vacío de z 0 tapa las filas (z 1). Afectaba a `on:contextmenu`, `on:dblclick` y `on:pointer*` en las filas de **cualquier** `<List>` | Bloquea (fallo) | La búsqueda bajo el puntero sigue el orden en que Qt dibuja (por `z`). Prueba `test_routed_events_reach_list_rows_also_while_they_slide` |
| 3 | Arrastrar justo después de mover otra tarjeta | Con `<List animate>`, una fila que aún se desliza queda fuera del alto nuevo de la lista y no recibía eventos (en Qt sí recibe el puntero) | Molesta (fallo) | Si ningún hijo contiene el punto, vale uno cuyo contenido se sale de él y lo contiene, como hace Qt |
| 4 | Soltar en la tarjeta 150 de una columna, o en la columna 15 de 20 | El arrastre no desplazaba la vista: solo se podía soltar en lo visible | Bloquea | Cerca del borde (40 px) de una zona con desplazamiento (`<List>`, `<Scroll>`, `overflow: auto`) esta avanza sola, más deprisa cuanto más cerca |
| 5 | Probar doble clic, menú contextual y atajos con `janelkit.inspect` | No había forma sin `QTest` (fuera de la API pública) | Molesta | `Element.double_click()`, `.right_click()`, `.key("Ctrl+D")`, `.drag_to(destino, cancel=)` y `MountedApp.key("Ctrl+Z")` |
| 6 | Buscar una tarjeta recién movida con `app.find(label=…)` | `inspect` encontraba dos: la nueva y la vieja, que se desvanecía al salir | Molesta (fallo) | `inspect` no ve las filas de `<List>` que salen: ya no cuentan, como en el resto del framework |
| 7 | Que una tarjeta conserve su estado local (la descripción desplegada) al pasar a otra columna | Dentro de su columna se conservaba: `{#each}` mueve la fila. Entre columnas son dos `{#each}` distintos: la fila se quitaba de uno y se creaba otra en el otro, con el estado inicial. Era el criterio de terminado que no se cumplía | Molesta | **Traslado de filas** ([lenguaje.md](../../../docs/lenguaje.md#trasladar-filas-entre-listas)): si en un mismo cambio una fila sale de un `{#each}` con clave y entra en otra instancia de la misma declaración con la misma clave, sus componentes se trasladan con su estado. Las props y los `on:` pasan a la fila nueva. Sin sintaxis nueva. Pruebas en `packages/janelkit/tests/test_each_transfer.py` |
| 8 | Mover una tarjeta con Alt+→ sin perder el foco | La tarjeta era una fila nueva en la otra columna y el foco se perdía; la aplicación lo devolvía a mano (`ui.enfocar` y `on_mount`) | Molesta | Con el 7, la tarjeta trasladada recupera el foco en su vista nueva. `ui.enfocar` queda solo para enfocar las tarjetas nuevas (duplicar, añadir) |

## Pendientes (propuestas)

| # | Qué intenté | Qué pasó | Gravedad | Propuesta |
|---|---|---|---|---|
| 9 | 20 columnas con sus listas | Cada elemento cuesta unos 30–35 KB (un `<Text>` ~33 KB, un `<flex>` ~35 KB; medido con 300 filas sueltas) y una tarjeta lleva unos 8 `<flex>` y 6 `<Text>`: ~0,7 MB por tarjeta creada. `<List>` solo crea las filas visibles, pero las 20 columnas se crean todas aunque solo se vean 5: 270 tarjetas, 246 MB y 1 s al montar | Molesta | Aligerar más `JkText` y `JkBox` (memoria por elemento, no solo tiempo). Para tableros anchos, `<List direction="row">` o virtualizar columnas |
| 10 | Menú contextual con «Mover a ▸» como submenú | No hay `<Menu>`: el menú es un `<flex>` con `position: fixed` en un velo (40 líneas, como `apps/examples/flex`). Sin submenús (las opciones «Mover a…» van en la lista), no se recoloca si no cabe junto al borde de la ventana | Molesta | `<Menu>` en el núcleo (el alcance lo cuenta entre los controles básicos): posición automática, submenús, teclas mostradas y foco devuelto al cerrar |
| 11 | Abrir el menú con el teclado (Mayús+F10) junto a la tarjeta | `KeyEvent` no trae posición y no hay forma de leer dónde está un elemento: el menú se abre en un sitio fijo | Detalle | `ref.rect()` (posición y tamaño en la ventana) o que `<Menu>` se ancle a un `ref` |
| 12 | Soltar encima de una tarjeta, delante o detrás según la mitad | `DragEvent` trae `x`/`y` pero no el tamaño de la caja que escucha | Detalle | Se usa «delante, o detrás si baja en su columna». Añadir `event.width`/`event.height` (de la caja que escucha) |
| 13 | Arrastrar una columna por encima de las tarjetas | Toda caja con `on:drop` es destino: la tarjeta bajo el puntero se marca `:drag-over` aunque no acepte columnas | Detalle | Que `on:dragover` pueda rechazar (`event.prevent()` como «aquí no», o un `accept={…}`) y entonces no se marque |
| 14 | Renombrar una columna: Escape cancela, salir del campo guarda | `<TextField>` no tiene `on:keydown` ni `on:blur` | Molesta | Se envuelve en un `<flex on:keydown>` (el evento sube desde el foco); guardar al salir no se pudo. Añadir `on:keydown`/`on:keyup`/`on:focus`/`on:blur` a los campos |
| 15 | Descripción emergente en «Deshacer» con lo que se desharía | `title` solo existe en `<flex>`, no en `<Button>` | Detalle | Se usa `label`. `title` en todos los controles |
| 16 | `gap: 4px 12px` (separación de filas y de columnas) en las etiquetas del detalle | Advertencia: solo un valor | Detalle | `gap` con dos valores, `row-gap` y `column-gap` |
| 17 | `{ui.texto}` con un `state` guardado en un objeto | Hay que escribir `.value`: solo se desenvuelven los nombres del script | Detalle | Documentarlo junto a `state`; quizá desenvolver también atributos que son `state` |
| 18 | Un velo que cierra el menú al hacer clic fuera, y el menú con `on:click={event.stop()}` | Con el menú abierto, toda la ventana se agrisaba: una caja con `on:click` se resalta y pone el cursor de mano al pasar el ratón, aunque `on:click` solo sirva para cerrar o cortar la propagación | Detalle | Se fija el fondo con `:hover` y `cursor: default`. Resaltar solo las cajas con papel de botón o enlace, o un atributo para no hacerlo |
| 19 | Deshacer y rehacer todas las acciones | No hay almacén con historial: `services/tablero.py` (~100 líneas) aplica operaciones que devuelven su inversa | Molesta (prevista) | ✅ Después del reto 2: `History` en el núcleo, y `services/tablero.py` lo usa (cada acción es un `step`; las ~100 líneas de inversas desaparecieron). Lo que hizo falta: operaciones con inversa, agrupar (`batch`) y describir cada paso («Deshacer mover “X”»). Las operaciones mueven en el sitio para que `{#each}` mueva filas en vez de recrearlas |

## Mediciones

Windows 11, Python 3.13, PySide6 6.12, sin ventana (`offscreen`, dibujado por software), tablero de 20 columnas × 200 tarjetas (`python bench.py`). Cada tiempo va desde la acción hasta que el hilo de la interfaz entrega el fotograma (eventos, Python y disposición); como referencia, un fotograma sin ningún cambio ya tarda 5 ms en llegar.

| Medida | Objetivo | Resultado |
|---|---|---|
| Cada movimiento del puntero al arrastrar entre columnas | fluido (< 16 ms) | p50 5,0 ms, p99 7,1 ms, máximo 8,7 ms: lo mismo que un fotograma sin cambios (p50 5,1 ms) más ~2 ms en el peor caso. La parte de Python (zona bajo el puntero, copia, `:drag-over`) es ~0,5 ms |
| Soltar en otra columna (la tarjeta se traslada entre dos `<List>`) | — | p50 12 ms, p99 18 ms; igual que antes del traslado, cuando se creaba otra |
| Soltar dentro de la columna (mover la fila) | — | p50 3,2 ms |
| Deshacer un movimiento | — | p50 5,7 ms, p99 12 ms |
| Cada cambio en la búsqueda (270 tarjetas creadas se comparan) | — | p50 7,7 ms; el primero, que muestra «Quitar filtros», 35 ms |
| Montar el tablero | — | 1,0 s (4 columnas × 200: 0,29 s) |
| Memoria | — | 246 MB más que antes de montar (4 × 200: 84 MB; 4 × 6: 61 MB). Ver 9 |
| Estado local tras mover en su columna / a otra | se conserva | sí / sí (ver 7) |
| Deshacer y rehacer cada acción; cada acción del menú con su tecla | todas | sí (pruebas `test_every_action_undoes_and_redoes` y `test_context_menu_and_its_keyboard_alternatives`) |

## Vía de escape usada

- Ninguna: ni QML propio ni acceso a Qt desde la aplicación. Solo `bench.py` usa `QTest` y las señales de la ventana para medir.

## Veredicto

- **Sí se pudo construir con la API pública**, una vez añadido al núcleo arrastrar y soltar (1), el desplazamiento al arrastrar cerca del borde (4) y las acciones que faltaban en `inspect` (5). Con lo que había al empezar no se podía: no había arrastre y el clic derecho no llegaba a las filas de `<List>` (2), un fallo que afectaba a cualquier aplicación con listas.
- **El diseño de arrastrar y soltar sobre el enrutado de eventos funcionó bien:** propagación, `prevent()` y `stop()` sirven igual. Que `data` sea un objeto de Python (aquí `("tarjeta", id)`) evita serializar, y `:dragging`/`:drag-over` bastan para dar respuesta visual sin código.
- **Arrastrar es fluido con 20 × 200:** un movimiento cuesta lo mismo que un fotograma vacío. Lo caro es la memoria por elemento (9), que no es del arrastre sino de cuántas cajas crea cada tarjeta.
- **El reto se cumple entero** desde que una fila se traslada entre dos `{#each}` sin recrearla (7). La regla elegida («misma declaración, misma clave, mismo cambio») no necesita sintaxis y no confunde dos entidades que comparten clave en listas distintas; cuesta lo mismo que recrear la fila.
- **Lo siguiente** sería `<Menu>` (10) y los eventos de teclado y foco en los campos (14). La ampliación a gestor de proyectos con varias vistas es otro reto (el 6 de [challenges_to_test.md](../../../docs/challenges_to_test.md)), pendiente de un enrutador.
