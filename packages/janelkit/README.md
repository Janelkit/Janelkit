# JanelKit

[![PyPI](https://img.shields.io/pypi/v/janelkit)](https://pypi.org/project/janelkit/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit)](https://pypi.org/project/janelkit/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**A new window for Python.** Desktop apps written in Python, one file per component, rendered with Qt Quick and tested without a screen.

[Leer en español](https://github.com/janelkit/janelkit/blob/main/README.es.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/janelkit/janelkit/main/docs/img/kanban.png" alt="A Kanban board built with JanelKit: four columns of cards with colored tags, people and dates, a search field and filters" width="820">
  <br>
  <sub>A Kanban board built with JanelKit: 842 lines of <code>.janel</code> and Python, and 12 tests that run without a screen. <a href="https://github.com/janelkit/janelkit/tree/main/apps/challenges/kanban">Source</a></sub>
</p>

```bash
pip install janelkit
janel new my-app
cd my-app
python main.py
```

## One file per component

A `.janel` file holds a component's logic, template and styles. Everything between `{` and `}` is Python, and the interface follows your state: when a value changes, only what depends on it is updated.

```html
<script lang="python">
from janelkit import state, computed

todos = state([{"id": 1, "title": "Try JanelKit", "done": False}])
draft = state("")

@computed
def pending():
    return sum(not t["done"] for t in todos.value)

def add():
    todos.value.append({"id": len(todos.value) + 1, "title": draft.value, "done": False})
    draft.value = ""
</script>

<window title="Tasks" width={420} height={360}>
  <column class="page">
    <text class="title">{pending} pending</text>
    <row class="new">
      <textfield bind:value={draft} on:submit={add} placeholder="New task" flex={1} />
      <button variant="primary" on:click={add}>Add</button>
    </row>
    {#each todos as todo (todo["id"])}
      <checkbox checked={todo["done"]} on:change={todo["done"] = event}>{todo["title"]}</checkbox>
    {/each}
  </column>
</window>

<style>
.page { padding: 24px; gap: 12px; }
.title { font-size: var(--font-size-xl); font-weight: 600; }
.new { gap: 8px; }
</style>
```

<p align="center"><img src="https://raw.githubusercontent.com/janelkit/janelkit/main/docs/img/example.png" alt="The window this component opens: '2 pending', a text field with an Add button and three tasks with checkboxes" width="320"></p>

Lowercase tags come with JanelKit (`<text>`, `<button>`, `<column>`). Capitalized tags are components you import like any Python module (`from components.TodoItem import TodoItem`).

## Every app can be tested the way it is used

`janelkit.inspect` mounts the app without a window and drives it like a user. This is the test for the component above:

```python
from janelkit.inspect import mount

def test_add_a_task():
    with mount("src/App.janel") as app:
        app.find(placeholder="New task").type("Buy milk").submit()
        app.find("checkbox", text="Buy milk").check()
        assert "1 pending" in app.texts()
```

There is no display, browser or driver to set up: it runs wherever `pytest` runs. A large app is tested the same way. These lines are from the [tests of the Kanban board](https://github.com/janelkit/janelkit/blob/main/apps/challenges/tests/test_challenge_kanban.py) above (its labels are in Spanish):

```python
app.find("Tarjeta", label="Beta").drag_to(app.find("Columna", label="Hecho"))  # press, move, release
app.find("Tarjeta", label="Gamma").right_click()                               # opens the context menu
app.find("flex", label="Mover a «Hecho»").click()
app.find("Tarjeta", label="Beta").key("Enter")                                 # opens the card
assert app.find("Detalle").visible
app.screenshot("board.png")
```

- **It finds what a user sees.** `find` looks an element up by tag, text, label, placeholder or id, only among the visible ones, and fails unless exactly one matches. `app.texts()` returns the visible text in reading order.
- **It acts through the real paths.** `click`, `type`, `check`, `choose`, `slide`, `drag_to` and `key` emit the same signals a user would, so they go through your handlers and your `bind:`. Acting on a disabled control fails, as it would for a user.
- **It waits for async work.** `app.wait(until=...)` lets tasks and timers run until a condition holds.
- **It reaches the whole app.** Windows opened with `open_window`, system dialogs, the state of the script (`app.get("todos")`) and screenshots of the app or of one element.
- **It serves tools as well as tests.** `janel build` and `check_file` report every error without running the app. With `inspect`, a script or a coding agent can write a component, check it, use it and look at the result, all without a display.

JanelKit's own suite, more than 650 tests, runs this way on Windows, macOS and Linux. [Reference](https://github.com/janelkit/janelkit/blob/main/docs/api.md#janelkitinspect-pruebas-y-herramientas)

## Why JanelKit

- **Tests without a screen.** Every app can be mounted headless and driven like a user, from the first component to a full board with drag and drop. [See above](#every-app-can-be-tested-the-way-it-is-used).
- **One language for your app.** Logic, template expressions and tests are Python, and the compiler generates the QML. The door stays open: a `.qml` file of your own is imported like any other component when you want something from Qt Quick that JanelKit doesn't have. [Your own QML elements](https://github.com/janelkit/janelkit/blob/main/docs/lenguaje.md#elementos-propios-en-qml)
- **Errors that point at your code.** `janel build` checks every component before anything runs. Errors, including those raised by Qt or at run time, come back with the `.janel` file, line and column, and a suggestion when there is one.
- **Save and see it.** `janel dev` reloads the window when you save a `.janel` and restarts the app when you save a `.py`. Either way, every component whose script didn't change keeps its state.
- **Errors as you type.** The VS Code extension underlines the compiler's errors in the `.janel` you are editing. `janel lsp` gives the same to any editor that speaks the Language Server Protocol.
- **Your libraries in the same process.** A NumPy array, a pandas table or a model's result goes straight to the interface, with no server in between and nothing to serialize.
- **A small core.** Navigation, shared data, native dialogs and translations are separate packages that you add when you need them.

## Is it for you?

**A good fit:** internal tools, data and lab tools, and any desktop app whose logic is already in Python and that you want covered by tests.

**Not covered today:**

- Web and mobile apps: JanelKit is for the desktop.
- Installers and code signing: there is a [PyInstaller recipe](https://github.com/janelkit/janelkit/blob/main/docs/desarrollo.md#distribuir-un-ejecutable-con-pyinstaller); MSI, DMG and AppImage are up to you.
- Computer vision and video beyond the basics: `<video>` shows frames pushed from any thread, and anything more specialized will be a separate package. It is not being worked on for now. [Figures and limits](https://github.com/janelkit/janelkit/blob/main/docs/patrones.md#qué-latencia-esperar-y-para-qué-no-sirve)
- English documentation: the guides and the compiler messages are in Spanish for now.

## Learn

The guides are in Spanish:

| Guide | What's in it |
|---|---|
| [Tutorial](https://github.com/janelkit/janelkit/blob/main/docs/tutorial.md) | **Start here:** a complete app, step by step |
| [Language](https://github.com/janelkit/janelkit/blob/main/docs/lenguaje.md) | The `.janel` format: expressions, blocks, components, built-in elements |
| [Styles](https://github.com/janelkit/janelkit/blob/main/docs/estilos.md) | Supported CSS, flex layout, tokens, light and dark themes |
| [Real-time patterns](https://github.com/janelkit/janelkit/blob/main/docs/patrones.md) | Cameras, models and data acquisition: loops, frames, latency |
| [Development](https://github.com/janelkit/janelkit/blob/main/docs/desarrollo.md) | `janel dev`, `janel build`, errors, tests, executables |
| [Public API](https://github.com/janelkit/janelkit/blob/main/docs/api.md) · [Changes](https://github.com/janelkit/janelkit/blob/main/docs/cambios.md) | What is public, the versioning policy and how to migrate |

[Examples](https://github.com/janelkit/janelkit/tree/main/apps/examples): small apps, one topic each. [Challenges](https://github.com/janelkit/janelkit/tree/main/apps/challenges): large apps that put the framework to the test, including a chat client, a project manager, the Kanban board above, a 10 000 × 26 spreadsheet and a live system monitor.

## Packages

`pip install janelkit` is all a one-screen app needs. Add the rest when you need it:

| You need | Install |
|---|---|
| Several screens: page stacks, a sidebar with sections | [`janelkit-router`](https://pypi.org/project/janelkit-router/) |
| Data shared by several views or windows, remembered between sessions | [`janelkit-store`](https://pypi.org/project/janelkit-store/) |
| Native file and system dialogs, clipboard | [`janelkit-desktop`](https://pypi.org/project/janelkit-desktop/) |
| Translations | [`janelkit-i18n`](https://pypi.org/project/janelkit-i18n/) |
| `.janel` syntax highlighting and compiler errors in VS Code | [`janelkit-vscode`](https://github.com/janelkit/janelkit/tree/main/packages/janelkit-vscode) |

## Requirements

- Python 3.10 or later.
- PySide6-Essentials 6.8 or later, except 6.12.0: Qt's essential modules, without the Add-ons. It is installed automatically.
- Windows, macOS or Linux.

## Status

**Alpha (0.2).** The public API is documented in [api.md](https://github.com/janelkit/janelkit/blob/main/docs/api.md) and protected by tests. Each series (0.1, 0.2…) may break it, always with migration notes in [cambios.md](https://github.com/janelkit/janelkit/blob/main/docs/cambios.md) and `janel migrate`.

**What is there:**

- The `.janel` language and its compiler, with errors located in your file.
- Reactive state (`state`, `computed`, `effect`), components with props, events and slots, async tasks and timers.
- Twenty-one built-in elements, flex layout, scoped CSS, light and dark themes, several windows.
- `janel dev`, which keeps the state when a `.janel` is reloaded and when a change in a `.py` restarts the app.
- `janelkit.inspect` for tests, and the compiler's errors in the editor through `janel lsp` and the VS Code extension.
- Four packages built on the public API: router, store, desktop and i18n.

**What comes first:**

1. **Python tooling inside a `.janel`.** The editor shows the compiler's errors, but not yet what Python tooling gives you in any other file: completion and type checking for the Python in `<script>` and in template expressions.
2. **State that lives in your `.py` files across a restart.** `janel dev` restores the state of components. A `state` kept in a service, or a store without `persist=`, still starts over when a `.py` changes. [What is kept](https://github.com/janelkit/janelkit/blob/main/docs/desarrollo.md#janel-dev)

## License

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE). JanelKit uses [PySide6](https://pypi.org/project/PySide6/) (Qt for Python), distributed under LGPL-3.0: if you ship an app that bundles Qt, review its [terms](https://doc.qt.io/qtforpython-6/licenses.html).
