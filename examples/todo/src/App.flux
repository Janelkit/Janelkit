<script lang="python">
from itertools import count as counter

from fluxui import state, computed

_ids = counter(4)

todos = state([
    {"id": 1, "title": "Leer el plan de FluxUI", "done": True},
    {"id": 2, "title": "Probar {#each} con claves", "done": False},
    {"id": 3, "title": "Escribir una app de verdad", "done": False},
])
draft = state("")
query = state("")
filter_mode = state("todas")  # "todas" | "pendientes" | "hechas"

FILTERS = ["todas", "pendientes", "hechas"]


@computed
def visible():
    q = query.value.strip().lower()
    mode = filter_mode.value
    return [
        t for t in todos.value
        if (mode == "todas" or (mode == "hechas") == t["done"]) and q in t["title"].lower()
    ]


@computed
def pending():
    return sum(not t["done"] for t in todos.value)


def add():
    title = draft.value.strip()
    if title:
        todos.value = [*todos.value, {"id": next(_ids), "title": title, "done": False}]
        draft.value = ""


def toggle(todo_id, done):
    todos.value = [{**t, "done": done} if t["id"] == todo_id else t for t in todos.value]


def remove(todo_id):
    todos.value = [t for t in todos.value if t["id"] != todo_id]


def set_filter(mode):
    filter_mode.value = mode


def clear_done():
    todos.value = [t for t in todos.value if not t["done"]]
</script>

<Window title="Tareas" width={520} height={560} minWidth={380}>
  <Column class="page">
    <Text class="title">Tareas</Text>

    <Row class="new">
      <TextField bind:value={draft} on:submit={add} placeholder="¿Qué hay que hacer?" flex={1} />
      <Button variant="primary" on:click={add} enabled={bool(draft.strip())}>Añadir</Button>
    </Row>

    <Row class="filters">
      <TextField bind:value={query} placeholder="Buscar…" flex={1} />
      {#each FILTERS as mode (mode)}
        <Button variant={"primary" if mode == filter_mode else "ghost"} on:click={lambda: set_filter(mode)}>
          {mode.capitalize()}
        </Button>
      {/each}
    </Row>

    <Scroll class="list">
      {#each visible as todo (todo["id"])}
        <Row class="item">
          <Checkbox checked={todo["done"]} on:change={lambda done: toggle(todo["id"], done)} flex={1}>
            {todo["title"]}
          </Checkbox>
          <Button variant="ghost" on:click={lambda: remove(todo["id"])}>Eliminar</Button>
        </Row>
      {:else}
        <Column class="empty">
          {#if todos}
            <Text class="muted">Ninguna tarea coincide con el filtro.</Text>
          {:else}
            <Text class="muted">No hay tareas. Escribe una arriba y pulsa Intro.</Text>
          {/if}
        </Column>
      {/each}
    </Scroll>

    <Row class="footer">
      <Text class="muted">{pending} pendiente{"" if pending == 1 else "s"} de {len(todos)}</Text>
      <Spacer />
      <Button variant="ghost" on:click={clear_done} enabled={pending < len(todos)}>Borrar hechas</Button>
    </Row>
  </Column>
</Window>

<style>
.page { padding: 24px; gap: 14px; }
.title { font-size: var(--font-size-xl); font-weight: 600; }
.new, .filters { gap: 8px; }
.list { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 6px; gap: 2px; }
.item { padding: 4px 8px; gap: 8px; border-radius: var(--radius-sm); }
.empty { padding: 24px; align-items: center; }
.muted { color: var(--text-muted); }
.footer { gap: 8px; }
</style>
