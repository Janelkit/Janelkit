# Hallazgos: cliente de chat (reto 4)

Construido solo con la API pública. Lo que faltaba y entraba en el alcance del núcleo ([alcance.md](../../../docs/alcance.md)) se añadió al framework durante el reto; lo demás queda como propuesta.

Gravedad: **Bloquea** (no se podía hacer), **Molesta** (había que dar un rodeo), **Detalle**.

## Resueltos en el núcleo durante el reto

| # | Qué intenté | Qué pasó | Gravedad | Solución |
|---|---|---|---|---|
| 1 | Que la lista de mensajes empiece abajo y siga a los nuevos | `<List>` no tenía control del desplazamiento | Bloquea | `<List follow>`, `on:top`, `on:bottom`, `on:scroll` y `ref.scroll_to_end()` / `scroll_to_start()` / `scroll_to(i)` |
| 2 | Saber si el usuario está abajo (botón «N mensajes nuevos ↓», no marcar como leído) | `on:top`/`on:bottom` solo avisan al llegar, no al irse | Bloquea | `on:scroll` con `{"top", "bottom", "y", "height"}`, como mucho una vez por fotograma |
| 3 | Cargar 50 mensajes de historial arriba | Por encima de 64 cambios la lista se reiniciaba y volvía al principio | Bloquea | Las inserciones se aplican por bloques contiguos (`insert_many`), sin reiniciar, en cualquier cantidad |
| 4 | Cargar historial estando arriba del todo | ListView enseñaba las filas nuevas en lugar de mantener la que se leía | Bloquea | Con `follow`, anclaje explícito: la fila visible se queda en el mismo sitio de la pantalla |
| 5 | `scroll_to_start()` con `follow` | Un reposicionamiento pendiente devolvía la vista al final | Bloquea | Las colocaciones por código cancelan las pendientes |
| 6 | Cambiar de sala (`{#key}` recrea la lista) | `Qt.callLater` sobre una lista que se estaba destruyendo daba `TypeError` | Molesta | Temporizadores propios que mueren con la lista |
| 7 | Negrita, enlaces y código en los mensajes | `<Text>` solo mostraba texto plano | Bloquea | `<Text format="markdown">` (y `"html"`), cursor de mano y `on:link`; sin manejador, el enlace se abre en el navegador |
| 8 | Saber si el usuario está mirando la ventana | No había eventos de ventana | Bloquea | `<Window on:activate on:deactivate>` |
| 9 | Avisar de mensajes con la ventana en segundo plano | No había notificaciones | Bloquea | `fluxui.notify(título, mensaje, on_click=)` con la bandeja nativa de Qt (sin QtWidgets); `MountedApp.notifications()` para pruebas |
| 10 | Contadores de no leídos y reacciones como «pastillas» | `<Text>` no admitía fondo ni borde: había que envolverlo en un `<Row>` | Molesta | `background`, `border` y `border-radius` en `<Text>` |
| 11 | Botones fantasma con un emoji | Medían como mínimo 64 px | Detalle | Los botones `ghost` no tienen ancho mínimo |
| 12 | `class={"bubble mine" if mine else "bubble"}` en un `<Column>` | El compilador avisaba de todas las reglas de texto del `<style>` («font-size no tiene efecto en Column») | Molesta (falso aviso) | Con `class={expr}` se ignoran sin avisar las clases que no aplican al elemento |
| 13 | `on:scroll`, `on:link` y `RadioGroup`/`Tabs`/`TextArea` | Qt avisaba de que inyectar parámetros de señal en los manejadores está obsoleto (dejará de funcionar) | Molesta (futuro error) | El QML generado declara los parámetros: `onX: function(info) {…}`. También en los `.qml` propios |
| 14 | Probar «pulsar la sala Python» | `inspect` no podía buscar una fila pulsable por su nombre | Molesta | `find(label="Python")` y `Element.label` |

## Pendientes (propuestas)

| # | Qué intenté | Qué pasó | Gravedad | Propuesta |
|---|---|---|---|---|
| 15 | Indicador «escribiendo…» que se borra a los 3 s | No hay temporizadores: una corrutina con `asyncio.sleep` y cancelación a mano | Molesta | ✅ Resuelto en el reto 1: `timeout(3000, fn)` y `.restart()` en cada aviso |
| 16 | Copiar el texto de un mensaje | `<Text>` no se puede seleccionar | Molesta | `<Text selectable>` (un `TextEdit` de solo lectura con el mismo formato) |
| 17 | Mostrar Markdown de otras personas | El Markdown de Qt acepta HTML; hay que escaparlo a mano, y el escape se ve literal dentro de `código` (`a &lt; b`) | Molesta (seguridad) | Que `format="markdown"` no interprete HTML (`MarkdownNoHTML`) y dejar `"html"` para quien lo quiera |
| 18 | Icono propio en la notificación y en la bandeja | Se usa el icono de FluxUI; no hay forma de dar el de la aplicación | Molesta | `<Window icon="...">` o `run(..., icon=)`, usado también por `notify` |
| 19 | Contador de no leídos en el icono de la bandeja, menú de la bandeja | No existe | Detalle | Ampliar `fluxui.notify` con un `tray` (icono, menú, insignia) |
| 20 | `room.messages` en la plantilla | Solo se desenvuelven los `state` de nivel superior: dentro de un objeto hay que escribir `.value` | Detalle | Decisión de diseño (como Vue). Documentarlo en el lenguaje |
| 21 | El nombre de la sala árabe en una interfaz en español | Qt alinea cada texto según su propio idioma («# العربية» a la derecha) | Detalle | Opción de alineación natural frente a la del diseño (`text-align: start`) |
| 22 | Simular «la ventana pierde el foco» en pruebas | `inspect` no puede activar o desactivar ventanas | Detalle | `MountedApp.activate()` / `deactivate()` |

## Mediciones

Windows 11, Python 3.13, PySide6 6.12, ventana visible. El servidor corre en otro proceso (`bench.py`).

| Medida | Objetivo | Resultado |
|---|---|---|
| 20 mensajes/s durante 5 min: mensajes recibidos | 6 000 | 6 021 (19,7–20,4/s), ninguno perdido |
| CPU del proceso de la interfaz | — | 2–10 % |
| Retraso del bucle de eventos (tarea cada 50 ms) | sin bloqueos apreciables | p50 12–14 ms y p99 17–28 ms (la base es ~12 ms por la resolución del temporizador de Windows); máximo 113 ms en 5 min |
| Memoria con 20 msg/s | se estabiliza | 217 → 288 MB en 5 min; sube mientras las salas se llenan (hasta 600 mensajes) y luego despacio |
| Memoria con 100 msg/s (18 000 mensajes) | se estabiliza | oscila entre +34 y +49 MB desde los ~10 000 mensajes: sin fuga (objetos Python y QObject vivos constantes) |
| Cargar historial (bloques de 50) | el mensaje visible no se mueve | sin desplazamiento (prueba `test_prepending_*`), también arriba del todo |
| Cortar el servidor y levantarlo | reconecta sin perder mensajes ni bloquear | reconecta en < 1 s y recupera los mensajes perdidos (`test_reconnects_and_recovers_missed_messages`) |

## Vía de escape usada

Ninguna: ni `.qml` propio ni acceso a Qt desde la aplicación. Solo el banco de pruebas (`bench.py`) desactiva las notificaciones reales tocando un detalle interno.

## Veredicto

- **Al empezar, no se podía construir** con la API pública: faltaban el control del desplazamiento, el texto enriquecido, los eventos de ventana y las notificaciones, y la lista perdía la posición al cargar historial. Con lo añadido al núcleo (puntos 1–14), **sí**, sin vía de escape.
- La asincronía (`spawn` + `qasync` + WebSocket) funcionó a la primera: una corrutina que vive toda la sesión, con reconexión y cancelación al cerrar, sin hilos.
- El rendimiento sobra para un chat: 20 mensajes/s con la lista siguiendo al final usan menos del 10 % de CPU.
- Lo que más se echaba de menos eran los **temporizadores** (15, ya resueltos en el reto 1) y el **texto seleccionable** (16). El Markdown seguro (17) conviene decidirlo antes de publicar, porque cambiar después qué interpreta `format="markdown"` rompería aplicaciones.
