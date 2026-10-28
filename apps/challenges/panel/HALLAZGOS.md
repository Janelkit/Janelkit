# Hallazgos: panel de monitorización (reto 1)

Construido con la API pública y una gráfica en QML propio (la vía de escape prevista: las gráficas son de `janelkit-kit`, ver [alcance.md](../../../docs/alcance.md)). Lo que faltaba y entraba en el alcance del núcleo se añadió o se corrigió durante el reto; lo demás queda como propuesta.

Gravedad: **Bloquea** (no se podía hacer o salía mal), **Molesta** (había que dar un rodeo), **Detalle**.

## Resueltos en el núcleo durante el reto

| # | Qué intenté | Qué pasó | Gravedad | Solución |
|---|---|---|---|---|
| 1 | Muestrear cada 250 ms y leer los procesos cada segundo | No había temporizadores: un bucle con `asyncio.sleep` y cancelación a mano (como en el chat) | Molesta | `interval(ms, fn)` y `timeout(ms, fn)`, también como decoradores, ligados al componente; `Timer` con `.active`, `.stop()`, `.start()`, `.restart()` |
| 2 | Actualizar 50 métricas en cada muestra como un único cambio | `batch()` existe, pero había que acordarse de usarlo | Detalle | Cada tic de un temporizador va en su propio `batch`: una muestra, un recálculo |
| 3 | Leer los procesos en otro hilo cada segundo | Si una lectura tarda más que el periodo, se acumularían | Molesta | Con una función `async`, los tics se saltan mientras la anterior no termina |
| 4 | Gráficas con la historia (`values={serie.history.value}`) | La lista se modificaba en el sitio (`append`, `del`) y **QML no recibía los cambios**: el binding dependía del `state`, no de su contenido. Afectaba a cualquier lista entregada entera a QML (también `options` de un `Select`) | Bloquea (fallo) | Un binding que entrega una colección a QML depende también de su contenido, en profundidad |
| 5 | Ordenar la tabla por CPU con refresco cada segundo | Mover más de 64 filas reinicia el modelo y la lista **volvía arriba en cada refresco** | Bloquea | Tras un reinicio, la fila que estaba arriba (por su número) vuelve a su sitio, como en un administrador de tareas |
| 6 | `<LineChart flex={1} />` (QML propio) en la ventana de la gráfica | Error de Qt: `Cannot assign to non-existent property "jkFlex"`, aunque la documentación decía que `flex` se admitía | Bloquea (fallo) | `flex` en un elemento `.qml` sigue las mismas reglas que en los de JanelKit |
| 7 | `{cpu:.0f} %` en el texto | Error de sintaxis: había que escribir `{f"{cpu:.0f}"}` o una función | Molesta | Formato como en un f-string: `{x:.1f}`, `{n:,}`, `{x!r}` (solo en el texto) |
| 8 | `janel build` con `ChartWindow.janel` (raíz `<Window>`, se abre con `open_window`) | «un componente usado dentro de otro no puede tener `<Window>` como raíz»: falso error | Molesta | Un archivo sin usar en ninguna plantilla y con `<Window>` como raíz se valida como ventana |
| 9 | Probar la gráfica abierta en otra ventana | `inspect` solo veía la ventana principal | Molesta | `MountedApp.windows()`: cada ventana se inspecciona igual que la principal |
| 10 | Cambiar el periodo de muestreo con un `Select` | Primero no había forma | Detalle | `muestrear.ms = 500` y `muestrear.restart()` |
| 11 | Ejecutar las pruebas del reto solas (`pytest apps/challenges/tests/test_challenge_panel.py`) | Al salir: «Exception ignored … Signal source has been deleted» (el bucle de qasync se cerraba cuando Qt ya no existía) | Detalle | El bucle se cierra al salir, con Qt todavía vivo |

## Pendientes (propuestas)

| # | Qué intenté | Qué pasó | Gravedad | Propuesta |
|---|---|---|---|---|
| 12 | Gráficas de línea | No hay `<Canvas>` ni `<Chart>`: `LineChart.qml`, unas 100 líneas de QML. La primera versión, con `Canvas`, costaba un 30 % de CPU del hilo de la interfaz (8 gráficas × 600 puntos × 10/s); con `QtQuick.Shapes` (`PathPolyline`, triangulación asíncrona), un 12 % | Molesta (prevista) | `<Chart>` en `janelkit-kit`, sobre Shapes y no sobre `Canvas`. Como QML propio funcionó bien: props tipadas y tema con `jktheme` |
| 13 | Tarjetas y núcleos en rejilla | No hay rejilla ni `flex-wrap`: se trocean a mano en Python (`[i:i + 8]`) y no se recolocan al estrechar la ventana | Molesta | `<Grid columns={n}>` o `flex-wrap` en `Row`, con ancho mínimo por celda. **Ya existe** (`flex-wrap` y `flex: 1 1 200px`, fase 1 de [`<flex>`](../../../docs/flex.md)); el panel no se ha reescrito con ello |
| 14 | Tabla de procesos | No hay tabla: cabecera de botones y filas con los mismos anchos escritos dos veces (`COLUMNS` y cada `<Text width>`) | Molesta | Tabla con columnas declaradas en `janelkit-kit` (ver también la hoja de cálculo, reto 2) |
| 15 | Que `<LineChart>` ocupe el ancho de la tarjeta | Un elemento QML propio toma su tamaño natural (como un botón): hace falta `width: 100%` en una clase | Detalle | Documentado; valorar que los elementos propios se comporten como bloques en una columna |
| 16 | Texto de la fila seleccionada en el color de acento | Los estilos son locales y sin descendientes: la fila no puede cambiar el color de sus `<Text>` | Detalle | Fondo translúcido como rodeo; valorar herencia de `color` desde el contenedor |
| 17 | Comprobar en una prueba que el scroll no se mueve | `inspect` no da la posición de una lista: hay que leer el `ListView` de Qt | Detalle | `Element.scroll` (posición) y `Element.scroll_to(i)` en `inspect` |
| 18 | Reordenar 300 filas cada segundo | Funciona, pero cada reordenado vuelve a crear las filas visibles (reinicio del modelo) | Detalle | Medido: no se nota (ver mediciones). Si hiciera falta, mover por bloques en lugar de reiniciar |

## Mediciones

Windows 11, Python 3.13, PySide6 6.12, ventana visible a 60 Hz, fuente simulada con 50 métricas y 300 procesos, la ventana principal y dos gráficas abiertas en otras ventanas (`bench.py`). Cada 30 s el banco reordena y filtra la tabla.

| Medida | Objetivo | Resultado |
|---|---|---|
| 50 métricas 10 veces por segundo durante 10 min: muestras | 10/s | 9,9–10,1/s, sin perder ninguna |
| CPU del hilo de la interfaz | < 50 % de una CPU | media 12 %, máximo 16 % (el proceso entero, 12–35 %, cuenta también el hilo que lee los procesos) |
| Memoria | sin crecimiento | 279–316 MB sin tendencia (primera mitad 305 MB, segunda 291 MB) |
| Latencia desde la muestra hasta el fotograma en pantalla | sin tirones | p99 ≤ 27 ms, máximo 28 ms. La mediana se mueve entre 8 y 19 ms con la fase entre el temporizador (100 ms = 6 fotogramas) y el refresco de la pantalla; a 11 muestras/s se queda plana en 12–13 ms |
| Coste de cada fotograma (instrumentación de Qt) | — | render + sync + swap p99 2 ms; disposición (polish) p99 0 ms |
| Redimensionar sin parar durante 10 s con las gráficas llenas | sin tirones | coste por fotograma p99 2 ms (render) y 4 ms (disposición). La latencia de 60–90 ms es Windows cambiando el tamaño de la ventana (`blockedForSync`); una ventana con un solo texto da ~60 ms |
| Retraso del bucle de eventos (tarea cada 50 ms) | — | p99 22–33 ms (la base en Windows es ~15 ms) |
| Ordenar o filtrar mientras se actualiza | no pierde selección ni scroll | prueba `test_sorting_and_filtering_keep_the_selection_and_the_scroll` |
| Gráficas con `Canvas` (primera versión, 10 min) | — | CPU de la interfaz 30 %, disposición p99 22 ms y la latencia subía hasta 40 ms: se cambió a Shapes |

## Vía de escape usada

- `widgets/LineChart.qml`: la gráfica (QML con `QtQuick.Shapes`). Prevista por el alcance: las gráficas son de `janelkit-kit`.
- Ninguna otra: ni acceso a Qt desde la aplicación ni cambios en el QML generado. Solo el banco de pruebas (`bench.py`) lee los tiempos de Qt y desactiva las notificaciones reales.

## Veredicto

- **Sí se pudo construir**, con la gráfica en QML propio como prevé el alcance. Pero no con lo que había al empezar: faltaban los temporizadores y había tres fallos que lo impedían. Las listas modificadas en el sitio no llegaban a QML, la tabla volvía arriba en cada refresco y `flex` rompía los elementos QML propios. Los tres están corregidos, con pruebas.
- **El rendimiento sobra.** 50 métricas 10 veces por segundo usan un 12 % del hilo de la interfaz. Cada muestra llega a la pantalla en menos de 30 ms, y un fotograma cuesta 2 ms incluso redimensionando. No hizo falta agrupar las notificaciones a QML por fotograma: con el `batch` de cada tic basta.
- **Varias ventanas con el mismo `state` funcionan sin hacer nada:** la gráfica abierta aparte se actualiza con la principal.
- **Lo que más se echa de menos ahora** es la disposición en rejilla (13) y una tabla (14). El fallo de las listas (4) afectaba a cualquier aplicación que pase una lista entera a un control, no solo a las gráficas.
- Para `janelkit-kit`: las gráficas deben ir sobre `QtQuick.Shapes`. Un `Canvas` en JavaScript se queda corto a esta frecuencia.
