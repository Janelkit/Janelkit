# Retos para poner JanelKit al límite

Seis aplicaciones pensadas para encontrar los límites del framework antes de publicarlo. Ninguna es un ejemplo "bonito": cada una apunta a un tipo de aplicación de escritorio real que JanelKit debería poder hacer, y está elegida para que choque con lo que **todavía no existe** o con lo que **no se ha medido**.

El objetivo no es que salgan perfectas, sino responder con evidencia: *¿es JanelKit un framework completo para escritorio o le faltan piezas importantes?*

## Cómo construirlos

- **Solo con la API pública** ([api.md](api.md)). Si algo exige tocar `janelkit.runtime`, el QML generado o Qt directamente, eso ya es un hallazgo.
- **Primero en `.janel` puro.** Si no alcanza, se permite la vía de escape (un `.qml` propio, ver [lenguaje.md](lenguaje.md#elementos-propios-en-qml)), pero se anota como carencia: lo que muchas aplicaciones necesitan no debería exigir QML.
- **Con pruebas** usando `janelkit.inspect`, como hace cualquier usuario.
- **Medir**, no opinar: tiempos con `tools/bench_app.py` como referencia y uso de memoria con el administrador de tareas.
- Cada reto vive en `apps/challenges/<nombre>/` y termina con su **registro de hallazgos** (plantilla al final).

## Avance

| # | Reto | Estado | Resultado |
|---|---|---|---|
| 4 | Chat | ✅ | [apps/challenges/chat](../apps/challenges/chat/) · [hallazgos](../apps/challenges/chat/HALLAZGOS.md). Se añadieron al núcleo el desplazamiento de `<List>`, `<Text format>`, eventos de ventana y `notify`; quedan temporizadores, texto seleccionable y Markdown seguro. |
| 1 | Panel | ✅ | [apps/challenges/panel](../apps/challenges/panel/) · [hallazgos](../apps/challenges/panel/HALLAZGOS.md). Se añadieron al núcleo los temporizadores (`interval`, `timeout`), el formato en el texto (`{x:.1f}`) y `MountedApp.windows()`, y se corrigieron cuatro fallos (listas modificadas en el sitio que no llegaban a QML, scroll perdido al reordenar, `flex` en QML propio, `janel build` con ventanas); quedan gráficas (janelkit-kit), rejilla con salto de línea y tabla. |
| 3 | Kanban | ✅ | [apps/challenges/kanban](../apps/challenges/kanban/) · [hallazgos](../apps/challenges/kanban/HALLAZGOS.md). Se añadió al núcleo arrastrar y soltar (`draggable`, `on:dragstart/dragover/drop/dragend`, `:dragging`, `:drag-over`, desplazamiento al acercarse al borde) y en `inspect` doble clic, clic derecho, teclas y arrastre; se corrigió que los eventos de puntero no llegaran a las filas de `<List>`. Arrastrar con 20 × 200 cuesta lo mismo que un fotograma vacío. Una fila que pasa a otra lista de la misma declaración `{#each}` se traslada con su estado y su foco (la tarjeta conserva su estado al cambiar de columna). Quedan `<Menu>` y la memoria por elemento (~0,65 MB por tarjeta, antes ~0,77; ver la fila de la tabla de abajo). |
| 2 | Hoja de cálculo | ⏳ | |
| 5 | Editor | ⏳ | |
| 6 | Gestor de proyectos | ✅ | [apps/challenges/gestor](../apps/challenges/gestor/) · [hallazgos](../apps/challenges/gestor/HALLAZGOS.md). Antes de empezar se añadió al núcleo la navegación básica (`sections`, `navigation()`, `await push`/`back`, Alt+← y botón del ratón, `before_leave`, `{#hidden}`, transiciones de página). Durante el reto: las cajas ocultas ya no se recolocan (cambiar de pestaña con 200 tarjetas, de 239 a 5 ms), `pop`/`reset` se pueden esperar, y en `inspect` se corrigió aceptar un `confirm` y que dos apps con módulos del mismo nombre se mezclaran. Todas las medidas de «Hecho cuando» se cumplen y la memoria no crece. Quedan adelante y rutas (`janelkit-router`), otra ventana con su propia pila y parte del plan (pestaña Lista, ajustes de etiquetas y columnas). |

## Resumen

| # | Reto | Lleva al límite | Lo que probablemente falte |
|---|---|---|---|
| 1 | Panel de monitorización en tiempo real | Actualizaciones a alta frecuencia, gráficas, varias ventanas | Dibujo libre (canvas), gráficas, temporizadores |
| 2 | Hoja de cálculo | Rejilla grande editable, teclado, dependencias entre celdas | Tabla/rejilla virtualizada en 2D, eventos de teclado, portapapeles, deshacer |
| 3 | Tablero Kanban | Arrastrar y soltar, reordenar con animación, menús contextuales | Drag and drop, eventos de puntero, menús |
| 4 | Cliente de chat | Conexión permanente, lista que crece por los dos extremos, texto enriquecido | Control del desplazamiento, notificaciones del sistema, texto enriquecido |
| 5 | Editor de código ligero | Documentos grandes, pestañas, árbol de archivos, cierre con cambios sin guardar | Árbol, editor con resaltado, interceptar el cierre de ventana, preferencias persistentes |
| 6 | Gestor de proyectos | Varias pantallas con navegación, estado compartido entre vistas y ventanas, formularios de gestión | Enrutador (`janelkit-router`), conservar vistas ocultas, eventos en los campos |

---

## 1. Panel de monitorización en tiempo real

**La aplicación.** Muestra el estado del ordenador (CPU por núcleo, memoria, red, procesos) actualizado varias veces por segundo. Una ventana principal con tarjetas y gráficas de línea con los últimos 60 segundos, una tabla de procesos ordenable y filtrable, y la opción de abrir cualquier gráfica en una ventana aparte. Si un valor supera un umbral, la tarjeta cambia de color con transición y aparece un aviso.

**Qué pone a prueba**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Frecuencia de actualización | 20–60 cambios de `state` por segundo, en decenas de bindings a la vez | Sin medir: puede saturar el hilo de la interfaz |
| Gráficas de línea | Dibujar cientos de puntos que cambian sin crear un elemento por punto | **No existe**: no hay canvas ni gráficas |
| Lectura periódica | Muestrear cada 250 ms sin bloquear | Solo con `asyncio.sleep` en un bucle: no hay temporizadores declarados |
| Tabla de procesos | ~300 filas que cambian de orden cada segundo | `<List>` + `{#each}` con claves; mover muchas filas fuerza reinicio del modelo |
| Varias ventanas sincronizadas | La misma gráfica en dos ventanas con el mismo `state` | `open_window` + `state` compartido: debería funcionar |
| Agrupar cambios | Actualizar 40 métricas como un único cambio | `batch()` existe; hay que comprobar que basta |

**Hecho cuando**

- Actualiza 50 métricas 10 veces por segundo durante 10 minutos con el hilo de la interfaz por debajo del 50 % de una CPU y sin crecimiento de memoria.
- Las gráficas muestran 60 s de historia a 4 muestras/s sin tirones al redimensionar la ventana.
- Ordenar o filtrar la tabla mientras se actualiza no pierde la selección ni la posición del scroll.

**Hipótesis de carencias:** un elemento de dibujo (`<Canvas>` o `<Chart>`), un temporizador declarativo (`interval(ms, fn)` ligado al componente), y quizá agrupar las notificaciones a QML por fotograma.

---

## 2. Hoja de cálculo

**La aplicación.** Una hoja de 10 000 filas × 26 columnas. Las celdas se editan en el sitio y admiten fórmulas sencillas (`=A1+B2`, `=SUMA(A1:A100)`) que se recalculan solas cuando cambian sus dependencias. Se navega con las flechas, Tab e Intro; se selecciona un rango con Mayús; se copia y pega con el portapapeles (también desde Excel); se deshace con Ctrl+Z; se puede congelar la primera fila y la primera columna; se ordena por una columna. Abre y guarda CSV.

**Qué pone a prueba**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Rejilla virtualizada en 2D | 260 000 celdas: solo pueden existir las visibles, en filas **y** columnas | `<List>` virtualiza filas, no columnas: **no hay tabla** |
| Reactividad a gran escala | Una celda con dependencias que cambia y recalcula cientos de fórmulas | `computed` por celda: sin medir con miles de nodos |
| Teclado | Flechas, Tab, Intro, Esc, Mayús+flechas sobre celdas | **No existe** `on:keydown`; solo `<Shortcut>` global |
| Edición en el sitio | Pasar de mostrar a editar una celda y volver, con el foco correcto | `ref.focus()` existe; falta gestionar el foco entre muchos elementos |
| Portapapeles | Copiar y pegar rangos como texto tabulado | ✅ `janelkit_desktop.clipboard` (texto); falta probar el reto de rangos tabulados |
| Deshacer / rehacer | Historial de cambios de celdas | Todavía no existe (previsto en el núcleo, con los stores) |
| Selección con el ratón | Arrastrar para seleccionar un rango | Solo hay `on:click`: faltan eventos de puntero |

**Hecho cuando**

- Abrir un CSV de 10 000 × 26 tarda menos de 1 s y el desplazamiento es fluido en las dos direcciones.
- Editar una celda de la que dependen 1 000 fórmulas actualiza la vista en menos de 100 ms.
- Todo el flujo (navegar, editar, seleccionar, copiar, pegar, deshacer) funciona sin ratón.

**Hipótesis de carencias:** un elemento de tabla virtualizado (`<Table>` sobre `TableView`), `on:keydown`/`on:keyup` con tecla y modificadores, `janelkit_desktop.clipboard`, eventos de puntero (`on:press`, `on:drag`), y quizá un `computed` más barato cuando hay miles.

---

## 3. Tablero Kanban

**La aplicación.** Un tablero con columnas (Pendiente, En curso, Hecho…) y tarjetas que se arrastran entre columnas y dentro de una misma columna, con animación al recolocarse. Las tarjetas tienen etiquetas de colores, responsable y fecha. Doble clic abre la tarjeta en un panel de detalle; clic derecho muestra un menú contextual (mover a, duplicar, borrar). Las columnas se añaden, renombran y reordenan. Hay búsqueda y filtros que atenúan las tarjetas que no coinciden. Todo se guarda en un archivo JSON y se puede deshacer.

**Qué pone a prueba**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Arrastrar y soltar | Tarjeta fantasma, zona de destino resaltada, posición de inserción | **No existe** |
| Reordenar con animación | Que las demás tarjetas se aparten suavemente | Solo en `<List animate>`; en `Column` no hay animación de movimiento |
| Doble clic y clic derecho | Gestos distintos sobre el mismo elemento | **No existen**: solo `on:click` |
| Menús contextuales y barra de menús | Menú emergente con submenús y atajos | **No existen** |
| Listas anidadas | `{#each}` de columnas que contiene `{#each}` de tarjetas, con claves | Debería funcionar; sin medir con 20 columnas × 200 tarjetas |
| Mover entre listas | Una tarjeta pasa de una lista reactiva a otra conservando su componente | Hoy se destruye y se crea otra: se pierde su estado local |
| Estado compartido y deshacer | Muchas acciones que deben poder deshacerse | Sin ayuda del núcleo |

**Hecho cuando**

- Arrastrar una tarjeta entre columnas con 200 tarjetas cada una se ve fluido y la tarjeta mantiene su estado (p. ej. un desplegable abierto).
- Cada acción (mover, editar, borrar) se puede deshacer y rehacer.
- Todas las acciones del menú contextual tienen alternativa con teclado.

**Hipótesis de carencias:** `on:drag*`/`on:drop` o un elemento arrastrable, `on:doubleclick` y `on:contextmenu`, `<Menu>`/`<MenuBar>`, animación de movimiento en contenedores normales, y mover una fila entre dos `{#each}` sin recrearla.

---

## 4. Cliente de chat

**La aplicación.** Un cliente que conecta por WebSocket a un servidor de pruebas (incluido en el reto, en Python con `websockets`). Lista de conversaciones a la izquierda con contador de no leídos; a la derecha, los mensajes. Los nuevos llegan en tiempo real y la vista baja sola si el usuario ya estaba abajo; al subir del todo se carga el historial anterior **sin saltos**. Los mensajes admiten negrita, enlaces y código (un subconjunto de Markdown), imágenes remotas con carga diferida y reacciones. Indicador "escribiendo…", reconexión automática con aviso, notificación del sistema e icono en la bandeja si la ventana no está en primer plano. Español, inglés y árabe.

**Qué pone a prueba**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Conexión permanente | Una corrutina que vive toda la sesión, con reconexión | `spawn` + `qasync`: debería funcionar; sin probar con WebSocket |
| Desplazamiento controlado | Quedarse abajo con mensajes nuevos; cargar arriba sin que salte la vista | **No hay API** para leer o fijar el scroll de `<List>` (solo `ref.value`, interfaz de Qt) |
| Texto enriquecido | Negrita, enlaces pulsables, código | `<Text>` solo muestra texto plano: **no hay texto enriquecido** ni `on:link` |
| Imágenes remotas | Carga diferida en listas que se reciclan | `<Image src="https://…">` existe; sin medir en una `<List>` larga |
| Notificaciones y bandeja | Avisos del sistema, icono con menú | **No existen** |
| Ventana en primer plano | Saber si el usuario está mirando para marcar como leído | **No hay** eventos de ventana (activa, minimizada, cerrar) |
| Derecha a izquierda | Burbujas propias y ajenas a lados contrarios, también en árabe | `i18n` + `LayoutMirroring`: debería funcionar |

**Hecho cuando**

- Recibir 20 mensajes por segundo durante 5 minutos no degrada la respuesta y la memoria se estabiliza.
- Cargar el historial (bloques de 50) mantiene el mensaje visible en el mismo sitio de la pantalla.
- Cortar el servidor y volver a levantarlo reconecta sin perder mensajes ni bloquear la interfaz.

**Hipótesis de carencias:** control del scroll en `<List>` (`scroll_to_end`, `scroll_to(clave)`, anclaje al insertar arriba), `<Text rich>` o un elemento Markdown, `on:link`, `janelkit.notify`/bandeja, eventos de ventana (`on:activate`, `on:close`).

---

## 5. Editor de código ligero

**La aplicación.** Un editor para proyectos pequeños: árbol de carpetas a la izquierda (expandible, con iconos y menú contextual: nuevo, renombrar, borrar), pestañas de documentos abiertos con marca de "sin guardar", editor con números de línea y resaltado de sintaxis para Python y `.janel`, buscar y reemplazar en el archivo y en todo el proyecto (en segundo plano, con resultados que van apareciendo), paleta de comandos (Ctrl+Shift+P), preferencias (tema, tamaño de letra, idioma) que se guardan entre sesiones, y aviso al cerrar la ventana si hay cambios sin guardar. Se distribuye como ejecutable con la receta de [empaquetado.md](empaquetado.md).

**Qué pone a prueba**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Archivos grandes | Abrir y editar un archivo de 50 000 líneas | `<TextArea>` crece con el contenido: sin virtualizar, sin medir |
| Resaltado y números de línea | Colorear mientras se escribe | **No existe**; solo con QML propio (`QSyntaxHighlighter` desde Python) |
| Árbol de archivos | Nodos que se expanden bajo demanda | Se puede imitar con `{#each}` y sangría; **no hay** `<Tree>` virtualizado |
| Pestañas de documentos | Cada pestaña conserva su texto, cursor y scroll | `<Tabs>` es solo la barra; el contenido con `{#if}` se **destruye** al cambiar |
| Cerrar con cambios | Preguntar antes de cerrar y poder cancelar | **No hay** forma de interceptar el cierre de la ventana |
| Preferencias persistentes | Guardar y cargar ajustes en la carpeta del usuario | ✅ `persisted(clave, valor)` (antes, a mano con JSON) |
| Búsqueda en el proyecto | Miles de archivos en segundo plano, resultados incrementales | `background` devuelve un único resultado; faltan resultados por partes |
| Empaquetado | Un ejecutable con Python, Qt y los recursos | Receta verificada; sin probar `--onefile` ni instalador |

**Hecho cuando**

- Abrir un archivo de 50 000 líneas tarda menos de 1 s y escribir no tiene retraso apreciable.
- Cambiar de pestaña conserva el texto, el cursor y el scroll de cada documento.
- Cerrar la ventana con cambios pregunta y permite cancelar; las preferencias sobreviven a reiniciar la aplicación.
- El ejecutable funciona en un equipo sin Python.

**Hipótesis de carencias:** `<CodeEditor>` o un editor de texto con resaltado y números de línea, `<Tree>`, un modo de `{#if}`/pestañas que oculte en lugar de destruir (`keep-alive`), `on:close` cancelable en `<Window>`, `janelkit.settings`, y generadores asíncronos para ir mostrando resultados.

## 6. Gestor de proyectos

**Estado: hecho** ([apps/challenges/gestor](../apps/challenges/gestor/), [hallazgos](../apps/challenges/gestor/HALLAZGOS.md)). Nació al ampliar el Kanban (reto 3): de un tablero suelto a una aplicación con varias pantallas. Estaba en espera de `janelkit-router`; al revisar el alcance, la navegación fundamental (secciones, pila desde cualquier página, resultados, atrás, guardas, vistas que se conservan) pasó al núcleo, y el enrutado (rutas, historial con adelante, restaurar) sigue siendo `janelkit-router`. La tabla de abajo es la de partida; cómo quedó cada necesidad está en los hallazgos.

**La aplicación.** Un gestor de proyectos para un equipo pequeño, todo local, en un archivo JSON.

| Vista | Qué hace |
|---|---|
| **Proyectos** (inicio) | Rejilla de proyectos con color, nº de tarjetas, progreso y miembros. Crear, renombrar, archivar o recuperar, borrar con confirmación, buscar. |
| **Proyecto ▸ Tablero** | El tablero del reto 3, con las etiquetas y los miembros del proyecto. El responsable se elige entre los miembros. |
| **Proyecto ▸ Lista** | Las tarjetas en una tabla que se ordena por cabecera, se filtra con los filtros del tablero y se edita en línea; marca las vencidas. |
| **Proyecto ▸ Miembros** | Quién participa y con qué rol. Al quitar a alguien con tarjetas: reasignarlas o dejarlas sin responsable. |
| **Proyecto ▸ Ajustes** | Nombre, color y descripción; etiquetas (en uso: aviso antes de borrar); columnas, incluida la «de hecho» que cuenta para el progreso; exportar a JSON. |
| **Personas** | Directorio de todas las personas (nombre, iniciales y color, correo, rol): alta, edición y baja, con aviso de cuántas tarjetas tiene en cada proyecto. |
| **Mi trabajo** | Las tarjetas de una persona en todos los proyectos, por proyecto o por fecha; abrir una lleva a su tablero con ella enfocada. |
| **Ajustes** | Tema, archivo de datos, pasos de deshacer. |
| **Otra ventana** | Un proyecto abierto en una ventana aparte, sobre los mismos datos: lo que se mueve en una se ve en la otra. |

Las tarjetas guardan ids de personas y etiquetas, no nombres: renombrar una persona se ve al momento en todos los proyectos. Un solo historial de deshacer para todo, que dice en qué proyecto ocurrió cada paso. El `tablero.json` del reto 3 se importa como un proyecto.

**Por qué necesita un enrutador.** Con lo que hay en el núcleo (`pages`, una pila; `{#if}`; `<Tabs>`) se podría montar a mano, pero el reto quedaría midiendo los rodeos y no la aplicación:

| Necesidad | Con `pages` y `{#if}` | Lo que pediría a `janelkit-router` |
|---|---|---|
| Rutas con parámetros (`/proyectos/:id/tablero`, `/personas/:id`) | La página recibe props al apilarla; no hay una dirección que guardar o compartir | Rutas con nombre y parámetros, y la ruta actual como estado reactivo |
| Atrás **y adelante** (Alt+←/→, botones del ratón) | Solo atrás (`pop`); adelante se pierde | Historial con las dos direcciones |
| Enlaces profundos («Mi trabajo» → tablero de otro proyecto con una tarjeta enfocada) | Reconstruir la pila a mano (`reset` + `push`) | Navegar a una ruta, con parámetros de consulta (`?tarjeta=t5`) |
| Secciones paralelas (Proyectos, Personas, Mi trabajo), cada una con su propia pila | Una pila por sección y `{#if}` para elegir; la barra lateral sincronizada a mano | Rutas anidadas: una disposición con la barra lateral y una salida por sección |
| Conservar una vista al volver (búsqueda y desplazamiento de Proyectos) | `pages` mantiene viva la página de debajo, pero no la de otra sección | Vistas que se conservan (`keep-alive`, ya en las carencias del reto 5) |
| Salir con cambios sin guardar (Ajustes, Detalle) | Comprobarlo en cada botón | Guardas antes de salir de una ruta |
| La misma ruta en otra ventana | Pasar el proyecto como prop a `open_window` | Abrir una ruta en una ventana nueva |
| Restaurar la última vista al reabrir | Guardar y reconstruir a mano | Serializar la ruta actual |

**Qué pone a prueba (además del enrutador)**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Estado compartido entre vistas y ventanas | La misma tarjeta en el tablero, la lista, «Mi trabajo» y otra ventana | Colecciones reactivas + `provide`: debería funcionar; sin medir con varias ventanas |
| `computed` que cruza todos los proyectos | «Mi trabajo» y los contadores de cada proyecto recorren miles de tarjetas | Sin medir |
| Formularios de gestión | Validación, edición en línea, guardar al salir del campo | `<TextField>` sin `on:keydown` ni `on:blur` (reto 3, hallazgo 14) |
| Tabla ordenable y editable | Ordenar sin perder la posición, editar con `<Select>` en la fila | Hecha con `<List>` y `<flex>`, como en el reto 1 (la tabla de datos es de `janelkit-kit`) |
| Fechas | Elegir y validar una fecha | Sin selector (`janelkit-kit`): `<TextField>` con formato `AAAA-MM-DD` |
| Borrados en cascada | Personas, etiquetas, columnas o proyectos referenciados | De la aplicación |
| Memoria al navegar | Abrir y cerrar proyectos una y otra vez | Lo cerrado debe liberarse; la memoria por elemento ya es alta (reto 3) |

**Hecho cuando**

- Con 10 proyectos de 4 × 50 tarjetas y 300 personas: abrir un proyecto tarda menos de 150 ms, volver menos de 30 ms y cambiar de pestaña o de sección menos de 100 ms; buscar en Personas cuesta menos de 16 ms por pulsación.
- Abrir y cerrar los 10 proyectos varias veces no hace crecer la memoria.
- Atrás, adelante y los enlaces de «Mi trabajo» llevan siempre a la vista correcta, también en una segunda ventana.
- Toda acción se puede deshacer, y todo se puede hacer con el teclado.

**Hipótesis de carencias:** `janelkit-router` (rutas con parámetros, historial, rutas anidadas, guardas), conservar vistas ocultas (`keep-alive`), eventos de teclado y foco en los campos, `<Menu>`, y el coste de `computed` con colecciones grandes.

---

## Carencias que se repiten

Lo que aparece en más de un reto es lo que más urge decidir antes de publicar:

| Carencia | Retos | Núcleo o proyecto aparte |
|---|---|---|
| Eventos de teclado y de puntero (`on:keydown`, doble clic, clic derecho, arrastrar) | 2, 3, 5, 6 | ✅ Núcleo en `<flex>` (fase 3 y reto 3: arrastrar y soltar); ✅ también en los campos (`TextField`, `TextArea`, `Select`) |
| Control del desplazamiento (leer y fijar el scroll, anclaje) | 1, 2, 4, 5 | Núcleo · ✅ en `<List>` (retos 4 y 1: también al reordenar); falta en `<Scroll>` |
| Eventos de ventana (cerrar cancelable, activa) | 4, 5 | Núcleo · ✅ activa (reto 4); ✅ cerrar con la X consulta `before_leave` (reto 6) |
| Menús (contextual y barra) | 3, 5 | Núcleo (controles básicos) · el reto 3 hizo el contextual con `<flex>` (sin submenús ni recolocación junto al borde) |
| Trasladar una fila entre dos `{#each}` sin recrearla (conserva su estado) | 3, 6 | ✅ Núcleo (reto 3): misma declaración, misma clave, mismo cambio ([lenguaje.md](lenguaje.md#trasladar-filas-entre-listas)) |
| Memoria por elemento (~30–35 KB por `<Text>` o `<flex>`) | 3 | Núcleo · ✅ primera pasada: el texto heredado crea un enlace por propiedad usada (antes once siempre), `<Text>` es un `Text` y no un `Label`, y las cajas no interactivas no pagan hover, pulsado, foco ni bordes. Una tarjeta con estilos, −22 %; el tablero 20 × 200, de 282 a 249 MB; mismo tiempo de creación. Queda lo estructural: cada `{#if}`/`{#each}` es un `Repeater` (~8,5 KB vacío y ~8 KB más por fila) |
| Conservar contenido oculto (`keep-alive`) | 5, 6 | ✅ Núcleo (reto 6): `{#hidden}`, secciones y la página de debajo; lo oculto no se recoloca ni recalcula lo que muestra hasta volver a verse (reto 6) |
| Enrutado con parámetros, historial y rutas anidadas | 6 | `janelkit-router`. El núcleo da la navegación básica (reto 6): `pages`, `sections`, `navigation()`, resultados, atrás y `before_leave` |
| Portapapeles, notificaciones, bandeja, ajustes | 2, 4, 5 | Núcleo, como módulos pequeños (`janelkit_desktop.clipboard`, …) · ✅ `notify` (reto 4) · ✅ `clipboard` (texto) |
| Temporizadores ligados al componente | 1, 4 | ✅ Núcleo: `interval`, `timeout` (reto 1) |
| Texto seleccionable | 4, 5 | Núcleo |
| Tabla 2D y árbol virtualizados | 1, 2, 5 | Núcleo o `janelkit-kit` · el reto 1 hizo su tabla con `<List>` y anchos repetidos en cabecera y filas |
| Canvas, gráficas, editor de código | 1, 5 | `janelkit-kit` (sobre la vía de escape QML) · el reto 1 hizo su gráfica en QML propio sin problemas |
| Rejilla con salto de línea (tarjetas que se recolocan según el ancho) | 1 | ✅ Núcleo: `flex-wrap` en `<flex>`, `Column` y `Row` ([flex.md](flex.md), fase 1) |
| Texto enriquecido | 4 | ✅ Núcleo: `<Text format="markdown">` (reto 4) |
| Deshacer/rehacer y stores | 2, 3 | núcleo, pendiente · el reto 3 lo hizo en la aplicación con operaciones que devuelven su inversa (~100 líneas) |

## Registro de hallazgos (plantilla)

Cada reto termina con un `HALLAZGOS.md` en su carpeta:

```markdown
# Hallazgos: <reto>

| # | Qué intenté | Qué pasó | Gravedad | Propuesta |
|---|---|---|---|---|
| 1 | Arrastrar una tarjeta entre columnas | No hay eventos de arrastre; usé un .qml propio | Bloquea / Molesta / Detalle | `on:drag`, `on:drop` en el núcleo |

## Mediciones
| Medida | Objetivo | Resultado |
|---|---|---|

## Vía de escape usada
- Qué partes necesitaron QML propio o acceso a Qt y por qué.

## Veredicto
- ¿Se pudo construir solo con la API pública? ¿Qué faltaría para que sí?
```

## Orden sugerido

1. **Chat (4)** y **Panel (1):** ponen a prueba la asincronía y la frecuencia de actualización, lo más nuevo y menos medido.
2. **Kanban (3):** destapa las carencias de interacción (arrastrar, menús, gestos), que afectan al diseño del lenguaje.
3. **Hoja de cálculo (2)** y **Editor (5):** los más exigentes; conviene abordarlos cuando las decisiones de los anteriores estén tomadas.
4. **Gestor de proyectos (6):** ✅ hecho con la navegación básica del núcleo; servirá para validar `janelkit-router` cuando exista.
