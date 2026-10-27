# Retos para poner FluxUI al límite

Cinco aplicaciones pensadas para encontrar los límites del framework antes de publicarlo. Ninguna es un ejemplo "bonito": cada una apunta a un tipo de aplicación de escritorio real que FluxUI debería poder hacer, y está elegida para que choque con lo que **todavía no existe** o con lo que **no se ha medido**.

El objetivo no es que salgan perfectas, sino responder con evidencia: *¿es FluxUI un framework completo para escritorio o le faltan piezas importantes?*

## Cómo construirlos

- **Solo con la API pública** ([api.md](api.md)). Si algo exige tocar `fluxui.runtime`, el QML generado o Qt directamente, eso ya es un hallazgo.
- **Primero en `.flux` puro.** Si no alcanza, se permite la vía de escape (un `.qml` propio, ver [lenguaje.md](lenguaje.md#elementos-propios-en-qml)), pero se anota como carencia: lo que muchas aplicaciones necesitan no debería exigir QML.
- **Con pruebas** usando `fluxui.inspect`, como hace cualquier usuario.
- **Medir**, no opinar: tiempos con `tools/bench_app.py` como referencia y uso de memoria con el administrador de tareas.
- Cada reto vive en `examples/challenges/<nombre>/` y termina con su **registro de hallazgos** (plantilla al final).

## Avance

| # | Reto | Estado | Resultado |
|---|---|---|---|
| 4 | Chat | ✅ | [examples/challenges/chat](../examples/challenges/chat/) · [hallazgos](../examples/challenges/chat/HALLAZGOS.md). Se añadieron al núcleo el desplazamiento de `<List>`, `<Text format>`, eventos de ventana y `notify`; quedan temporizadores, texto seleccionable y Markdown seguro. |
| 1 | Panel | ⏳ | |
| 3 | Kanban | ⏳ | |
| 2 | Hoja de cálculo | ⏳ | |
| 5 | Editor | ⏳ | |

## Resumen

| # | Reto | Lleva al límite | Lo que probablemente falte |
|---|---|---|---|
| 1 | Panel de monitorización en tiempo real | Actualizaciones a alta frecuencia, gráficas, varias ventanas | Dibujo libre (canvas), gráficas, temporizadores |
| 2 | Hoja de cálculo | Rejilla grande editable, teclado, dependencias entre celdas | Tabla/rejilla virtualizada en 2D, eventos de teclado, portapapeles, deshacer |
| 3 | Tablero Kanban | Arrastrar y soltar, reordenar con animación, menús contextuales | Drag and drop, eventos de puntero, menús |
| 4 | Cliente de chat | Conexión permanente, lista que crece por los dos extremos, texto enriquecido | Control del desplazamiento, notificaciones del sistema, texto enriquecido |
| 5 | Editor de código ligero | Documentos grandes, pestañas, árbol de archivos, cierre con cambios sin guardar | Árbol, editor con resaltado, interceptar el cierre de ventana, preferencias persistentes |

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
| Portapapeles | Copiar y pegar rangos como texto tabulado | **No existe** API de portapapeles |
| Deshacer / rehacer | Historial de cambios de celdas | No existe en el núcleo (previsto en `fluxui-store`, proyecto aparte) |
| Selección con el ratón | Arrastrar para seleccionar un rango | Solo hay `on:click`: faltan eventos de puntero |

**Hecho cuando**

- Abrir un CSV de 10 000 × 26 tarda menos de 1 s y el desplazamiento es fluido en las dos direcciones.
- Editar una celda de la que dependen 1 000 fórmulas actualiza la vista en menos de 100 ms.
- Todo el flujo (navegar, editar, seleccionar, copiar, pegar, deshacer) funciona sin ratón.

**Hipótesis de carencias:** un elemento de tabla virtualizado (`<Table>` sobre `TableView`), `on:keydown`/`on:keyup` con tecla y modificadores, `fluxui.clipboard`, eventos de puntero (`on:press`, `on:drag`), y quizá un `computed` más barato cuando hay miles.

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

**Hipótesis de carencias:** control del scroll en `<List>` (`scroll_to_end`, `scroll_to(clave)`, anclaje al insertar arriba), `<Text rich>` o un elemento Markdown, `on:link`, `fluxui.notify`/bandeja, eventos de ventana (`on:activate`, `on:close`).

---

## 5. Editor de código ligero

**La aplicación.** Un editor para proyectos pequeños: árbol de carpetas a la izquierda (expandible, con iconos y menú contextual: nuevo, renombrar, borrar), pestañas de documentos abiertos con marca de "sin guardar", editor con números de línea y resaltado de sintaxis para Python y `.flux`, buscar y reemplazar en el archivo y en todo el proyecto (en segundo plano, con resultados que van apareciendo), paleta de comandos (Ctrl+Shift+P), preferencias (tema, tamaño de letra, idioma) que se guardan entre sesiones, y aviso al cerrar la ventana si hay cambios sin guardar. Se distribuye como ejecutable con la receta de [empaquetado.md](empaquetado.md).

**Qué pone a prueba**

| Aspecto | Por qué es difícil | Estado esperado |
|---|---|---|
| Archivos grandes | Abrir y editar un archivo de 50 000 líneas | `<TextArea>` crece con el contenido: sin virtualizar, sin medir |
| Resaltado y números de línea | Colorear mientras se escribe | **No existe**; solo con QML propio (`QSyntaxHighlighter` desde Python) |
| Árbol de archivos | Nodos que se expanden bajo demanda | Se puede imitar con `{#each}` y sangría; **no hay** `<Tree>` virtualizado |
| Pestañas de documentos | Cada pestaña conserva su texto, cursor y scroll | `<Tabs>` es solo la barra; el contenido con `{#if}` se **destruye** al cambiar |
| Cerrar con cambios | Preguntar antes de cerrar y poder cancelar | **No hay** forma de interceptar el cierre de la ventana |
| Preferencias persistentes | Guardar y cargar ajustes en la carpeta del usuario | A mano con JSON; **no hay** API de ajustes |
| Búsqueda en el proyecto | Miles de archivos en segundo plano, resultados incrementales | `background` devuelve un único resultado; faltan resultados por partes |
| Empaquetado | Un ejecutable con Python, Qt y los recursos | Receta verificada; sin probar `--onefile` ni instalador |

**Hecho cuando**

- Abrir un archivo de 50 000 líneas tarda menos de 1 s y escribir no tiene retraso apreciable.
- Cambiar de pestaña conserva el texto, el cursor y el scroll de cada documento.
- Cerrar la ventana con cambios pregunta y permite cancelar; las preferencias sobreviven a reiniciar la aplicación.
- El ejecutable funciona en un equipo sin Python.

**Hipótesis de carencias:** `<CodeEditor>` o un editor de texto con resaltado y números de línea, `<Tree>`, un modo de `{#if}`/pestañas que oculte en lugar de destruir (`keep-alive`), `on:close` cancelable en `<Window>`, `fluxui.settings`, y generadores asíncronos para ir mostrando resultados.

---

## Carencias que se repiten

Lo que aparece en más de un reto es lo que más urge decidir antes de publicar:

| Carencia | Retos | Núcleo o proyecto aparte |
|---|---|---|
| Eventos de teclado y de puntero (`on:keydown`, doble clic, clic derecho, arrastrar) | 2, 3, 5 | Núcleo: afecta al lenguaje |
| Control del desplazamiento (leer y fijar el scroll, anclaje) | 1, 2, 4, 5 | Núcleo · ✅ en `<List>` (reto 4); falta en `<Scroll>` |
| Eventos de ventana (cerrar cancelable, activa) | 4, 5 | Núcleo · ✅ activa (reto 4); falta cerrar cancelable |
| Menús (contextual y barra) | 3, 5 | Núcleo (controles básicos) |
| Conservar contenido oculto (`keep-alive`) | 5 | Núcleo: afecta al lenguaje |
| Portapapeles, notificaciones, bandeja, ajustes | 2, 4, 5 | Núcleo, como módulos pequeños (`fluxui.clipboard`, …) · ✅ `notify` (reto 4) |
| Temporizadores ligados al componente | 1, 4 | Núcleo |
| Texto seleccionable | 4, 5 | Núcleo |
| Tabla 2D y árbol virtualizados | 2, 5 | Núcleo o `fluxui-kit` |
| Canvas, gráficas, editor de código | 1, 5 | `fluxui-kit` (sobre la vía de escape QML) |
| Texto enriquecido | 4 | ✅ Núcleo: `<Text format="markdown">` (reto 4) |
| Deshacer/rehacer y stores | 2, 3 | `fluxui-store` |

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
