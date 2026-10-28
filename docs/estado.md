# Estado del desarrollo

Referencia: [`JanelKit_Plan_Desarrollo_v0.1.md`](../JanelKit_Plan_Desarrollo_v0.1.md). Actualizado: 26 de octubre de 2026.

**Entornos verificados:** Windows 11 con Python 3.13.9 + PySide6 6.12.0, y con Python 3.10.19 + PySide6 6.8.3 (las versiones mínimas declaradas): las 523 pruebas pasan en ambos (la vía rápida de `Column`/`Row` y las cajas ligeras, comprobadas con PySide6 6.12.0 y 6.8.3). Linux y macOS **no se han probado** todavía: la CI (`.github/workflows/ci.yml`) está preparada para hacerlo en cuanto el repositorio tenga un remoto en GitHub.

## Backlog inicial (sección 11)

| PR | Entrega | Estado | Evidencia |
|---|---|---|---|
| PR-001 | Biblioteca instalable, `src/janelkit/`, tests, `project.scripts` → `janel` | ✅ | `pyproject.toml`, `pip install -e ".[dev]"` |
| PR-002 | App Qt Quick mínima iniciada desde `main.py` | ✅ | `spikes/qt_bridge_counter/main.py` |
| PR-003 | `QObject` con valor observable, señal y clic | ✅ | spike + `spikes/qt_bridge_counter/check.py` |
| PR-004 | Campo editable sincronizado sin bucles | ✅ | spike + `tests/test_runtime_qt.py::test_two_way_binding_without_loops` |
| PR-005 | Hallazgos del puente; decisión | ✅ **continuar** | `spikes/qt_bridge_counter/NOTES.md` |
| PR-006 | Extractor de secciones con localización de errores | ✅ | `compiler/sfc_parser.py`, `tests/test_parser.py` |
| PR-007 | Parser de elementos anidados y atributos | ✅ | `compiler/template_parser.py` |
| PR-008 | Ventana QML desde `App.janel` y API `run()` | ✅ | `compiler/qml_generator.py`, `qt_backend/application.py` |
| PR-009 | `janel new` mínimo + arranque desde carpeta nueva | ✅ | `cli/scaffolding.py`, `tests/test_cli.py` |
| PR-010 | Wheel instalado en entorno limpio con plantillas | ✅ | `python tools/check_wheel.py` |

## Incrementos

| Incremento | Estado | Entregable / evidencia |
|---|---|---|
| 0 — Validación técnica | ✅ | `spikes/qt_bridge_counter/` |
| 1 — Formato SFC y compilador mínimo | ✅ | `janel parse`, `tests/test_parser.py` |
| 2 — Primera interfaz compilada | ✅ | `janel compile`; errores de Qt remitidos al `.janel` |
| 3 — Estado, interpolación y eventos | ✅ | `examples/counter` |
| 4 — Entrada de datos y control de flujo | ✅ | `examples/todo`: lista editable, filtro, búsqueda y estado vacío |
| 5 — Composición de componentes | ✅ | `examples/todo-components`: `App.janel`, `TodoList.janel`, `TodoItem.janel` |
| 6 — Estilos y temas (**cierre del MVP**) | ✅ | `examples/notes`: barra lateral, formulario y tarjetas; tema claro/oscuro |
| 7 — Experiencia de desarrollo | ✅ | `janel dev`, `janel build`, plantilla mejorada, resaltado para VS Code |
| 8 — Estabilidad y distribución pública | ⏳ | Pendiente: CI con matriz, Linux/macOS, TestPyPI, licencia, nombre |
| 9 — Validación comunitaria | ⏳ | Requiere usuarios externos |

### Criterios de salida comprobados

- **Inc. 4** — escribir actualiza el estado (`bind:value`); añadir/eliminar actualiza la lista sin recrear la ventana; los condicionales montan y desmontan; las claves conservan la identidad de las filas al reordenar (`test_keys_preserve_row_identity_when_reordering`).
- **Inc. 5** — un componente reutilizado no mezcla estados (`test_component_instances_are_independent`); el hijo comunica resultados al padre con eventos; el desmontaje no deja suscripciones activas (`test_unmounted_child_stops_receiving_notifications`).
- **Inc. 6** — tipografía, espaciado, colores, bordes, radios y alineación desde `<style>`; tokens y dos temas; advertencias para lo no soportado (`tests/test_compiler.py`, `test_theme_switch_updates_tokens_in_qml`).
- **Inc. 7** — un cambio en un `.janel` se refleja sin reiniciar el comando; un error remite al `.janel` y conserva la última versión correcta; `python main.py` sigue funcionando sin `janel dev` (`tests/test_dev.py`).

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
4. **Puente por instancia de plantilla:** una clase `QObject` generada por plantilla (componente o fragmento de `{#each}`/`{#if}`/`{#key}`) con una propiedad notificable por binding, expuesta como `jk` (propiedad de contexto en la raíz; rol del modelo en cada fila).
5. **Regiones dinámicas = `Repeater` + modelo Python** (`QAbstractListModel` de puentes). La reconciliación por clave ocurre en Python y emite insertar/mover/eliminar filas; Qt conserva los delegados movidos. `{#if}` usa un modelo de 0 o 1 filas por rama, así que **desmonta** de verdad.
6. **Componentes = imports Python** (`from components.X import X`), resueltos estáticamente por el compilador. El script se reescribe (sin ejecutarse) para quitar esos imports e inyectar los componentes.
7. **Props y eventos declarados en el script** (`nombre = prop(defecto)`, `nombre = event()`), detectados estáticamente para validar los usos en el padre. Props de solo lectura; los hijos comunican cambios con eventos.
8. **Estilos sobre controles propios:** el compilador genera tipos de un módulo QML interno (`janelkit/qml/Janel`, distribuido en el wheel) basados en Qt Quick Controls *Basic* y Qt Quick Layouts. `Column`/`Row` reproducen el comportamiento de flex (sin repartir el espacio sobrante). Estilo Qt Quick por defecto: *Basic* (respetando `QT_QUICK_CONTROLS_STYLE`).
9. **Tokens de tema** en un `QQmlPropertyMap` global (`jktheme`), sincronizado con `janelkit.theme`; `var(--x)` se compila a `jktheme.x`.
10. **Clases condicionales** con `Binding on <prop> { when }` de QML: al desactivarse, la propiedad recupera su valor anterior.
11. **`janel dev`:** recarga en proceso para `.janel` conservando el estado de los componentes cuyo script no cambió (identidad por ruta en el árbol: etiqueta, ordinal en la plantilla del padre y claves de fila); reinicio del proceso para `.py` y `.qml`.
12. **`janel build`:** validación + QML generado; no empaqueta ejecutables.
13. **Contrato de `run(entry, argv=None) -> int`:** resuelve la ruta respecto al archivo, añade su carpeta a `sys.path`, imprime diagnósticos en stderr y devuelve 1 ante errores de compilación o del script; reutiliza la `QGuiApplication` existente si la hay.
14. **`main.py` generado:** `raise SystemExit(run(...))` en lugar de `run(...)` a secas, para que el código de salida llegue al sistema.
15. **Versiones mínimas declaradas:** Python ≥ 3.10, PySide6 ≥ 6.8 (versión LTS de Qt). Se probó 6.6 y se descartó: `AbstractButton.click()` no es invocable, los diálogos de QtQuick.Dialogs llegan a Python con un tipo erróneo y borrar una ventana desde Python termina en un fallo al salir.
16. **Plantillas como `*.tmpl`** dentro del paquete (`dot-` → `.`) para que pip no las importe ni compile.
17. **Colecciones reactivas por copia:** `state` convierte `list`/`dict`/`set` (exactamente esos tipos, en profundidad) en subclases reactivas; cada colección es su propia fuente de dependencias.
18. **Manejadores en línea:** `on:x={...}` es una función si la expresión es un nombre, atributo, índice, `lambda` o condicional; si no, se ejecuta en línea (como en Vue). `event` es el argumento del evento.
19. **Clases puente permanentes:** las clases `QObject` generadas se reutilizan y nunca se liberan, porque QML cachea metadatos por dirección del `QMetaObject`.
20. **Asincronía con `qasync`:** el bucle de `asyncio` corre sobre el de Qt (QtAsyncio, incluido en PySide6, aún no implementa red). Dependencia nueva: `qasync>=0.27` (BSD). Las tareas se registran en el ámbito reactivo activo y se cancelan al liberarlo.
21. **Contenido de slots como documentos QML aparte:** se generan en la compilación del padre y se cargan como delegado del `Repeater` del hijo.
22. **Elementos propios = archivos `.qml` importados como componentes:** el compilador lee las `property`/`signal` del objeto raíz (análisis léxico, sin motor QML) y genera un `import "<carpeta>" as JkUserN`. Con `bind:` se usa `Binding on` y solo se devuelven valores distintos, porque `<prop>Changed` también salta con los cambios de Python. Al cambiar un `.qml`, `janel dev` desmonta y vacía la caché de componentes de QML.
23. **Nombre definitivo: JanelKit** (28 de octubre de 2026; de *janela*, «ventana» en portugués). Sustituye al provisional FluxUI: «Flux UI» ya es una biblioteca comercial de componentes para Laravel Livewire (fluxui.dev), el paquete `flux` de PyPI está ocupado y el comando `flux` choca con la CLI de Flux CD. Verificado libre: `janelkit` en PyPI, npm y GitHub; `janel` en PyPI. Equivalencias:

    | Qué | Antes | Ahora | Público |
    |---|---|---|---|
    | Paquete PyPI e import | `fluxui` | `janelkit` | sí |
    | Comando | `flux` | `janel` | sí |
    | Extensión de componentes | `.flux` | `.janel` | sí |
    | Variables de entorno | `FLUXUI_*` | `JANELKIT_*` | sí |
    | Objetos en `.qml` propios | `fxtheme`, `fxi18n` | `jktheme`, `jki18n` | sí |
    | Excepción de diagnósticos | `FluxError` | `JanelError` | sí |
    | Módulo QML interno | `Flux` | `Janel` | no |
    | Prefijo de tipos QML internos | `Fx` (`FxBox`…) | `Jk` (`JkBox`…) | no |
    | Logger | `fluxui` | `janelkit` | — |
    | Extensión de editor | `editors/vscode`, lenguaje `flux` | `janelkit-vscode`, lenguaje `janel` | sí |

    Como no se ha publicado nada, no se mantienen alias del nombre anterior (ni `import fluxui` ni archivos `.flux`).

## Rendimiento medido (indicativo)

Windows 11, offscreen, lista de filas con casilla, texto y botón. Se reproduce con `python tools/bench.py`:

| Operación | 100 filas | 1000 filas |
|---|---|---|
| Crear la lista completa | 38 ms | 430 ms |
| Insertar una fila en medio (reasignando) | 1 ms | 7 ms |
| Insertar una fila en medio (`insert`) | 1 ms | 5 ms |
| Añadir al final (`append`) | 1 ms | 2 ms |
| Editar una fila (reasignando) | <1 ms | 3 ms |
| Editar una fila en el sitio (`todo["done"] = True`) | <1 ms | <1 ms |
| Invertir el orden (`reverse`) | 2 ms | 93 ms |
| Vaciar (`clear`) | 2 ms | 39 ms |

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
2. **`flex` no repartía en proporción:** Qt reparte según el tamaño natural del contenido (un texto largo se quedaba con todo). `JkRow`/`JkColumn` calculan ahora el reparto como CSS (`flex: N 1 0`) cuando su tamaño viene de fuera.
3. **Procesar eventos de Qt dentro de una corrutina** hacía que asyncio ejecutara una tarea dentro de otra. `Application.process_events()` procesa con el bucle marcado como activo y fuera de cualquier corrutina.
4. **En pruebas, un clic sobre el texto de una fila** no llegaba a la fila. `Element.click()` sube hasta el contenedor con `on:click`, como un clic real.

### Retos ([challenges_to_test.md](challenges_to_test.md))

- **Chat (reto 4):** hecho, en `examples/challenges/chat`, con pruebas en `tests/test_challenge_chat.py` y [registro de hallazgos](../examples/challenges/chat/HALLAZGOS.md). Añadió al núcleo el desplazamiento de `<List>` (`follow`, `on:top`/`on:bottom`/`on:scroll`, `ref.scroll_to_*`), las inserciones por bloques sin reiniciar la lista, `<Text format="markdown">` con `on:link`, fondo y borde en `<Text>`, `on:activate`/`on:deactivate` en `<Window>`, `janelkit.notify`, y parámetros de señal declarados en el QML generado. Medido: 20 mensajes/s durante 5 min con menos del 10 % de CPU; la memoria se estabiliza.

- **Panel (reto 1):** hecho, en `examples/challenges/panel`, con pruebas en `tests/test_challenge_panel.py` y [registro de hallazgos](../examples/challenges/panel/HALLAZGOS.md). Añadió al núcleo los temporizadores (`interval`, `timeout`), el formato en el texto (`{x:.1f}`) y `MountedApp.windows()`. Corrigió que las listas modificadas en el sitio no llegaran a QML cuando se pasan enteras a un control, que una `<List>` volviera arriba al reordenar muchas filas, `flex` en elementos QML propios, `janel build` con ventanas de `open_window` y un aviso al salir. Medido: 50 métricas 10 veces por segundo durante 10 min con un 12 % del hilo de la interfaz, memoria estable y menos de 30 ms hasta la pantalla.

### Elementos base

- **`<flex>` (fase 1 de 6, [flex.md](flex.md)):** caja y motor de disposición propio (flexbox de CSS en JS interno, calculado en la fase de *polish* de Qt Quick antes de cada fotograma). `Column` y `Row` son atajos suyos. Validado con la rejilla y la barra de herramientas de `examples/flex` (`tests/test_flex_qt.py`, `tests/test_example_flex.py`). Medido (`examples/flex/bench.py`, ventana real): crear 1000 cajas, 220 ms con `Column` (antes 238 ms) y 251 ms con `<flex>` en fila (+5 %). Redimensionar una rejilla de 200 tarjetas cuesta 14 ms de mediana por fotograma (p99 18 ms): el objetivo de 4 ms **no se cumple todavía**. Son unas 600 cajas, porque cada tarjeta lleva la caja exterior de un componente con `class`, que desaparece en la fase 5; sin ella, el motor baja de 4,9 a 3,5 ms por pasada (medido sin pantalla).
- **Estados y selectores (fase 2):** pseudo-clases, selectores compuestos y de descendiente, `transform`, `cursor`, `box-shadow`, `outline`, todo resuelto al compilar en condiciones de la vista (`compiler/cascade.py`); un solo `Binding` por propiedad para que el resultado no dependa del orden en que Qt los procese (en PySide 6.8 sí dependía). Validado con el botón y la tarjeta de `examples/flex` (`tests/test_flex_states.py`). Medido: crear 1000 filas no cambia (463 ms frente a 461 ms sin la transformación). 
- **Eventos y accesibilidad (fase 3):** eventos de puntero, rueda, teclado, foco y tamaño con propagación, `prevent()` y `stop()` (`qt_backend/events.py`, un filtro por ventana), `as`, `tabindex`, `disabled`, `title`, `pointer-events`, `visibility`. Validado con el botón, el chip, el interruptor y el menú de `examples/flex` (`tests/test_flex_events.py`). Medido: crear 1000 filas sin eventos, 478 ms (+3 % frente a la fase 2); con `on:click`, 488 ms. 
- **Herencia y variables (fase 4):** texto heredado, variables propias y `style=` (`JkContext.qml`, `JkTextInherit.qml`: un enlace por propiedad heredada que se usa), validados con la tabla y las pestañas segmentadas de `examples/flex` (`tests/test_flex_inherit.py`). 
- **Componentes como elementos (fase 5):** los atributos de la etiqueta van a la raíz del componente (`JkRemote.qml`), sin caja exterior (`tests/test_flex_components.py`). Rendimiento de la rejilla: 44 ms por paso con el catálogo actual (48 ms antes); el objetivo de 4 ms no se cumple (ver [flex.md](flex.md), fase 5).
- **Posición (fase 6):** `position` (relative, absolute, fixed), `inset`, `z-index`, validados con la insignia, el menú en el puntero y el diálogo superpuesto de `examples/flex` (`tests/test_flex_position.py`). Con esto están las seis fases de [flex.md](flex.md). Pendiente: el rendimiento de la rejilla grande (ver fase 5).
- **Vía rápida de `Column`/`Row`:** el compilador elige caja a caja entre un layout de Qt (`JkColumn`, `JkRow`, `JkQtBox`) y el motor de `<flex>` (`JkFlexColumn`, `JkFlexRow`, `JkFlex`), según lo que usen la caja y sus hijos (`compiler/layout_choice.py`; `tests/test_layout_choice.py`). Las dos vías colocan igual en todos los ejemplos. Medido con 300 tarjetas: cambiar el ancho, 9 ms por paso frente a 32 ms con el motor (4 ms con `ColumnLayout` sin más); crear, 285 ms frente a 300 ms (60 ms). Crear sigue siendo caro por el peso de cada caja y de cada texto (ver [flex.md](flex.md#vía-rápida-layouts-de-qt)). En los ejemplos, algo más de la mitad de las cajas van por la vía rápida (96 de 173; en el panel, 60 de 72); las de `<flex>` en fila, como las de `examples/flex` (1 de 43), siguen con el motor.
- **Cajas y textos ligeros:** cada caja y cada `<Text>` crean solo las piezas que usan (`JkHover`, `JkTap`, `JkRole`, `JkTranslate`, `JkTextBox`, `JkTextLinks`; `tests/test_flex_lazy.py`). Una caja vacía pasa de ~50 a ~32 µs y un texto de ~43 a ~30 µs; las 300 tarjetas desde `.janel`, de ~425 a ~325 ms al crear y de ~9 a ~6,5 ms por paso al cambiar el ancho.
- **Trasladar filas entre `{#each}` (reto Kanban):** al quitar una fila con clave, sus componentes quedan aparcados hasta el final del cambio reactivo (`when_settled` en `reactivity/effects.py`); si otra instancia de la misma declaración crea una fila con esa clave, los adopta: reutiliza las fuentes de sus props, cambia padre, manejadores y puente, y devuelve el foco a la vista nueva. Si la lista destino se actualiza antes que la de origen, la reclama directamente. Soltar en otra columna con 20 × 200 sigue en ~12 ms (`tests/test_each_transfer.py`).
- **Arrastrar y soltar (reto Kanban):** sobre el mismo filtro de eventos (`qt_backend/events.py`): al pasar la distancia de arrastre empieza el arrastre y Qt Quick deja de seguir ese puntero; la zona bajo el puntero se busca en el orden de dibujo de Qt (antes, `childAt`, que ignora `z` y dejaba sin eventos la primera fila de una `<List>`). Con 20 columnas × 200 tarjetas, un movimiento cuesta lo mismo que un fotograma vacío (p99 7 ms frente a 6 ms), ~0,5 ms de Python ([hallazgos](../examples/challenges/kanban/HALLAZGOS.md)).
- **Tiempos recuperados:** invertir 1000 filas en un `<Scroll>` volvió a ~93 ms (~380 ms desde el motor de `<flex>`): cada fila avisaba a su contenedor al cambiar su índice, y mover una fila cambiaba el de todas las de detrás; ahora avisa el modelo, una vez por movimiento. La rejilla de 200 tarjetas de `examples/flex` volvió a 17 ms por fotograma (con la vía rápida había subido a 40, con picos de casi 3 s): dentro de una caja con el motor, también el motor, y lo que quede con layout de Qt se coloca al momento (ver [flex.md](flex.md#vía-rápida-layouts-de-qt)). 300 tarjetas dentro de un `<Scroll>`: 8,7 ms por paso al cambiar el ancho (28 ms en el último commit).

## Limitaciones conocidas

- Los objetos propios modificados en el sitio no se detectan (las listas, diccionarios y conjuntos sí): llama a `estado.notify()`.
- Sin empaquetado de aplicaciones (`.exe`, `.app`).
- Licencia sin decidir y nada publicado todavía. El nombre, JanelKit, ya está decidido y aplicado (decisión 23).

## Siguientes pasos

Todos los pendientes P0, P1 y P2 de [lanzamiento.md](lanzamiento.md) están hechos salvo dos, que dependen de decisiones o de infraestructura del autor:

1. **CI en Linux y macOS (punto 11):** la configuración está lista en `.github/workflows/ci.yml`; falta un repositorio remoto en GitHub para ejecutarla.
2. **Nombre, licencia y publicación (punto 17):** verificar `janelkit`/`janel` en PyPI, elegir licencia y publicar primero en TestPyPI.

Después: Incremento 9 (validación con usuarios externos, a partir del [tutorial](tutorial.md)).
