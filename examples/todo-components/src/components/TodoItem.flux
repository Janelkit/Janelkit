<script lang="python">
from fluxui import prop, event, state

# Props: datos que decide el padre (solo lectura aquí).
todo = prop()

# Eventos: lo que este componente comunica al padre.
toggled = event()
renamed = event()
removed = event()

# Estado local: cada fila tiene el suyo y no se mezcla con el de las demás.
editing = state(False)
draft = state("")


def start_edit():
    draft.value = todo.value["title"]
    editing.value = True


def save():
    title = draft.value.strip()
    if title and title != todo.value["title"]:
        renamed.emit(todo.value["id"], title)
    editing.value = False


def cancel():
    editing.value = False
</script>

<Row class="item">
  {#if editing}
    <TextField bind:value={draft} on:submit={save} flex={1} />
    <Button variant="primary" on:click={save}>Guardar</Button>
    <Button variant="ghost" on:click={cancel}>Cancelar</Button>
  {:else}
    <Checkbox checked={todo["done"]} on:change={lambda done: toggled.emit(todo["id"], done)} flex={1}>
      {todo["title"]}
    </Checkbox>
    <Button variant="ghost" on:click={start_edit}>Editar</Button>
    <Button variant="ghost" on:click={lambda: removed.emit(todo["id"])}>Eliminar</Button>
  {/if}
</Row>

<style>
.item { padding: 4px 8px; gap: 6px; background: var(--surface); border-radius: var(--radius-sm); }
</style>
