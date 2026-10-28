<script lang="python">
# Una tarjeta del tablero de un proyecto (viene del reto 3). Se arrastra (draggable) y acepta que le suelten otra encima:
# se coloca delante (o detrás, si baja en su misma columna). Doble clic o Intro abren
# el detalle; clic derecho, el menú. Cada acción del menú tiene su tecla (ver tecla()).
# `abierta` es estado local de la tarjeta: sobrevive al arrastre, también a otra columna
# (la fila se traslada entre las dos <List>, con su estado y su foco).
from fluxui import inject, on_destroy, on_mount, prop, ref, state

t = prop({})
atenuada = prop(False)
tablero = inject("tablero")
datos = inject("datos")  # el responsable es un id del directorio de personas
ui = inject("ui")  # estado compartido de la ventana: detalle, menú y tarjeta nueva que enfocar
abierta = state(False)
caja = ref()


@on_mount
def enfocar_si_toca():
    ui.tarjetas[t.value["id"]] = caja
    # Una tarjeta recién creada (Ctrl+D) o pedida por un enlace toma el foco al aparecer.
    if ui.enfocar.peek() == t.value["id"]:
        ui.enfocar.value = None
        caja.focus()


on_destroy(lambda: ui.tarjetas.pop(t.value["id"], None))


def soltar(event):
    tipo, origen = event.data
    if tipo != "tarjeta":
        return  # una columna: la recoloca la columna
    event.stop()
    if origen == t.value["id"]:
        return
    col, i = tablero.donde(t.value["id"])
    tablero.mover(origen, col["id"], i)  # al bajar en su columna, queda detrás: sacarla corre las demás


def tecla(event):
    k, ident = event.key, t.value["id"]
    if k == "Enter":
        ui.abrir(ident)
    elif k == "Delete":
        tablero.borrar(ident)
    elif k.lower() == "d" and event.ctrl:
        ui.enfocar.value = tablero.duplicar(ident)
    elif event.alt and k in ("ArrowLeft", "ArrowRight"):
        tablero.mover_a(ident, -1 if k == "ArrowLeft" else 1)
    elif event.alt and k in ("ArrowUp", "ArrowDown"):
        tablero.subir(ident, -1 if k == "ArrowUp" else 1)
    elif k == "ContextMenu" or (k == "F10" and event.shift):
        ui.menu_en(ident, None, None, caja)
    else:
        return
    event.prevent()
</script>

<flex as="listitem" class="tarjeta" class:atenuada={atenuada} tabindex={0} ref={caja} label={t["titulo"]}
      draggable on:dragstart={event.data = ("tarjeta", t["id"])} on:drop={soltar}
      on:dblclick={ui.abrir(t["id"])} on:contextmenu={ui.menu_en(t["id"], event.window_x, event.window_y, caja)}
      on:keydown={tecla}>
  {#if t["etiquetas"]}
    <flex class="etiquetas">
      {#each t["etiquetas"] as e (e)}
        <flex class="etiqueta" style={{"background": tablero.etiquetas.get(e, "#868e96")}}><Text>{e}</Text></flex>
      {/each}
    </flex>
  {/if}
  <Text class="titulo">{t["titulo"]}</Text>
  <flex class="pie">
    {#if t["responsable"]}<Text class="persona">{datos.nombre(t["responsable"]).split(" ")[0]}</Text>{/if}
    {#if t["fecha"]}<Text class="fecha">{t["fecha"]}</Text>{/if}
    <flex as="button" class="mas" label={("Ocultar" if abierta else "Ver") + f" descripción de {t['titulo']}"} expanded={abierta}
          on:click={abierta = not abierta}>
      <Text>{"▾" if abierta else "▸"}</Text>
    </flex>
  </flex>
  {#if abierta}
    <Text class="descripcion">{t["descripcion"] or "Sin descripción."}</Text>
  {/if}
</flex>

<style>
.tarjeta {
  direction: column; gap: 6px; padding: 8px 10px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  cursor: grab; transition: opacity 120ms;
}
.tarjeta:focus-visible { outline: 2px solid var(--primary); }
.tarjeta:dragging { opacity: 0.35; }
.tarjeta:drag-over { border-color: var(--primary); border-top-width: 3px; }
.atenuada { opacity: 0.3; }
.etiquetas { gap: 4px; flex-wrap: wrap; }
.etiqueta { padding: 1px 6px; border-radius: 8px; color: #ffffff; font-size: 11px; }
.titulo { font-weight: 600; }
.pie { gap: 8px; align-items: center; color: var(--text-muted); font-size: 12px; }
.persona { padding: 1px 6px; border-radius: 8px; background: var(--surface-alt); }
.mas { margin-left: auto; padding: 0 6px; border-radius: 4px; cursor: pointer; }
.descripcion { color: var(--text-muted); font-size: 12px; }
</style>
