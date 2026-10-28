<script lang="python">
# Reto 3: tablero Kanban. Ver ../README.md y ../HALLAZGOS.md.
# KANBAN_FILE: archivo JSON del tablero (por defecto, tablero.json junto a la app).
# KANBAN_DEMO=20x200: tablero generado de 20 columnas con 200 tarjetas, sin archivo
# (pruebas y mediciones).
import os
from pathlib import Path

from fluxui import provide, state
from components.Columna import Columna
from components.Detalle import Detalle
from components.MenuContextual import MenuContextual
from services.interfaz import Interfaz
from services.tablero import ETIQUETAS, PERSONAS, Tablero, ejemplo

if os.environ.get("KANBAN_DEMO"):
    cols, cards = (int(n) for n in os.environ["KANBAN_DEMO"].split("x"))
    tablero = Tablero(None, ejemplo(cols, cards))
else:
    tablero = Tablero(Path(os.environ.get("KANBAN_FILE", Path(__file__).parent.parent / "tablero.json")))

texto = state("")
etiqueta = state("")
persona = state("")
ui = Interfaz(texto, etiqueta, persona)
provide("tablero", tablero)
provide("ui", ui)

columnas = tablero.columnas
detalle = ui.detalle
menu = ui.menu
deshacer = tablero.puede_deshacer
rehacer = tablero.puede_rehacer
ETIQUETAS_OPC = [{"label": "Todas las etiquetas", "value": ""}] + [{"label": e, "value": e} for e in ETIQUETAS]
PERSONAS_OPC = [{"label": "Todas las personas", "value": ""}] + [{"label": p, "value": p} for p in PERSONAS]


def opciones_menu(ident):
    col, _ = tablero.donde(ident)
    destinos = [{"label": f"Mover a «{c['nombre']}»", "valor": ("mover", c["id"]), "tecla": "Alt+← / Alt+→"}
                for c in columnas.value if c is not col]
    return destinos + [
        {"label": "Abrir", "valor": ("abrir", None), "tecla": "Intro"},
        {"label": "Duplicar", "valor": ("duplicar", None), "tecla": "Ctrl+D"},
        {"label": "Borrar", "valor": ("borrar", None), "tecla": "Supr"},
    ]


def elegir(valor):
    ident = menu.value["id"]
    accion, col = valor
    ui.cerrar_menu()
    if accion == "mover":
        tablero.mover(ident, col, 0)  # la tarjeta se traslada con el foco que le devolvió el menú
    elif accion == "abrir":
        ui.abrir(ident)
    elif accion == "duplicar":
        ui.enfocar.value = tablero.duplicar(ident)
    else:
        tablero.borrar(ident)


def limpiar_filtros():
    texto.set("")
    etiqueta.set("")
    persona.set("")
</script>

<Window title="Kanban" width={1200} height={760} minWidth={640} minHeight={420}>
  <Shortcut keys="Ctrl+Z" on:activate={tablero.deshacer()} />
  <Shortcut keys="Ctrl+Y" on:activate={tablero.rehacer()} />
  <Shortcut keys="Ctrl+Shift+Z" on:activate={tablero.rehacer()} />
  <flex class="app">
    <flex class="barra">
      <Text class="marca">Kanban</Text>
      <TextField class="buscar" bind:value={texto} placeholder="Buscar tarjetas…" label="Buscar" />
      <Select options={ETIQUETAS_OPC} bind:value={etiqueta} label="Filtrar por etiqueta" />
      <Select options={PERSONAS_OPC} bind:value={persona} label="Filtrar por persona" />
      {#if texto or etiqueta or persona}
        <Button text="Quitar filtros" variant="ghost" on:click={limpiar_filtros()} />
      {/if}
      <Spacer />
      <Button text="Deshacer" enabled={bool(deshacer)} label={f"Deshacer {deshacer} (Ctrl+Z)"} on:click={tablero.deshacer()} />
      <Button text="Rehacer" enabled={bool(rehacer)} label={f"Rehacer {rehacer} (Ctrl+Y)"} on:click={tablero.rehacer()} />
      <Button text="+ Columna" variant="primary" on:click={tablero.nueva_columna()} />
    </flex>
    <flex class="cuerpo">
      <flex class="tablero" label="Tablero">
        {#each columnas as c (c["id"])}
          <Columna columna={c} />
        {/each}
      </flex>
      {#if detalle}
        {#key detalle}
          <Detalle ident={detalle} on:cerrar={detalle = None} />
        {/key}
      {/if}
    </flex>
  </flex>
  {#if menu}
    <MenuContextual opciones={opciones_menu(menu["id"])} x={menu["x"] if menu["x"] is not None else 240}
                    y={menu["y"] if menu["y"] is not None else 120}
                    on:elegir={elegir} on:cerrar={ui.cerrar_menu()} />
  {/if}
</Window>

<style>
.app { direction: column; flex: 1; background: var(--bg); }
.barra { gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--surface); }
.marca { font-size: 16px; font-weight: 700; margin-right: 8px; }
.buscar { width: 240px; }
.cuerpo { flex: 1; }
.tablero { flex: 1; gap: 12px; padding: 12px; overflow: auto; align-items: stretch; }
</style>
