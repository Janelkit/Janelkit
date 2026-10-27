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
        # Las listas y diccionarios de un state son reactivos: se pueden modificar en el sitio.
        todos.value.append({"id": next(_ids), "title": title, "done": False})
        draft.value = ""


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
        <Button variant={"primary" if mode == filter_mode else "ghost"} on:click={filter_mode = mode}>
          {mode.capitalize()}
        </Button>
      {/each}
    </Row>

    <Scroll class="list">
      {#each visible as todo (todo["id"])}
        <Row class="item" transition:fade={150}>
          <Checkbox checked={todo["done"]} on:change={todo["done"] = event} flex={1}>
            {todo["title"]}
          </Checkbox>
          <Button variant="ghost" on:click={todos.remove(todo)}>Eliminar</Button>
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
