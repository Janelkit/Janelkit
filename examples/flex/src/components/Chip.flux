<script lang="python">
# Chip: se elige con un clic y se quita con su ✕. El ✕ está dentro del chip: su
# clic llamaría también al del chip, salvo que lo pare (event.stop()), como en la web.
from fluxui import event, prop

text = prop("")
selected = prop(False)
choose = event()
remove = event()


def quitar(event):
    event.stop()
    remove.emit()
</script>

<flex as="button" class="chip" selected={selected} label={text} on:click={choose.emit()}>
  <Text class="texto">{text}</Text>
  <flex as="button" class="quitar" label={f"Quitar {text}"} title="Quitar" on:click={quitar}>
    <Text class="x">✕</Text>
  </flex>
</flex>

<style>
.chip {
  align-items: center; gap: 4px; padding: 2px 4px 2px 10px; border-radius: 12px;
  background: var(--surface-alt); border: 1px solid var(--border); cursor: pointer;
  transition: background 120ms, border-color 120ms;
}
.chip:hover { border-color: var(--text-muted); }
.chip:selected { background: var(--primary); border-color: var(--primary); }
.chip:selected .texto, .chip:selected .x { color: var(--on-primary); }
.chip:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }
.quitar { padding: 0 6px; border-radius: 9px; justify-content: center; }
.quitar:hover { background: rgba(0, 0, 0, 0.12); }
.quitar:focus-visible { outline: 2px solid var(--primary); outline-offset: -2px; }
.x { font-size: 11px; color: var(--text-muted); }
</style>
