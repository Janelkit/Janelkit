# Arquitectura

Cómo está organizado JanelKit por dentro: paquetes, capas del núcleo, el recorrido de un `.janel` desde el archivo hasta la pantalla, y cómo se versiona. Para usar JanelKit no hace falta leerlo; sirve para trabajar en el framework o escribir una extensión. Qué va en el núcleo y qué en el ecosistema está en [alcance.md](alcance.md).

## Paquetes del repositorio

| Paquete | Qué es | Depende de |
|---|---|---|
| `packages/janelkit` | El núcleo: lenguaje, compilador, reactividad, runtime, controles, CLI, inspección | PySide6, qasync |
| `packages/janelkit-i18n` | Traducciones: catálogos, plurales, formatos | `janelkit`, solo su API pública |
| `packages/janelkit-desktop` | Diálogos, portapapeles, notificaciones | `janelkit`, solo su API pública |
| `packages/janelkit-vscode` | Resaltado de `.janel` en VS Code | — |
| `apps/examples` | Ejemplos pequeños, uno por tema, con pruebas | `janelkit` y extensiones |
| `apps/challenges` | Aplicaciones grandes que ponen a prueba el núcleo, con pruebas | `janelkit` y extensiones |

Cada paquete tiene versión propia y se prueba por separado. Las extensiones declaran el rango del núcleo que admiten (`janelkit>=0.1,<0.3`). Dos pruebas del repositorio vigilan la frontera: `tests/test_boundaries.py` (el núcleo no importa el ecosistema y las extensiones no usan nada interno) y `tests/test_packages.py` (versiones y rangos compatibles).

## Capas del núcleo

Cada módulo de `janelkit` pertenece a una capa y solo importa de su capa o de las de abajo. Lo comprueba `tests/test_architecture.py`, que lee los imports de todos los módulos (también los que se hacen dentro de una función): un import hacia arriba o un ciclo entre áreas hace fallar la prueba. Las capas 0 y 1 no importan Qt: `import janelkit.compiler` funciona sin PySide6.

| Capa | Módulos | Qué hace |
|---|---|---|
| **0** | `reactivity`, `diagnostics`, `events` | Estado reactivo (`State`, `Computed`, `Effect`, `batch`, `Scope`, `Gate`, colecciones, props, `History`); errores con ubicación; los objetos de evento de `<flex>`. Python puro |
| **1** | `compiler` | `.janel` → AST → IR → QML, con el catálogo de elementos (`elements.py`) y el CSS (`css_parser.py`, `css.py`, `cascade.py`). Python puro |
| **2** | `runtime`, `lifecycle`, `pages`, `windows`, `tasks`, `timers`, `storage`, `locale`, `themes`, `displays` | Instancias de componentes, puente con QML, ciclo de vida, navegación, ventanas, asincronía, temporizadores, `persisted`, idioma, temas, pantallas |
| **3** | `qt_backend`, `video` | Arranque de Qt y del bucle de eventos, carga del QML, eventos de `<flex>`, motor de disposición, vídeo |
| **4** | `cli`, `inspect`, `testing`, `ext`, `janelkit` (raíz) | La CLI `janel`, la inspección para pruebas, las fixtures de pytest, la API para extensiones y lo que exporta `janelkit` |

Reglas que se siguen al mover código:

- Un módulo no se llama igual que un nombre público que exporta su paquete (por eso `themes.py` exporta `theme` y `displays.py` exporta `screens`): el submódulo taparía al objeto.
- Cuando una capa necesita algo de una de arriba, se invierte la dependencia con una interfaz en la de abajo. Ejemplo: el runtime monta `<Pages stack={…}>` sin conocer la navegación, porque `PageStack` y `Sections` implementan `lifecycle.ElementHost`.

## De un `.janel` a la pantalla

```
App.janel ──► sfc_parser ──► template_parser / script_analysis ──► AST
          ──► lowering (valida, resuelve estilos y bindings) ──► IR
          ──► qml_generator ──► QML  +  tablas del runtime (bindings, manejadores, regiones)
```

1. **Compilar** (capa 1). `sfc_parser` separa `<script>`, plantilla y `<style>` conservando las líneas. `template_parser` lee la plantilla (no es XML: admite expresiones Python entre llaves). `script_analysis` analiza el script sin ejecutarlo (qué es `state`, `prop`, `event`, qué componentes importa). `lowering` valida elementos, atributos y nombres contra el catálogo, resuelve la cascada de estilos al compilar y produce el IR. `layout_choice` decide, caja por caja, si basta un layout de Qt o hace falta el motor de `<flex>`. `qml_generator` escribe el QML y un mapa de origen (línea QML → línea del `.janel`), que usan los errores.
2. **Montar** (capa 2). `runtime/component.py` crea una instancia por componente: ejecuta el script en un módulo propio (registrado en `sys.modules` mientras vive), crea un puente QObject (`runtime/qt_bridge.py`) con una propiedad por binding, y un `Effect` por binding que recalcula su valor y lo escribe en el puente. Las regiones dinámicas (`{#if}`, `{#each}`, `{#key}`, `{#hidden}`) son modelos Qt (`runtime/list_model.py`) con un puente por fila.
3. **Dibujar** (capa 3). `qt_backend/application.py` arranca Qt y el bucle de asyncio (qasync), carga el QML generado sobre los controles de `qml/Janel/` y conecta los temas. QML nunca ejecuta lógica del usuario: solo lee propiedades del puente y le devuelve eventos.

### Reactividad y ámbitos

- Lo que lee un `Effect` o un `Computed` queda registrado; al cambiar, el efecto se vuelve a ejecutar al terminar el `batch` en curso.
- Cada instancia de componente tiene un `Scope`: lo que se crea mientras su script, un manejador o un tic se ejecutan (efectos, `computed`, temporizadores, tareas) queda en él y se libera al desmontar. El ámbito activo es una variable de contexto (`contextvars`), así que una corrutina lo conserva tras cada `await`.
- Una `Gate` (compuerta de visibilidad) aplaza los efectos de la plantilla de lo que no se ve (`{#hidden}`, otra sección, la página de debajo, una fila de `<List>` fuera de la vista). Lo del script sigue funcionando; `is_visible()` expone la compuerta como `computed` para pararlo a propósito.
- El estado reactivo solo se modifica desde el hilo de la interfaz. `background()` ejecuta en otro hilo y devuelve el valor por `await`.

## Versiones y publicación

La versión de cada paquete la calcula la CI a partir del prefijo de cada commit (`tools/versioning.py`; las reglas están en [api.md](api.md#cómo-se-calcula-la-versión)):

| Prefijo | Sube | Cuándo |
|---|---|---|
| `mayor:` | 0.#.0 | API pública nueva, algo que se rompe o se retira, un cambio de comportamiento |
| `menor:` | 0.0.# | Corrige o mejora sin añadir ni quitar API |
| `interno:`, `docs:` | nada | Reorganización, pruebas, CI, herramientas, documentación |

Un commit cuenta para los paquetes cuyos archivos toca, desde la última etiqueta de cada uno (`janelkit-v0.2.0`). La 1.0.0 se decide a mano.

Flujo: el trabajo de una versión se acumula en una rama. Al integrarla en `main`, la CI (`.github/workflows/ci.yml`) prueba cada paquete por separado. Si pasa, `.github/workflows/version.yml` escribe las versiones y los registros de cambios, crea el commit `version: …` y las etiquetas, y lanza `release.yml`, que publica en PyPI. El hook `.githooks/commit-msg` comprueba el prefijo en local.

## Herramientas

| Herramienta | Para qué |
|---|---|
| `tools/versioning.py` | `plan` (qué versión toca a cada paquete), `apply`, `check` (prefijos) |
| `tools/check_wheel.py` | Construye los wheels, los instala en un entorno limpio y prueba `janel new` + `python main.py` fuera del repositorio |
| `tools/bench.py`, `tools/bench_app.py` | Los tiempos de [rendimiento.md](rendimiento.md) |
