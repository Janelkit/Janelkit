<script lang="python">
# Una columna: cabecera (se arrastra para reordenar columnas; doble clic renombra) y
# sus tarjetas en una <List animate> (solo crea las que se ven: 200 por columna).
# Soltar una tarjeta en el hueco de la columna la pone al final.
from fluxui import inject, prop, state
from components.Tarjeta import Tarjeta
from services.tablero import coincide

columna = prop({})
tablero = inject("tablero")
ui = inject("ui")
editando = state(False)
nombre = state("")


def renombrar():
    editando.set(False)
    tablero.renombrar(columna.value["id"], nombre.value.strip())


def empezar_a_renombrar():
    nombre.set(columna.value["nombre"])
    editando.set(True)


def tecla_nombre(event):
    if event.key == "Escape":
        editando.set(False)
        event.prevent()


def soltar(event):
    tipo, ident = event.data
    col = columna.value
    if tipo == "tarjeta":
        origen, _ = tablero.donde(ident)
        fin = len(col["tarjetas"]) - (1 if origen is col else 0)
        tablero.mover(ident, col["id"], fin)
    else:
        indice = next(i for i, c in enumerate(tablero.columnas.peek()) if c is col)
        tablero.mover_columna(ident, indice)
</script>

<flex as="region" class="columna" label={columna["nombre"]} on:drop={soltar}>
  <flex class="cabecera" draggable on:dragstart={event.data = ("columna", columna["id"])}
        on:dblclick={empezar_a_renombrar()} title="Arrastra para mover la columna; doble clic para renombrar">
    {#if editando}
      <flex class="nombre-campo" on:keydown={tecla_nombre}>
        <TextField bind:value={nombre} on:submit={renombrar()} label="Nombre de la columna" flex={1} />
      </flex>
    {:else}
      <Text class="nombre">{columna["nombre"]}</Text>
      <Text class="cuenta">{len(columna["tarjetas"])}</Text>
      <flex as="button" class="accion" label={f"Borrar la columna {columna['nombre']}"}
            on:click={tablero.borrar_columna(columna["id"])}><Text>✕</Text></flex>
    {/if}
  </flex>
  <List class="tarjetas" animate>
    {#each columna["tarjetas"] as t (t["id"])}
      <Tarjeta t={t} atenuada={ui.filtro.value is not None and not coincide(t, *ui.filtro.value)} />
    {/each}
  </List>
  <flex as="button" class="nueva" label="Añadir tarjeta" on:click={ui.enfocar.set(tablero.nueva(columna["id"]))}>
    <Text>+ Añadir tarjeta</Text>
  </flex>
</flex>

<style>
.columna {
  direction: column; width: 280px; gap: 6px; padding: 8px;
  background: var(--surface-alt); border: 2px solid transparent; border-radius: 8px;
}
.columna:drag-over { border-color: var(--primary); }
.cabecera { gap: 6px; align-items: center; padding: 2px 4px; cursor: grab; }
.cabecera:dragging { opacity: 0.4; }
.nombre { font-weight: 700; flex: 1; }
.nombre-campo { flex: 1; }
.cuenta { color: var(--text-muted); font-size: 12px; }
.accion { padding: 0 6px; border-radius: 4px; color: var(--text-muted); cursor: pointer; }
.tarjetas { gap: 6px; flex: 1; }
.nueva { padding: 6px; border-radius: 6px; color: var(--text-muted); cursor: pointer; }
</style>
