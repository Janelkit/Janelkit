<script lang="python">
from fluxui import prop, event
from services.notes import excerpt, when

note = prop()
active = prop(False)
chosen = event()
</script>

<Column class="card" class:active={active} on:click={lambda: chosen.emit(note["id"])}>
  <Row class="top">
    <Text class="title">{note["title"] or "Sin título"}</Text>
    <Text class="tag">{note["tag"]}</Text>
  </Row>
  <Text class="excerpt">{excerpt(note["body"]) or "Nota vacía"}</Text>
  <Text class="date">{when(note["updated"])}</Text>
</Column>

<style>
.card { padding: 12px; gap: 4px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
.active { border-color: var(--primary); border-width: 2px; }
.top { gap: 8px; }
.title { font-weight: 600; flex: 1; }
.tag { font-size: var(--font-size-sm); color: var(--primary); text-transform: uppercase; letter-spacing: 1px; }
.excerpt { color: var(--text-muted); }
.date { font-size: var(--font-size-sm); color: var(--text-muted); }
</style>
