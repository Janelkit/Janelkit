<script lang="python">
# Notas rápidas: la lista es un persisted, así que añadir, marcar o quitar se guarda solo.
from fluxui import state
from services.prefs import notas

borrador = state("")


def anadir():
    texto = borrador.value.strip()
    if texto:
        siguiente = max((n["id"] for n in notas.value), default=0) + 1
        notas.value.append({"id": siguiente, "texto": texto, "hecha": False})
        borrador.value = ""


def tecla(event):
    if event.key == "Escape":  # descarta lo escrito
        borrador.value = ""
</script>

<Column class="notas">
  <Row class="nueva">
    <TextField label="Nueva nota" bind:value={borrador} placeholder="Escribe y pulsa Intro…" flex={1}
               on:submit={anadir} on:keydown={tecla} />
    <Button variant="primary" on:click={anadir} enabled={bool(borrador.strip())}>Añadir</Button>
  </Row>
  {#each notas as nota (nota["id"])}
    <Row class="nota">
      <Checkbox label={nota["texto"]} checked={nota["hecha"]} on:change={nota["hecha"] = event} />
      <Text class="texto" class:hecha={nota["hecha"]}>{nota["texto"]}</Text>
      <Button variant="ghost" on:click={notas.remove(nota)}>Quitar</Button>
    </Row>
  {:else}
    <Text class="vacio">No hay notas. Las que escribas seguirán aquí al volver a abrir.</Text>
  {/each}
</Column>

<style>
.notas { gap: 6px; }
.nueva { gap: 8px; align-items: center; }
.nota { gap: 8px; align-items: center; }
.texto { flex: 1; }  /* hereda el tamaño de letra elegido; el texto de un Checkbox, no */
.hecha { color: var(--text-muted); }
.vacio { color: var(--text-muted); }
</style>
