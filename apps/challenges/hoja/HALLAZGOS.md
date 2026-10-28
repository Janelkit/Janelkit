# Hallazgos: hoja de cálculo (reto 2)

Construida solo con la API pública, sin QML propio. Lo que faltaba y entraba en el alcance del núcleo se corrigió durante el reto; lo demás queda como propuesta.

Gravedad: **Bloquea** (no se podía hacer o salía mal), **Molesta** (había que dar un rodeo), **Detalle**.

## Resueltos en el núcleo durante el reto

| # | Qué intenté | Qué pasó | Gravedad | Solución |
|---|---|---|---|---|
| 1 | Mover la celda activa con las flechas | Cada celda leía la selección (`vista.rango`), y un `computed` avisaba a quien lo lee aunque su valor no cambiase: una flecha reevaluaba las clases de **todas** las celdas. Calcular por fila «¿estoy en la selección?» no servía de nada | Bloquea | **Corte por igualdad** en la reactividad: un efecto avisado solo por `computed` los recalcula primero y solo se ejecuta si alguno cambió de valor (para valores inmutables: números, texto, tuplas…). Pruebas en `packages/janelkit/tests/test_reactivity.py` |
| 2 | Recorrer la hoja con AvPág y después mover la selección | `<List>` conserva la parte Python de las filas que salen de pantalla, con sus bindings **activos**. Tras 10 páginas, una sola tecla reevaluaba 8 889 bindings (de ~380 filas vivas, 40 visibles), y editar una celda de la que dependían 1 000 fórmulas tardaba 155 ms *sin ninguna a la vista* | Bloquea | Cada fila de `<List>` tiene una **compuerta** (`Gate`, la de `{#hidden}`) que se cierra cuando Qt destruye su vista: lo que muestra espera y se actualiza una vez al volver. Prueba `test_rows_off_screen_wait_until_they_are_shown_again` |
| 3 | Probar AvPág con `inspect`: `rejilla.key("PageDown")` | No pulsaba nada y la prueba seguía: `inspect.key` esperaba el nombre de Qt (`PgDown`) y `event.key` da el de la web (`PageDown`) | Molesta (fallo) | `key()` acepta los nombres de `event.key` (`PageDown`, `ArrowRight`…) y da error con una tecla que no entiende |

Antes y después de los tres (`python bench.py`, 10 000 × 26, ventana de 1280 × 800):

| Medida | Antes | Después |
|---|---|---|
| Flecha abajo | 47 ms | 29 ms |
| AvPág (una página de filas nuevas) | 607 ms | 192 ms |
| Seleccionar 30 × 10 | 551 ms | 136 ms |
| Editar una celda de la que dependen 1 000 fórmulas, ninguna a la vista | 155 ms | 0,02 ms |
| Ordenar 10 000 filas | 1 602 ms | 337 ms |
| Memoria tras recorrer ~500 filas | +614 MB | +479 MB |

(«Después» incluye también lo que hizo la aplicación: cada celda es un solo `<Text>` y los eventos de puntero los recibe la fila.)

## Pendientes (propuestas)

| # | Qué intenté | Qué pasó | Gravedad | Propuesta |
|---|---|---|---|---|
| 4 | Rejilla de 10 000 × 26 con desplazamiento en las dos direcciones | `<List>` virtualiza filas, pero sus filas ocupan su ancho: no hay desplazamiento horizontal ni columnas virtualizadas. Las columnas se virtualizan a mano (`services/vista.py`: `inicio`, `caben`, `on:resize`, Mayús+rueda), y el desplazamiento horizontal va de columna en columna. Congelar la columna A sale de ahí; congelar la fila 1 es mostrarla fuera de la lista | Molesta | Un `<Table>`/`<Grid>` sobre `TableView` (virtualiza en 2D, cabeceras y filas/columnas fijas), en el núcleo o en `janelkit-kit` |
| 5 | AvPág fluido | Crear la vista de una fila (11 `<Text>`) cuesta ~4,5 ms en Qt: una página de 40 filas, 192 ms. Con la rueda (3 filas por paso) la mediana es 13 ms, pero hay picos de 99 ms | Molesta | Aligerar `JkText` (también en tiempo de creación, no solo memoria: hallazgo 9 del reto 3) y probar `reuseItems` en el `ListView` de `<List>`: reutilizar delegados en vez de destruirlos y crearlos, que encaja con la compuerta del hallazgo 2 |
| 6 | Recorrer toda la hoja | Las filas que salen de pantalla ya no recalculan (hallazgo 2), pero siguen en memoria: +479 MB tras recorrer ~500 filas. Recorrer las 10 000 acumularía todas | Molesta | Liberar la parte Python de las filas que llevan tiempo sin vista. Rompe lo que hoy promete `<List>` (el estado local de la fila se conserva), así que haría falta decidir cómo: p. ej. solo en filas sin estado propio, o con una opción en `<List>` |
| 7 | Deshacer y rehacer cada cambio | Segunda vez que una aplicación se lo hace a mano. Aquí, con instantáneas por celda (lo que había y lo que hay, ~40 líneas en `services/hoja.py`); en el reto 3, con operaciones que devuelven su inversa (~100 líneas). Ninguno de los dos sirve tal cual al otro | Molesta | ✅ Después del reto: `History` en el núcleo admite los dos. Propuesta original: registrar como un paso con nombre los cambios de `State` y colecciones hechos dentro de un `batch` (sirve a la hoja), y dejar pasos propios con su inversa (sirve al Kanban). Al final fue al revés: el Kanban usa `step` (sus listas son reactivas) y la hoja `add`, porque lo escrito vive en un diccionario normal |
| 8 | Que la selección no cueste lo mismo en todas las celdas | Con el hallazgo 1 resuelto, hace falta saber que conviene calcular por fila (`sel`, `cur` en `Fila.janel`) lo que leen sus celdas. No está documentado | Detalle | Una sección «Listas grandes y estado compartido» en la guía, con este patrón |
| 9 | Editar en el sitio, encima de la celda | No se puede saber dónde está un elemento: la posición del editor se calcula a mano (`ANCHO_NUM + índice × ANCHO_COL`), y se rompería si las columnas tuvieran anchos distintos | Detalle | `ref.rect()` (como el hallazgo 11 del reto 3) |
| 10 | Usar un color del tema que no existe (`var(--muted)`) | Compila; al ejecutar, un aviso de QML («Unable to assign [undefined] to QColor») con la línea del `.janel` | Detalle | Que el compilador avise de los tokens que el tema no define |

## Lo que funcionó sin tocar nada

- **`computed` perezosos para las fórmulas.** Cada celda leída es un `state` con lo escrito y un `computed` con su valor; las fórmulas leen otras celdas y JanelKit registra las dependencias solas. Como son perezosos, una celda de la que dependen 1 000 fórmulas se edita en 1–5 ms: solo se recalculan las que se ven (o las que necesita un total a la vista).
- **Teclado.** `on:keydown` con modificadores y `event.prevent()` en la rejilla; el campo del editor gestiona Intro, Tab y Escape y para los demás corta la propagación con `event.stop()`.
- **Portapapeles.** `janelkit_desktop.clipboard` con texto separado por tabuladores, también lo que copia Excel (`\r\n`, comillas).
- **Abrir un CSV de 10 000 × 26** en 0,37 s, montaje incluido: lo escrito vive en un diccionario normal y solo se crean celdas reactivas para lo que se lee.

## Mediciones

`python bench.py` (Windows 11, Python 3.13, PySide6 6.12, offscreen; los tiempos incluyen Python y Qt Quick, no el dibujado):

| Medida | Resultado |
|---|---|
| Abrir el CSV de 10 000 × 26 y montar | 372 ms |
| Volver a abrir el CSV con la hoja a la vista | 110 ms |
| Flecha abajo / columna a la derecha | 29 ms / 33 ms |
| Rueda, 3 filas por paso | p50 13 ms, máx 99 ms |
| AvPág / Ctrl+Fin | 192 ms / 183 ms |
| Editar con 1 000 fórmulas dependientes: ~30 a la vista / un total que las suma todas / ninguna | 1,2 ms / 5,4 ms / 0,02 ms |
| Seleccionar 30 × 10 / toda la hoja (con suma y promedio) | 136 ms / 299 ms |
| Ordenar 10 000 filas / deshacerlo | 337 ms / 97 ms |

**«Hecho cuando»:**

- Abrir un CSV de 10 000 × 26 en menos de 1 s: ✅ 0,37 s.
- Desplazamiento fluido en las dos direcciones: 🟡 con la rueda, casi (mediana de 13 ms, picos de 99 ms); de columna en columna, 33 ms; AvPág, 192 ms (hallazgo 5).
- Editar una celda de la que dependen 1 000 fórmulas en menos de 100 ms: ✅ 1–5 ms.
- Navegar, editar, seleccionar, copiar, pegar y deshacer sin ratón: ✅ (`apps/challenges/tests/test_challenge_hoja.py`).

## Vía de escape usada

Ninguna. Todo es `.janel` y Python con la API pública.

## Veredicto

Una hoja de cálculo de 10 000 × 26 se puede hacer con JanelKit, y la reactividad (fórmulas como `computed`) es su punto fuerte. Los dos fallos que lo impedían eran generales de la reactividad y de `<List>`, y su arreglo beneficia a cualquier lista grande. Para que sea cómoda faltan dos piezas: un elemento de tabla con virtualización en 2D (hallazgo 4), que evita virtualizar columnas a mano, y que crear filas en Qt cueste menos (hallazgo 5). Deshacer/rehacer ya está en el núcleo (`History`, hallazgo 7) y lo usan esta aplicación y el Kanban.
