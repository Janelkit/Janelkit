<script lang="python">
# Pestaña Ajustes de un proyecto: nombre, color y descripción (un borrador que se guarda
# como un solo cambio), archivar o recuperar, y borrar con confirmación.
from fluxui import before_leave, dialogs, event, inject, prop, state
from services.datos import COLORES, cuenta

pid = prop("")
borrado = event()
datos = inject("datos")
proyecto = datos.proyecto(pid.value)
nombre = state(proyecto["nombre"])
descripcion = state(proyecto["descripcion"])
color = state(proyecto["color"])


def cambios():
    return {k: v for k, v in {"nombre": nombre.value.strip() or proyecto["nombre"], "descripcion": descripcion.value,
                              "color": color.value}.items() if proyecto[k] != v}


@before_leave
async def salir():
    return not cambios() or await dialogs.confirm("Los ajustes del proyecto tienen cambios sin guardar. ¿Salir sin guardarlos?")


def guardar():
    datos.editar_proyecto(pid.value, **cambios())


def descartar():
    nombre.value, descripcion.value, color.value = proyecto["nombre"], proyecto["descripcion"], proyecto["color"]


async def borrar():
    total = datos.resumen(proyecto)["total"]
    if await dialogs.confirm(f"¿Borrar «{proyecto['nombre']}» y sus {cuenta(total, 'tarjeta')}? Se puede deshacer con Ctrl+Z."):
        borrado.emit()
        datos.borrar_proyecto(pid.value)
</script>

<flex class="ajustes">
  <flex class="panel general">
    <Text class="panel-titulo">General</Text>
    <Text class="rotulo">Nombre</Text>
    <TextField bind:value={nombre} label="Nombre del proyecto" />
    <Text class="rotulo">Descripción</Text>
    <TextArea class="descripcion" bind:value={descripcion} label="Descripción del proyecto" />
    <Text class="rotulo">Color</Text>
    <flex class="colores">
      {#each COLORES as c (c)}
        <flex as="button" class="muestra" class:elegido={color == c} style={{"background": c}} label={f"Color {c}"}
              on:click={color = c} />
      {/each}
    </flex>
    <flex class="botones">
      {#if cambios()}<Text class="aviso">Cambios sin guardar</Text>{/if}
      <Spacer />
      <Button text="Descartar" enabled={bool(cambios())} on:click={descartar()} />
      <Button text="Guardar" variant="primary" enabled={bool(cambios())} on:click={guardar()} />
    </flex>
  </flex>
  <flex class="lateral">
    <flex class="panel">
      <Text class="panel-titulo">Resumen</Text>
      <flex class="dato-fila"><Text>Tarjetas</Text><Spacer /><Text class="cifra">{datos.resumen(proyecto)["total"]}</Text></flex>
      <flex class="dato-fila"><Text>Columnas</Text><Spacer /><Text class="cifra">{len(proyecto["columnas"])}</Text></flex>
      <flex class="dato-fila"><Text>Miembros</Text><Spacer /><Text class="cifra">{len(proyecto["miembros"])}</Text></flex>
      <flex class="dato-fila"><Text>Hecho</Text><Spacer /><Text class="cifra">{f"{round(datos.resumen(proyecto)['progreso'] * 100)} %"}</Text></flex>
      <ProgressBar value={datos.resumen(proyecto)["progreso"]} max={1} />
    </flex>
    <flex class="panel peligro">
      <Text class="panel-titulo">Zona peligrosa</Text>
      <Text class="explica">{"Recuperarlo lo devuelve a la lista de proyectos activos." if proyecto["archivado"] else "Archivarlo lo quita de la lista sin borrar nada."}</Text>
      <Button text={"Recuperar" if proyecto["archivado"] else "Archivar"}
              on:click={datos.editar_proyecto(pid, archivado=not proyecto["archivado"])} />
      <Text class="explica">Borrarlo quita también todas sus tarjetas (se puede deshacer con Ctrl+Z).</Text>
      <Button class="borrar" text="Borrar proyecto" on:click={borrar()} />
    </flex>
  </flex>
</flex>

<style>
.ajustes { flex: 1; flex-wrap: wrap; gap: 20px; padding: 20px 24px; overflow: auto; align-items: start; align-content: start; }
.panel { direction: column; gap: 8px; padding: 18px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; }
.general { flex: 1 1 360px; }
.lateral { direction: column; flex: 0 1 300px; min-width: 260px; gap: 16px; }
.panel-titulo { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
.rotulo { color: var(--text-muted); font-size: 12px; margin-top: 6px; }
.descripcion { height: 120px; }
.colores { gap: 8px; }
.muestra { width: 28px; height: 28px; border-radius: 14px; cursor: pointer; border: 3px solid transparent; }
.muestra:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.elegido { border-color: var(--text); }
.botones { gap: 8px; margin-top: 12px; align-items: center; }
.aviso { color: var(--warning); font-size: 12px; font-weight: 600; }
.dato-fila { align-items: center; }
.cifra { font-weight: 700; }
.peligro { border-color: var(--danger); }
.explica { color: var(--text-muted); font-size: 12px; }
.borrar { color: var(--danger); }
</style>
