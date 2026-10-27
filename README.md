# FluxUI

> **Prealfa.** Nombre, extensión y API son provisionales. No está publicado en PyPI.

Componentes de archivo único (`.flux`) para aplicaciones de escritorio: **Python** para la lógica, una plantilla declarativa reactiva y **Qt Quick** (PySide6) para el renderizado. Sin JavaScript ni QML escrito a mano.

```html
<script lang="python">
from fluxui import state, computed
from components.TodoItem import TodoItem   # otro .flux (ver examples/todo-components)

todos = state([{"id": 1, "title": "Probar FluxUI", "done": False}])
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
- **Componentes:** imports Python de otros `.flux`, `prop()` y `event()`, slots, estado local por instancia, ciclo de vida (`on_mount`, `on_destroy`), referencias a elementos (`ref`), contexto (`provide`/`inject`), componentes recursivos.
- **Asincronía:** manejadores `async def`, `@task` con estados de carga y error, `background()` para trabajo bloqueante; todo se cancela al desmontar.
- **Estilos:** subconjunto CSS (colores, tipografía, espaciado, bordes, radios, alineación, `flex`), clases condicionales `class:x={cond}`, tokens `var(--primary)` y temas claro/oscuro intercambiables en caliente.
- **Diagnósticos:** errores con archivo, línea, columna y sugerencias («¿quisiste decir…?»), también para errores de Qt y de ejecución.
- **Herramientas:** `flux new`, `flux dev` (recarga al guardar), `flux build`, `flux compile`, `flux parse`; resaltado para VS Code.

## Probarlo (desde el repositorio)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
python -m pip install -e ".[dev]"

flux new mi-app
cd mi-app
python main.py                  # o: flux dev
```

Ejemplos incluidos (cada uno se ejecuta con `python examples/<nombre>/main.py`):

| Ejemplo | Muestra |
|---|---|
| `counter` | estado, `computed`, eventos, `{#if}` |
| `todo` | lista con claves, filtro, búsqueda, estado vacío |
| `todo-components` | la misma app dividida en `TodoList` y `TodoItem` con props y eventos |
| `notes` | barra lateral, formulario, tarjetas, `class:`, `{#key}` y cambio de tema |
| `books` | búsqueda en una API real sin bloquear la ventana: `@task`, `background`, cargando y errores |
| `compra` | la aplicación del [tutorial](docs/tutorial.md): componentes, slot, guardado en segundo plano y pruebas |
| `idiomas` | cambio de idioma en caliente, plurales, formatos según el idioma y árabe (derecha a izquierda) |
| `files` | explorador de archivos: `<List>` virtualizada, slots, `provide`/`inject`, `ref`, atajos, diálogos y vista previa en segundo plano |

## Comandos

| Comando | Qué hace |
|---|---|
| `flux new <nombre> [--path DIR]` | Crea un proyecto con `main.py` y `src/App.flux`. No sobrescribe carpetas con contenido. |
| `python main.py` | Forma canónica de ejecutar una aplicación. |
| `flux dev [carpeta]` | Ejecuta la app y la recarga al guardar (`.flux`) o la reinicia (`.py`). |
| `flux build [carpeta]` | Valida todos los componentes y guarda el QML generado en `build/qml`. No crea ejecutables. |
| `flux compile <archivo.flux>` | Muestra el QML generado. |
| `flux parse <archivo.flux>` | Muestra el AST o los errores con línea y columna. |

## Cómo funciona

```
App.flux ─► parser (AST con ubicaciones) ─► IR ─┬─► QML generado (controles del módulo interno Flux)
  + componentes importados                       └─► runtime Python: script por instancia, bindings reactivos
                                                          │
                     puente QObject por plantilla (propiedad notificable por binding)
                     regiones {#each}/{#if}: Repeater + modelo Python con reconciliación por clave
```

Las expresiones de la plantilla se evalúan en **Python**; cuando cambia un `state`, solo se recalculan los bindings que lo leyeron y solo se notifica a QML la propiedad afectada.

## Documentación

- [docs/tutorial.md](docs/tutorial.md) — **empieza aquí**: una aplicación completa paso a paso (código en `examples/compra`).
- [docs/lenguaje.md](docs/lenguaje.md) — formato `.flux`, expresiones, bloques, componentes y elementos.
- [docs/estilos.md](docs/estilos.md) — CSS soportado, disposición (flex), tokens y temas.
- [docs/desarrollo.md](docs/desarrollo.md) — `flux dev`, `flux build`, errores y editor.
- [docs/api.md](docs/api.md) — qué es API pública y política de versiones.
- [docs/cambios.md](docs/cambios.md) — cambios entre versiones y cómo migrar.
- [docs/empaquetado.md](docs/empaquetado.md) — crear un ejecutable con PyInstaller.
- [docs/estado.md](docs/estado.md) — avance frente al plan, decisiones provisionales, rendimiento y limitaciones.
- [docs/alcance.md](docs/alcance.md) — qué es el framework, qué queda fuera y proyectos paralelos.
- [docs/lanzamiento.md](docs/lanzamiento.md) — pendientes priorizados antes de la primera versión pública.
- [spikes/qt_bridge_counter/NOTES.md](spikes/qt_bridge_counter/NOTES.md) — validación técnica del puente Python ↔ Qt Quick.

## Desarrollo de FluxUI

```bash
python -m pytest                 # pruebas (Qt en modo offscreen)
python tools/check_wheel.py      # construye wheel/sdist, instala en un venv limpio y prueba flux new + python main.py
```
