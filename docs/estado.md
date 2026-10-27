# Estado del desarrollo

Referencia: [`FluxUI_Plan_Desarrollo_v0.1.md`](../FluxUI_Plan_Desarrollo_v0.1.md). Actualizado: 26 de octubre de 2026.

**Entornos verificados:** Windows 11 con Python 3.13.9 + PySide6 6.12.0, y con Python 3.10.19 + PySide6 6.8.3 (las versiones mínimas declaradas): las 267 pruebas pasan en ambos. Linux y macOS **no se han probado** todavía: la CI (`.github/workflows/ci.yml`) está preparada para hacerlo en cuanto el repositorio tenga un remoto en GitHub.

## Backlog inicial (sección 11)

| PR | Entrega | Estado | Evidencia |
|---|---|---|---|
| PR-001 | Biblioteca instalable, `src/fluxui/`, tests, `project.scripts` → `flux` | ✅ | `pyproject.toml`, `pip install -e ".[dev]"` |
| PR-002 | App Qt Quick mínima iniciada desde `main.py` | ✅ | `spikes/qt_bridge_counter/main.py` |
| PR-003 | `QObject` con valor observable, señal y clic | ✅ | spike + `spikes/qt_bridge_counter/check.py` |
| PR-004 | Campo editable sincronizado sin bucles | ✅ | spike + `tests/test_runtime_qt.py::test_two_way_binding_without_loops` |
| PR-005 | Hallazgos del puente; decisión | ✅ **continuar** | `spikes/qt_bridge_counter/NOTES.md` |
| PR-006 | Extractor de secciones con localización de errores | ✅ | `compiler/sfc_parser.py`, `tests/test_parser.py` |
| PR-007 | Parser de elementos anidados y atributos | ✅ | `compiler/template_parser.py` |
| PR-008 | Ventana QML desde `App.flux` y API `run()` | ✅ | `compiler/qml_generator.py`, `qt_backend/application.py` |
| PR-009 | `flux new` mínimo + arranque desde carpeta nueva | ✅ | `cli/scaffolding.py`, `tests/test_cli.py` |
| PR-010 | Wheel instalado en entorno limpio con plantillas | ✅ | `python tools/check_wheel.py` |

## Incrementos

| Incremento | Estado | Entregable / evidencia |
|---|---|---|
| 0 — Validación técnica | ✅ | `spikes/qt_bridge_counter/` |
| 1 — Formato SFC y compilador mínimo | ✅ | `flux parse`, `tests/test_parser.py` |
| 2 — Primera interfaz compilada | ✅ | `flux compile`; errores de Qt remitidos al `.flux` |
| 3 — Estado, interpolación y eventos | ✅ | `examples/counter` |
| 4 — Entrada de datos y control de flujo | ✅ | `examples/todo`: lista editable, filtro, búsqueda y estado vacío |
| 5 — Composición de componentes | ✅ | `examples/todo-components`: `App.flux`, `TodoList.flux`, `TodoItem.flux` |
| 6 — Estilos y temas (**cierre del MVP**) | ✅ | `examples/notes`: barra lateral, formulario y tarjetas; tema claro/oscuro |
| 7 — Experiencia de desarrollo | ✅ | `flux dev`, `flux build`, plantilla mejorada, resaltado para VS Code |
| 8 — Estabilidad y distribución pública | ⏳ | Pendiente: CI con matriz, Linux/macOS, TestPyPI, licencia, nombre |
| 9 — Validación comunitaria | ⏳ | Requiere usuarios externos |

### Criterios de salida comprobados

- **Inc. 4** — escribir actualiza el estado (`bind:value`); añadir/eliminar actualiza la lista sin recrear la ventana; los condicionales montan y desmontan; las claves conservan la identidad de las filas al reordenar (`test_keys_preserve_row_identity_when_reordering`).
- **Inc. 5** — un componente reutilizado no mezcla estados (`test_component_instances_are_independent`); el hijo comunica resultados al padre con eventos; el desmontaje no deja suscripciones activas (`test_unmounted_child_stops_receiving_notifications`).
- **Inc. 6** — tipografía, espaciado, colores, bordes, radios y alineación desde `<style>`; tokens y dos temas; advertencias para lo no soportado (`tests/test_compiler.py`, `test_theme_switch_updates_tokens_in_qml`).
- **Inc. 7** — un cambio en un `.flux` se refleja sin reiniciar el comando; un error remite al `.flux` y conserva la última versión correcta; `python main.py` sigue funcionando sin `flux dev` (`tests/test_dev.py`).

### Pruebas de aceptación del MVP (sección 7)

| Prueba | Estado | Evidencia |
|---|---|---|
| Al pulsar «Agregar», aparece un elemento sin reconstruir toda la ventana | ✅ | `test_each_renders_inserts_updates_and_removes` |
| Al modificar la consulta, la lista filtrada se actualiza | ✅ | `test_notes_example_flow` (búsqueda en la barra lateral) |
| Al borrar una tarea, no se intercambia el estado local de otras filas | ✅ | `test_removing_a_row_keeps_local_state_of_the_others` |
| Al desmontar una tarjeta, deja de recibir notificaciones reactivas | ✅ | `test_unmounted_child_stops_receiving_notifications`, `test_removed_rows_release_their_subscriptions` |
| Al cambiar un tema, los colores y tipografías definidos por tokens cambian | ✅ | `test_theme_switch_updates_tokens_in_qml` |
| Al introducir una directiva mal formada, se indica el archivo y la línea | ✅ | `tests/test_parser.py` |
| La aplicación inicia sin QML escrito a mano en el proyecto | ✅ | `test_example_runs_with_python_main` |

## Decisiones provisionales tomadas al implementar

Cierran de forma **provisional** puntos del «Registro de decisiones pendientes» del plan para poder avanzar; pueden revisarse.

1. **Una sola raíz** en la plantilla. Si la raíz de la app no es `<Window>`, se envuelve en una ventana.
2. **Reactividad por seguimiento automático de lecturas** (no hay declaración estática de dependencias).
3. **Expresiones de plantilla = expresiones Python evaluadas en Python**, con desenvolvido automático de `state`/`computed`/props. QML solo lee propiedades del puente; nunca se traduce Python a JavaScript. Los nombres libres se resuelven al evaluarse (cadena: variables de bloque → script → builtins), así que también funcionan dentro de `lambda`. Para modificar estado desde la plantilla hay manejadores en línea (`on:click={n += 1}`): las asignaciones a nombres se reescriben como escrituras en el `state`.
4. **Puente por instancia de plantilla:** una clase `QObject` generada por plantilla (componente o fragmento de `{#each}`/`{#if}`/`{#key}`) con una propiedad notificable por binding, expuesta como `fx` (propiedad de contexto en la raíz; rol del modelo en cada fila).
5. **Regiones dinámicas = `Repeater` + modelo Python** (`QAbstractListModel` de puentes). La reconciliación por clave ocurre en Python y emite insertar/mover/eliminar filas; Qt conserva los delegados movidos. `{#if}` usa un modelo de 0 o 1 filas por rama, así que **desmonta** de verdad.
6. **Componentes = imports Python** (`from components.X import X`), resueltos estáticamente por el compilador. El script se reescribe (sin ejecutarse) para quitar esos imports e inyectar los componentes.
7. **Props y eventos declarados en el script** (`nombre = prop(defecto)`, `nombre = event()`), detectados estáticamente para validar los usos en el padre. Props de solo lectura; los hijos comunican cambios con eventos.
8. **Estilos sobre controles propios:** el compilador genera tipos de un módulo QML interno (`fluxui/qml/Flux`, distribuido en el wheel) basados en Qt Quick Controls *Basic* y Qt Quick Layouts. `Column`/`Row` reproducen el comportamiento de flex (sin repartir el espacio sobrante). Estilo Qt Quick por defecto: *Basic* (respetando `QT_QUICK_CONTROLS_STYLE`).
9. **Tokens de tema** en un `QQmlPropertyMap` global (`fxtheme`), sincronizado con `fluxui.theme`; `var(--x)` se compila a `fxtheme.x`.
10. **Clases condicionales** con `Binding on <prop> { when }` de QML: al desactivarse, la propiedad recupera su valor anterior.
11. **`flux dev`:** recarga en proceso para `.flux` conservando el estado de los componentes cuyo script no cambió (identidad por ruta en el árbol: etiqueta, ordinal en la plantilla del padre y claves de fila); reinicio del proceso para `.py` y `.qml`.
12. **`flux build`:** validación + QML generado; no empaqueta ejecutables.
13. **Contrato de `run(entry, argv=None) -> int`:** resuelve la ruta respecto al archivo, añade su carpeta a `sys.path`, imprime diagnósticos en stderr y devuelve 1 ante errores de compilación o del script; reutiliza la `QGuiApplication` existente si la hay.
14. **`main.py` generado:** `raise SystemExit(run(...))` en lugar de `run(...)` a secas, para que el código de salida llegue al sistema.
15. **Versiones mínimas declaradas:** Python ≥ 3.10, PySide6 ≥ 6.8 (versión LTS de Qt). Se probó 6.6 y se descartó: `AbstractButton.click()` no es invocable, los diálogos de QtQuick.Dialogs llegan a Python con un tipo erróneo y borrar una ventana desde Python termina en un fallo al salir.
16. **Plantillas como `*.tmpl`** dentro del paquete (`dot-` → `.`) para que pip no las importe ni compile.
17. **Colecciones reactivas por copia:** `state` convierte `list`/`dict`/`set` (exactamente esos tipos, en profundidad) en subclases reactivas; cada colección es su propia fuente de dependencias.
18. **Manejadores en línea:** `on:x={...}` es una función si la expresión es un nombre, atributo, índice, `lambda` o condicional; si no, se ejecuta en línea (como en Vue). `event` es el argumento del evento.
19. **Clases puente permanentes:** las clases `QObject` generadas se reutilizan y nunca se liberan, porque QML cachea metadatos por dirección del `QMetaObject`.
20. **Asincronía con `qasync`:** el bucle de `asyncio` corre sobre el de Qt (QtAsyncio, incluido en PySide6, aún no implementa red). Dependencia nueva: `qasync>=0.27` (BSD). Las tareas se registran en el ámbito reactivo activo y se cancelan al liberarlo.
21. **Contenido de slots como documentos QML aparte:** se generan en la compilación del padre y se cargan como delegado del `Repeater` del hijo.
22. **Elementos propios = archivos `.qml` importados como componentes:** el compilador lee las `property`/`signal` del objeto raíz (análisis léxico, sin motor QML) y genera un `import "<carpeta>" as FxUserN`. Con `bind:` se usa `Binding on` y solo se devuelven valores distintos, porque `<prop>Changed` también salta con los cambios de Python. Al cambiar un `.qml`, `flux dev` desmonta y vacía la caché de componentes de QML.

## Rendimiento medido (indicativo)

Windows 11, offscreen, lista de filas con casilla, texto y botón. Se reproduce con `python tools/bench.py`:

| Operación | 100 filas | 1000 filas |
|---|---|---|
| Crear la lista completa | 33 ms | 443 ms |
| Insertar una fila en medio (reasignando) | 1 ms | 7 ms |
| Insertar una fila en medio (`insert`) | 1 ms | 5 ms |
| Añadir al final (`append`) | 1 ms | 2 ms |
| Editar una fila (reasignando) | <1 ms | 3 ms |
| Editar una fila en el sitio (`todo["done"] = True`) | <1 ms | <1 ms |
| Invertir el orden (`reverse`) | 3 ms | 102 ms |
| Vaciar (`clear`) | 1 ms | 92 ms |

Modificar en el sitio un elemento de una colección reactiva solo actualiza los bindings que leyeron ese elemento.

Con `<List>` (virtualizada: solo se crean las filas visibles):

| Operación | 1000 filas | 10 000 filas |
|---|---|---|
| Crear la lista completa | 9 ms | 39 ms |
| Insertar una fila en medio (`insert`) | 2 ms | 16 ms |
| Editar una fila en el sitio | <1 ms | <1 ms |
| Invertir el orden | 11 ms | 25 ms |
| Vaciar | 1 ms | 3 ms |

En `<Scroll>` las filas se crean todas; para miles de elementos, usa `<List>`.

### Arranque y respuesta de una aplicación (indicativo)

`python tools/bench_app.py`. Arranque en frío de cada ejemplo, offscreen:

| Ejemplo | Importar | Compilar | Qt + montar | Total |
|---|---|---|---|---|
| counter | 214 ms | 10 ms | 38 ms | 262 ms |
| todo | 238 ms | 4 ms | 51 ms | 293 ms |
| notes | 225 ms | 9 ms | 51 ms | 285 ms |
| books | 205 ms | 3 ms | 79 ms | 287 ms |
| files | 206 ms | 9 ms | 56 ms | 271 ms |

Casi todo el arranque es importar PySide6. Compilar cuesta menos de 10 ms, así que **no hace falta una caché de compilación** por ahora.

Explorador (`examples/files`) sobre una carpeta de 5000 archivos:

| Operación | Tiempo |
|---|---|
| Listar la carpeta (hilo aparte + lista) | 62 ms |
| Filtrar (quedan 10) | 12 ms |
| Quitar el filtro (vuelven todos) | 31 ms |
| Ordenar por tamaño | 31 ms |
| Elegir un archivo | 3 ms |

## Validación con aplicaciones reales

`examples/files` (explorador de archivos) y `examples/books` (cliente de una API) se construyeron sin tocar el framework a mano y están cubiertos por `tests/test_inspect.py` y `tests/test_examples.py`. Lo que salió al construirlas, ya corregido:

1. **Un componente con `flex` en su etiqueta no ocupaba su caja:** la caja exterior crecía, pero la raíz del componente no. Ahora la caja exterior hace que su raíz la llene.
2. **`flex` no repartía en proporción:** Qt reparte según el tamaño natural del contenido (un texto largo se quedaba con todo). `FxRow`/`FxColumn` calculan ahora el reparto como CSS (`flex: N 1 0`) cuando su tamaño viene de fuera.
3. **Procesar eventos de Qt dentro de una corrutina** hacía que asyncio ejecutara una tarea dentro de otra. `Application.process_events()` procesa con el bucle marcado como activo y fuera de cualquier corrutina.
4. **En pruebas, un clic sobre el texto de una fila** no llegaba a la fila. `Element.click()` sube hasta el contenedor con `on:click`, como un clic real.

## Limitaciones conocidas

- Los objetos propios modificados en el sitio no se detectan (las listas, diccionarios y conjuntos sí): llama a `estado.notify()`.
- Sin empaquetado de aplicaciones (`.exe`, `.app`).
- Nombre `fluxui`/`flux` y extensión `.flux` siguen siendo provisionales y **no se han verificado en PyPI**. No se ha publicado nada.
- Licencia sin decidir.

## Siguientes pasos

Todos los pendientes P0, P1 y P2 de [lanzamiento.md](lanzamiento.md) están hechos salvo dos, que dependen de decisiones o de infraestructura del autor:

1. **CI en Linux y macOS (punto 11):** la configuración está lista en `.github/workflows/ci.yml`; falta un repositorio remoto en GitHub para ejecutarla.
2. **Nombre, licencia y publicación (punto 17):** verificar `fluxui`/`flux` en PyPI, elegir licencia y publicar primero en TestPyPI.

Después: Incremento 9 (validación con usuarios externos, a partir del [tutorial](tutorial.md)).
