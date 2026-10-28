# JanelKit

> **Prealfa.** La API es provisional. No está publicado en PyPI.

Componentes de archivo único (`.janel`) para aplicaciones de escritorio: **Python** para la lógica, una plantilla declarativa reactiva y **Qt Quick** (PySide6) para el renderizado. Sin JavaScript ni QML escrito a mano.

```html
<script lang="python">
from janelkit import state, computed
from components.TodoItem import TodoItem   # otro .janel (ver apps/examples/todo-components)

todos = state([{"id": 1, "title": "Probar JanelKit", "done": False}])
draft = state("")

@computed
def pending():
    return sum(not t["done"] for t in todos.value)

def add():
    todos.value = [*todos.value, {"id": len(todos.value) + 1, "title": draft.value, "done": False}]
    draft.value = ""

def remove(todo_id):
    todos.value = [t for t in todos.value if t["id"] != todo_id]
</script>

<Window title="Tareas" width={480} height={400}>
  <Column class="page">
    <Text class="title">{pending} pendientes</Text>
    <Row class="new">
      <TextField bind:value={draft} on:submit={add} placeholder="Nueva tarea" flex={1} />
      <Button variant="primary" on:click={add}>Añadir</Button>
    </Row>
    {#each todos as todo (todo["id"])}
      <TodoItem todo={todo} on:removed={remove} />
    {:else}
      <Text>No hay tareas.</Text>
    {/each}
  </Column>
</Window>

<style>
.page { padding: 24px; gap: 12px; }
.title { font-size: var(--font-size-xl); font-weight: 600; }
.new { gap: 8px; }
</style>
```

## Qué incluye

- **Reactividad:** `state` (con listas y diccionarios reactivos), `@computed`, `effect`, interpolación `{expr}`, `on:evento` (también en línea: `on:click={n += 1}`), `bind:value`/`bind:checked`. Solo se actualiza lo que depende de lo que cambió.
- **Control de flujo:** `{#if}`/`{:else if}`/`{:else}` (desmonta de verdad), `{#each items as item, i (clave)}` con `{:else}`, `{#key}`.
- **Componentes:** imports Python de otros `.janel`, `prop()` y `event()`, slots, estado local por instancia, ciclo de vida (`on_mount`, `on_destroy`), referencias a elementos (`ref`), contexto (`provide`/`inject`), componentes recursivos.
- **Asincronía:** manejadores `async def`, `@task` con estados de carga y error, `background()` para trabajo bloqueante; todo se cancela al desmontar.
- **Estilos:** subconjunto CSS (colores, tipografía, espaciado, bordes, radios, alineación, `flex`), clases condicionales `class:x={cond}`, tokens `var(--primary)` y temas claro/oscuro intercambiables en caliente.
- **Diagnósticos:** errores con archivo, línea, columna y sugerencias («¿quisiste decir…?»), también para errores de Qt y de ejecución.
- **Herramientas:** `janel new`, `janel dev` (recarga al guardar), `janel build`, `janel compile`, `janel parse`.

## Organización del repositorio

Un solo repositorio con el núcleo y los paquetes del ecosistema, que se publican por separado:

| Carpeta | Paquete | Qué es |
|---|---|---|
| [`packages/janelkit`](packages/janelkit/README.md) | `janelkit` | El núcleo: lenguaje `.janel`, compilador, reactividad, runtime, disposición, controles, ventanas, navegación, temas, tareas, `persisted`, `janelkit.inspect` y el comando `janel`. |
| [`packages/janelkit-i18n`](packages/janelkit-i18n/README.md) | `janelkit-i18n` | Traducciones (`t`, `i18n`): catálogos, plurales y formatos según el idioma. |
| [`packages/janelkit-desktop`](packages/janelkit-desktop/README.md) | `janelkit-desktop` | Diálogos nativos, portapapeles y notificaciones (`dialogs`, `clipboard`, `notify`). |
| [`packages/janelkit-vscode`](packages/janelkit-vscode/README.md) | — | Resaltado de `.janel` para VS Code. |
| `apps/examples` | — | Ejemplos pequeños, uno por tema. |
| `apps/challenges` | — | Aplicaciones grandes que ponen a prueba el framework (chat, gestor, kanban, panel). |

Las extensiones solo usan la API pública del núcleo (`tests/test_boundaries.py` lo comprueba), y el núcleo no las importa. Qué va en cada sitio: [docs/alcance.md](docs/alcance.md).

## Probarlo (desde el repositorio)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
python -m pip install -r requirements-dev.txt   # los tres paquetes editables y las herramientas, con versiones probadas
python -m pytest                                # toda la suite; o un paquete: python -m pytest packages/janelkit

janel new mi-app
cd mi-app
python main.py                  # o: janel dev
```

Ejemplos incluidos (cada uno se ejecuta con `python apps/examples/<nombre>/main.py`):

| Ejemplo | Muestra |
|---|---|
| `counter` | estado, `computed`, eventos, `{#if}` |
| `todo` | lista con claves, filtro, búsqueda, estado vacío |
| `todo-components` | la misma app dividida en `TodoList` y `TodoItem` con props y eventos |
| `notes` | barra lateral, formulario, tarjetas, `class:`, `{#key}` y cambio de tema |
| `books` | búsqueda en una API real sin bloquear la ventana: `@task`, `background`, cargando y errores |
| `compra` | la aplicación del [tutorial](docs/tutorial.md): componentes, slot, guardado en segundo plano y pruebas |
| `idiomas` | cambio de idioma en caliente, plurales, formatos según el idioma y árabe (derecha a izquierda), con `janelkit-i18n` |
| `files` | explorador de archivos: `<List>` virtualizada, slots, `provide`/`inject`, `ref`, atajos, diálogos (`janelkit-desktop`) y vista previa en segundo plano |

## Comandos

| Comando | Qué hace |
|---|---|
| `janel new <nombre> [--path DIR]` | Crea un proyecto con `main.py` y `src/App.janel`. No sobrescribe carpetas con contenido. |
| `python main.py` | Forma canónica de ejecutar una aplicación. |
| `janel dev [carpeta]` | Ejecuta la app y la recarga al guardar (`.janel`) o la reinicia (`.py`). |
| `janel build [carpeta]` | Valida todos los componentes y guarda el QML generado en `build/qml`. No crea ejecutables. |
| `janel compile <archivo.janel>` | Muestra el QML generado. |
| `janel parse <archivo.janel>` | Muestra el AST o los errores con línea y columna. |

## Cómo funciona

```
App.janel ─► parser (AST con ubicaciones) ─► IR ─┬─► QML generado (controles del módulo interno Janel)
  + componentes importados                       └─► runtime Python: script por instancia, bindings reactivos
                                                          │
                     puente QObject por plantilla (propiedad notificable por binding)
                     regiones {#each}/{#if}: Repeater + modelo Python con reconciliación por clave
```

Las expresiones de la plantilla se evalúan en **Python**; cuando cambia un `state`, solo se recalculan los bindings que lo leyeron y solo se notifica a QML la propiedad afectada.

## Documentación

- [docs/tutorial.md](docs/tutorial.md) — **empieza aquí**: una aplicación completa paso a paso (código en `apps/examples/compra`).
- [docs/lenguaje.md](docs/lenguaje.md) — formato `.janel`, expresiones, bloques, componentes y elementos.
- [docs/estilos.md](docs/estilos.md) — CSS soportado, disposición (flex), tokens y temas.
- [docs/desarrollo.md](docs/desarrollo.md) — `janel dev`, `janel build`, errores y editor.
- [docs/api.md](docs/api.md) — qué es API pública y política de versiones.
- [docs/cambios.md](docs/cambios.md) — cambios entre versiones y cómo migrar.
- [docs/empaquetado.md](docs/empaquetado.md) — crear un ejecutable con PyInstaller.
- [docs/estado.md](docs/estado.md) — avance frente al plan, decisiones provisionales, rendimiento y limitaciones.
- [docs/alcance.md](docs/alcance.md) — qué es el framework, qué queda fuera y proyectos paralelos.
- [docs/lanzamiento.md](docs/lanzamiento.md) — pendientes priorizados antes de la primera versión pública.
- [spikes/qt_bridge_counter/NOTES.md](spikes/qt_bridge_counter/NOTES.md) — validación técnica del puente Python ↔ Qt Quick.

## Desarrollo de JanelKit

```bash
python -m pytest                 # pruebas (Qt en modo offscreen)
python tools/check_wheel.py      # construye wheel/sdist, instala en un venv limpio y prueba janel new + python main.py
```
