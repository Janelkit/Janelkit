<script lang="python">
from fluxui import prop, event, state, computed
from components.NoteCard import NoteCard
from services.notes import matches

notes = prop()
selected = prop(None)
chosen = event()
created = event()

# La búsqueda es estado local de la barra lateral: el resto de la app no la necesita.
query = state("")


@computed
def found():
    return [n for n in notes.value if matches(n, query.value)]
</script>

<Column class="sidebar">
  <Row class="head">
    <Text class="brand">Notas</Text>
    <Spacer />
    <Button variant="primary" on:click={created.emit}>Nueva</Button>
  </Row>
  <TextField bind:value={query} placeholder="Buscar en las notas" />
  <Scroll class="list">
    {#each found as note (note["id"])}
      <NoteCard note={note} active={note["id"] == selected} on:chosen={chosen.emit} />
    {:else}
      <Text class="empty">{"Sin resultados para «" + query + "»" if query else "Todavía no hay notas"}</Text>
    {/each}
  </Scroll>
  <Text class="count">{len(found)} de {len(notes)} notas</Text>
</Column>

<style>
.sidebar { width: 280px; padding: 16px; gap: 12px; background: var(--surface-alt); align-self: stretch; }
.head { align-items: center; }
.brand { font-size: var(--font-size-lg); font-weight: 700; }
.list { gap: 8px; }
.empty { padding: 16px; color: var(--text-muted); text-align: center; }
.count { font-size: var(--font-size-sm); color: var(--text-muted); }
</style>
