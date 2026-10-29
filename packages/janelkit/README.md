# JanelKit

[![PyPI](https://img.shields.io/pypi/v/janelkit)](https://pypi.org/project/janelkit/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit)](https://pypi.org/project/janelkit/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**Aplicaciones de escritorio con componentes de archivo único, escritas en Python.**

Cada componente `.janel` reúne en un archivo la lógica en Python, una plantilla declarativa y reactiva, y sus estilos en CSS. JanelKit lo compila a Qt Quick (PySide6): interfaces nativas y aceleradas por GPU en Windows, macOS y Linux, sin escribir JavaScript ni QML.

```bash
pip install janelkit
janel new mi-app
cd mi-app
python main.py
```

<p align="center">
  <img src="https://raw.githubusercontent.com/janelkit/janelkit/main/docs/img/tutorial.png" alt="La aplicación del tutorial: una lista de la compra con un campo, un botón Añadir y tres productos con casillas" width="360">
</p>

## Un componente

```html
<script lang="python">
from janelkit import state, computed

todos = state([{"id": 1, "title": "Probar JanelKit", "done": False}])
draft = state("")

@computed
def pending():
    return sum(not t["done"] for t in todos.value)

def add():
    todos.value.append({"id": len(todos.value) + 1, "title": draft.value, "done": False})
    draft.value = ""
</script>

<Window title="Tareas" width={480} height={400}>
  <Column class="page">
    <Text class="title">{pending} pendientes</Text>
    <Row class="new">
      <TextField bind:value={draft} on:submit={add} placeholder="Nueva tarea" flex={1} />
      <Button variant="primary" on:click={add}>Añadir</Button>
    </Row>
    {#each todos as todo (todo["id"])}
      <Checkbox checked={todo["done"]} on:change={todo["done"] = event}>{todo["title"]}</Checkbox>
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

Cuando cambia un `state`, solo se recalcula lo que lo leyó, y solo se actualiza en pantalla lo afectado. Las listas y diccionarios son reactivos también al modificarlos en el sitio (`append`, `todo["done"] = True`).

## Por qué JanelKit

- **Python de principio a fin.** La lógica, los manejadores y las expresiones de la plantilla son Python: tus módulos, tus bibliotecas y tus pruebas de siempre.
- **Rendimiento nativo.** Qt Quick dibuja; JanelKit solo avisa de lo que cambió. Una aplicación mediana arranca en menos de 300 ms y responde en menos de 70 ms. Una `<List>` virtualizada crea 10 000 filas en unos 40 ms.
- **Errores que ayudan.** Cada error indica archivo, línea y columna, con sugerencias («¿quisiste decir `on:click`?»), también los que vienen de Qt o de la ejecución.
- **Recarga al guardar.** `janel dev` recarga la vista y conserva el estado de los componentes cuyo script no cambió.
- **Probado a fondo.** Una suite extensa de pruebas que la CI ejecuta en Windows, Linux y macOS, y cinco aplicaciones grandes de validación (chat, panel en tiempo real, Kanban, hoja de cálculo y gestor de proyectos) construidas sin tocar el framework.
- **API pública explícita.** Qué es público está documentado y protegido por pruebas, con una [política de versiones](https://github.com/janelkit/janelkit/blob/main/docs/api.md#política-de-versiones) clara.

## Qué incluye

| Área | Contenido |
|---|---|
| **Reactividad** | `state`, `@computed`, `effect`, `batch`, colecciones reactivas, `persisted` (estado que se recuerda entre sesiones), deshacer y rehacer (`History`) |
| **Plantilla** | `{expr}` con formato (`{cpu:.1f}`), `on:evento`, `bind:value`, `class:x={cond}`, `{#if}`, `{#each}` con claves, `{#key}`, `{#hidden}`, transiciones |
| **Componentes** | Importados como módulos Python, `prop()` con tipos, `event()`, slots, `on_mount`/`on_destroy`, `ref`, `provide`/`inject` |
| **Asincronía** | Manejadores `async def`, `@task` con estados de carga y error, `background()` para trabajo bloqueante, temporizadores; todo se cancela al desmontar |
| **Disposición y estilos** | Flexbox de CSS (`<flex>`, `Column`, `Row`), posición, pseudo-clases y selectores, tokens `var(--primary)`, temas claro y oscuro intercambiables en caliente |
| **Controles** | Texto (también Markdown), botones, campos, casillas, `Select`, `Switch`, `Slider`, `RadioGroup`, `Tabs`, `Image`, `ProgressBar`, `<List>` virtualizada, `<Video>`, arrastrar y soltar |
| **Ventanas y navegación** | Varias ventanas, pilas de páginas, secciones que conservan su estado, `before_leave` para cambios sin guardar, Alt+← |
| **Accesibilidad** | Navegación con teclado, foco visible, nombres accesibles, derecha a izquierda |
| **Interoperabilidad** | Importa un `.qml` propio como si fuera un componente |
| **Pruebas** | `janelkit.inspect`: monta sin ventana, busca elementos, simula clics y teclas, lee el estado |

## Comandos

| Comando | Qué hace |
|---|---|
| `janel new <nombre>` | Crea un proyecto con `main.py` y `src/App.janel`. |
| `janel dev [carpeta]` | Ejecuta la aplicación y la recarga al guardar. |
| `janel build [carpeta]` | Valida todos los componentes y guarda el QML generado. |
| `janel compile <archivo>` | Muestra el QML generado de un componente. |
| `janel parse <archivo>` | Muestra el árbol sintáctico o los errores con línea y columna. |

## Probar una aplicación

```python
from janelkit import inspect

def test_add(tmp_path):
    with inspect.mount("src/App.janel") as app:
        app.find(placeholder="Nueva tarea").type("Pan")
        app.find(text="Añadir").click()
        assert app.find(text="1 pendientes")
```

## Ecosistema

| Paquete | Qué añade |
|---|---|
| [`janelkit-i18n`](https://pypi.org/project/janelkit-i18n/) | Traducciones, plurales, formatos según el idioma y cambio de idioma en caliente. |
| [`janelkit-desktop`](https://pypi.org/project/janelkit-desktop/) | Diálogos nativos, portapapeles y notificaciones del sistema. |
| [Resaltado para VS Code](https://github.com/janelkit/janelkit/tree/main/packages/janelkit-vscode) | Sintaxis de `.janel`: Python, plantilla y CSS. |

## Requisitos

- Python 3.10 o posterior.
- PySide6 6.8 o posterior, salvo la 6.12.0 (se instala solo).
- Windows, macOS o Linux.

## Estado

JanelKit está en **alfa** (serie 0.x). Lo público está [documentado](https://github.com/janelkit/janelkit/blob/main/docs/api.md). Una versión de parche nunca lo rompe; una versión menor puede hacerlo, pero cada cambio se anuncia en las [notas de la versión](https://github.com/janelkit/janelkit/blob/main/docs/cambios.md) con cómo migrar.

## Documentación

- [Tutorial](https://github.com/janelkit/janelkit/blob/main/docs/tutorial.md): una aplicación completa paso a paso. **Empieza aquí.**
- [El lenguaje `.janel`](https://github.com/janelkit/janelkit/blob/main/docs/lenguaje.md): expresiones, bloques, componentes y elementos.
- [Estilos y disposición](https://github.com/janelkit/janelkit/blob/main/docs/estilos.md): CSS soportado, flexbox, tokens y temas.
- [Desarrollo](https://github.com/janelkit/janelkit/blob/main/docs/desarrollo.md): `janel dev`, `janel build`, errores y editor.
- [API pública](https://github.com/janelkit/janelkit/blob/main/docs/api.md) y [cambios entre versiones](https://github.com/janelkit/janelkit/blob/main/docs/cambios.md).
- [Crear un ejecutable](https://github.com/janelkit/janelkit/blob/main/docs/empaquetado.md) con PyInstaller.
- [Ejemplos](https://github.com/janelkit/janelkit/tree/main/apps/examples): contador, tareas, notas, explorador de archivos, cliente de una API, idiomas, vídeo…

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE). JanelKit usa [PySide6](https://pypi.org/project/PySide6/) (Qt for Python), que se distribuye bajo LGPL-3.0: si empaquetas tu aplicación con Qt incluido, revisa sus [condiciones](https://doc.qt.io/qtforpython-6/licenses.html).
