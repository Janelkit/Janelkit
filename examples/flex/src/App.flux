<script lang="python">
# Catálogo de elementos construidos con <flex> (fase 1: rejilla y barra de herramientas).
# Ver docs/flex.md. Ningún tamaño ni columna se calcula en Python.
import os

from fluxui import state
from components.Barra import Barra
from components.Tarjeta import Tarjeta

TAGS = ["diseño", "datos", "red", "texto"]
cards = [
    {"id": i, "title": f"Tarjeta {i + 1}", "tag": TAGS[i % 4],
     "body": "Texto de ejemplo que se corta en varias líneas cuando la tarjeta es estrecha." if i % 3 == 0 else "Corto."}
    for i in range(int(os.environ.get("FLEX_CARDS", "8")))  # FLEX_CARDS: para bench.py
]
last = state("—")


def on_action(name):
    last.set(name)
</script>

<Window title="flex: catálogo" width={900} height={600}>
  <flex direction="column" class="pagina">
    <Barra title="Catálogo de flex" on:action={on_action} />
    <flex class="contenido">
      <Text class="estado">Última acción: {last}</Text>
      <flex id="rejilla" class="rejilla">
        {#each cards as card (card["id"])}
          <Tarjeta class="celda" title={card["title"]} tag={card["tag"]} body={card["body"]} />
        {/each}
      </flex>
    </flex>
  </flex>
</Window>

<style>
.pagina { background: var(--bg); }
.contenido { direction: column; gap: 12px; padding: 16px; flex: 1; overflow: auto; }
.estado { color: var(--text-muted); }
/* Rejilla: cada celda parte de 200 px y crece; las que no caben saltan de línea. */
.rejilla { flex-wrap: wrap; gap: 12px; align-items: start; }
.celda { flex: 1 1 200px; }
</style>
