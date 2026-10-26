# Estado del desarrollo

Referencia: [`FluxUI_Plan_Desarrollo_v0.1.md`](../FluxUI_Plan_Desarrollo_v0.1.md). Actualizado: 26 de octubre de 2026.

**Entorno verificado:** Windows 11, Python 3.13.9, PySide6 6.12.0. Linux y macOS **no se han probado**.

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
| 7 — Experiencia de desarrollo | ✅ (sin HMR) | `flux dev`, `flux build`, plantilla mejorada, resaltado para VS Code |
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
3. **Expresiones de plantilla = expresiones Python evaluadas en Python**, con desenvolvido automático de `state`/`computed`/props. QML solo lee propiedades del puente; nunca se traduce Python a JavaScript. Los nombres libres se resuelven al evaluarse (cadena: variables de bloque → script → builtins), así que también funcionan dentro de `lambda`. Consecuencia: el estado se modifica desde funciones del script, no con `lambda: x.set(...)` en la plantilla.
4. **Puente por instancia de plantilla:** una clase `QObject` generada por plantilla (componente o fragmento de `{#each}`/`{#if}`/`{#key}`) con una propiedad notificable por binding, expuesta como `fx` (propiedad de contexto en la raíz; rol del modelo en cada fila).
5. **Regiones dinámicas = `Repeater` + modelo Python** (`QAbstractListModel` de puentes). La reconciliación por clave ocurre en Python y emite insertar/mover/eliminar filas; Qt conserva los delegados movidos. `{#if}` usa un modelo de 0 o 1 filas por rama, así que **desmonta** de verdad.
6. **Componentes = imports Python** (`from components.X import X`), resueltos estáticamente por el compilador. El script se reescribe (sin ejecutarse) para quitar esos imports e inyectar los componentes.
7. **Props y eventos declarados en el script** (`nombre = prop(defecto)`, `nombre = event()`), detectados estáticamente para validar los usos en el padre. Props de solo lectura; los hijos comunican cambios con eventos.
8. **Estilos sobre controles propios:** el compilador genera tipos de un módulo QML interno (`fluxui/qml/Flux`, distribuido en el wheel) basados en Qt Quick Controls *Basic* y Qt Quick Layouts. `Column`/`Row` reproducen el comportamiento de flex (sin repartir el espacio sobrante). Estilo Qt Quick por defecto: *Basic* (respetando `QT_QUICK_CONTROLS_STYLE`).
9. **Tokens de tema** en un `QQmlPropertyMap` global (`fxtheme`), sincronizado con `fluxui.theme`; `var(--x)` se compila a `fxtheme.x`.
10. **Clases condicionales** con `Binding on <prop> { when }` de QML: al desactivarse, la propiedad recupera su valor anterior.
11. **`flux dev`:** recarga completa en proceso para `.flux` y reinicio del proceso para `.py`. Sin conservación de estado.
12. **`flux build`:** validación + QML generado; no empaqueta ejecutables.
13. **Contrato de `run(entry, argv=None) -> int`:** resuelve la ruta respecto al archivo, añade su carpeta a `sys.path`, imprime diagnósticos en stderr y devuelve 1 ante errores de compilación o del script; reutiliza la `QGuiApplication` existente si la hay.
14. **`main.py` generado:** `raise SystemExit(run(...))` en lugar de `run(...)` a secas, para que el código de salida llegue al sistema.
15. **Versiones mínimas declaradas:** Python ≥ 3.10, PySide6 ≥ 6.6. Solo se ha probado 3.13 + 6.12.
16. **Plantillas como `*.tmpl`** dentro del paquete (`dot-` → `.`) para que pip no las importe ni compile.

## Rendimiento medido (indicativo)

Windows 11, offscreen, lista de filas con casilla, texto y botón:

| Operación | 100 filas | 1000 filas |
|---|---|---|
| Crear la lista completa | 70 ms | 414 ms |
| Insertar una fila en medio | 1 ms | 10 ms |
| Editar una fila | 1 ms | 3 ms |
| Invertir el orden | 1 ms | 106 ms |
| Vaciar | 1 ms | 94 ms |

Las filas se crean todas (no hay virtualización): para miles de elementos hará falta una lista virtualizada basada en `ListView`.

## Limitaciones conocidas

- Las mutaciones in situ de listas/diccionarios en un `state` no se detectan: hay que asignar un valor nuevo.
- `class` dinámico (`class={expr}`) no está soportado; usa `class:nombre={cond}`.
- Los componentes no admiten contenido entre etiquetas (slots), ni `class`/`id` en la etiqueta del componente.
- `TextArea` no tiene `on:input` (Qt no distingue sus cambios del usuario de los programáticos); usa `bind:value`.
- No hay lista virtualizada para colecciones muy grandes (ver rendimiento).
- `flux dev` reinicia el estado en cada recarga (sin HMR).
- El trabajo en hilos o asíncrono no tiene integración: todo debe ocurrir en el hilo de Qt.
- Sin empaquetado de aplicaciones (`.exe`, `.app`).
- Nombre `fluxui`/`flux` y extensión `.flux` siguen siendo provisionales y **no se han verificado en PyPI**. No se ha publicado nada.
- Licencia sin decidir.

## Siguientes pasos recomendados (Incremento 8)

> La priorización completa de lo pendiente antes del lanzamiento está en [lanzamiento.md](lanzamiento.md); el alcance del framework frente a proyectos paralelos, en [alcance.md](alcance.md).

1. Inicializar el repositorio git y CI con la matriz Python/PySide6 (y Linux/macOS).
2. Probar en Linux y macOS (fuentes, escalado, estilo Basic).
3. Verificar nombres en PyPI, elegir licencia y publicar en TestPyPI.
4. Lista virtualizada (`ListView`) para colecciones grandes y medición sistemática.
5. Tutorial de inicio para evaluadores externos (Incremento 9).
