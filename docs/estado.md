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

La **primera demostración** de la sección 11 se cumple: tras instalar el paquete, `flux new ejemplo` crea un proyecto con `main.py`, y `python main.py` abre `App.flux` con un contador reactivo y un campo de texto.

## Incrementos

| Incremento | Estado | Notas |
|---|---|---|
| 0 — Validación técnica | ✅ | Ver `NOTES.md` del spike. |
| 1 — Formato SFC y compilador mínimo | ✅ | `flux parse`. Errores con archivo, línea, columna, fragmento y sugerencia. |
| 2 — Primera interfaz compilada | ✅ | `Window`, `Column`, `Row`, `Text`, `Button`, `TextField` (+ `Checkbox`). Errores de Qt remitidos al `.flux`. |
| 3 — Estado, interpolación y eventos | ✅ | `state`, `@computed`, `{expr}`, `on:click`, actualización por binding, instancias independientes, liberación al desmontar. |
| 4 — Entrada de datos y control de flujo | 🟡 parcial | Hecho: `bind:value`, `bind:checked`, `{#if}/{:else if}/{:else}` (por visibilidad), `@computed`. Falta: `{#each}` con claves y modelos Qt, desmontaje real de ramas, ejemplo `todo`. |
| 5 — Composición | ⏳ | — |
| 6 — Estilos y temas (cierre MVP) | 🟡 base | Subconjunto CSS con clases y advertencias. Faltan bordes, radios, tokens y temas. |
| 7 — Experiencia de desarrollo | ⏳ | `flux new` mínimo ya existe; faltan `flux dev`, `flux build`, recarga. |
| 8–9 | ⏳ | — |

## Decisiones provisionales tomadas al implementar

Cierran de forma **provisional** puntos del «Registro de decisiones pendientes» del plan para poder avanzar; pueden revisarse.

1. **Una sola raíz** en la plantilla. Si no es `<Window>`, se envuelve en una ventana.
2. **Reactividad por seguimiento automático de lecturas** (no hay declaración estática de dependencias).
3. **Expresiones de plantilla = expresiones Python evaluadas en Python**, con desenvolvido automático de `state`/`computed`. QML solo lee propiedades del puente; nunca se traduce Python a JavaScript.
4. **Puente por instancia:** clase `QObject` generada por componente con una propiedad notificable por binding, expuesta como propiedad de contexto `fx` en un `QQmlContext` propio de la instancia.
5. **Contrato de `run(entry, argv=None) -> int`:** resuelve la ruta respecto al archivo, añade su carpeta a `sys.path`, imprime diagnósticos en stderr y devuelve 1 ante errores de compilación o del script; reutiliza la `QGuiApplication` existente si la hay. Estilo Qt Quick por defecto: Fusion (respetando `QT_QUICK_CONTROLS_STYLE`).
6. **`main.py` generado:** `raise SystemExit(run(...))` en lugar de `run(...)` a secas, para que el código de salida llegue al sistema. Es la única diferencia con el ejemplo de la sección 14.3.
7. **Versiones mínimas declaradas:** Python ≥ 3.10, PySide6 ≥ 6.6. Solo se ha probado 3.13 + 6.12.
8. **Plantillas como `*.tmpl`** dentro del paquete (`dot-` → `.`) para que pip no las importe ni compile.
9. `FLUXUI_EXIT_AFTER_MS`: variable de entorno para pruebas de humo que cierra la aplicación tras N ms.

## Limitaciones conocidas

- `{#each}` no compila todavía.
- `{#if}` oculta en lugar de desmontar: los elementos de ramas inactivas existen (sin coste reactivo extra, pero ocupan memoria).
- No hay composición de componentes `.flux` (imports, props, eventos propios).
- Las mutaciones in situ de listas/diccionarios en un `state` no se detectan.
- `class` dinámico no está soportado.
- Los nombres usados dentro de `lambda` en la plantilla no se desenvuelven.
- El trabajo en hilos o asíncrono no tiene integración: todo debe ocurrir en el hilo de Qt.
- Sin `flux dev` (recarga) ni `flux build`.
- Nombre `fluxui`/`flux` y extensión `.flux` siguen siendo provisionales y **no se han verificado en PyPI**. No se ha publicado nada.
- Licencia sin decidir.

## Siguientes pasos recomendados

1. Incremento 4: `{#each}` con clave (adaptador `QAbstractListModel` + `Repeater`/`ListView`), desmontaje real de `{#if}` con `Loader`, y `examples/todo`.
2. Inicializar el repositorio git y CI con la matriz Python/PySide6.
3. Probar en Linux y macOS.
