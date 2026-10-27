<script lang="python">
# Explorador de archivos: aplicación de validación de FluxUI.
# Carpeta inicial: la actual, o la de la variable de entorno FLUX_FILES_START.
import os
from pathlib import Path

from fluxui import state, computed, task, background, effect, provide, ref, on_mount, dialogs, theme
from services.fs import list_dir, read_preview
from components.Panel import Panel
from components.FileRow import FileRow

folder = state(str(Path(os.environ.get("FLUX_FILES_START") or Path.cwd()).resolve()))
query = state("")
sort_by = state("name")
show_hidden = state(False)
exact_sizes = state(False)
selected = state(None)  # ruta del archivo elegido
search = ref()

provide("exact_sizes", exact_sizes)  # lo lee cada FileRow con inject()

SORTS = [{"label": "Nombre", "value": "name"}, {"label": "Tamaño", "value": "size"}, {"label": "Fecha", "value": "modified"}]
SORT_KEYS = {"name": lambda e: e["name"].lower(), "size": lambda e: -e["size"], "modified": lambda e: -e["modified"]}


@task
async def listing(path, hidden):
    return await background(list_dir, path, hidden)  # leer el disco no bloquea la ventana


@task
async def preview(path):
    return await background(read_preview, path)


def reload():
    listing.run(folder.value, show_hidden.value)


effect(reload)  # se vuelve a listar al cambiar la carpeta o «Ocultos»


@computed
def visible():
    entries = listing.value or []
    q = query.value.strip().lower()
    if q:
        entries = [e for e in entries if q in e["name"].lower()]
    key = SORT_KEYS[sort_by.value]
    return sorted(entries, key=lambda e: (not e["is_dir"], key(e)))  # carpetas primero


def go_to(path):
    folder.value = str(path)
    selected.value = None
    query.value = ""


def open_entry(entry):
    if entry["is_dir"]:
        go_to(entry["path"])
    else:
        selected.value = entry["path"]
        preview.run(entry["path"])


def go_up():
    parent = Path(folder.value).parent
    if str(parent) != folder.value:
        go_to(parent)


async def choose_folder():
    path = await dialogs.choose_folder("Elegir carpeta", folder=folder.value)
    if path is not None:
        go_to(path)


@on_mount
def start():
    search.focus()
</script>

<Window title="Archivos" width={920} height={620} minWidth={640} minHeight={400}>
  <Column class="page">
    <Row class="toolbar">
      <Button on:click={go_up} enabled={str(Path(folder).parent) != folder}>↑ Subir</Button>
      <Text class="path" flex={1}>{folder}</Text>
      <Button on:click={choose_folder}>Abrir carpeta…</Button>
      <Button variant="ghost" on:click={reload()}>Actualizar</Button>
      <Button variant="ghost" on:click={theme.toggle()}>{"Tema oscuro" if theme.name == "light" else "Tema claro"}</Button>
    </Row>

    <Row class="filters">
      <TextField ref={search} bind:value={query} placeholder="Filtrar por nombre (Ctrl+F)" flex={1} />
      <Select bind:value={sort_by} options={SORTS} />
      <Switch bind:checked={show_hidden}>Ocultos</Switch>
      <Switch bind:checked={exact_sizes}>Tamaños exactos</Switch>
    </Row>

    <Row class="body" flex={1}>
      <Panel title="Archivos" subtitle={f"{len(visible)} elementos"} flex={2}>
        {#if listing.error}
          <Text class="error">No se pudo leer la carpeta: {listing.error}</Text>
        {:else if listing.loading and not listing.value}
          <ProgressBar indeterminate />
        {:else if not visible}
          <Text class="muted">{"Nada coincide con el filtro." if query else "Carpeta vacía."}</Text>
        {/if}
        <List class="list">
          {#each visible as entry (entry["path"])}
            <FileRow file={entry} selected={entry["path"] == selected} on:opened={open_entry} />
          {/each}
        </List>
      </Panel>

      <Panel title="Vista previa" subtitle={Path(selected).name if selected else ""} flex={1}>
        {#if not selected}
          <Text class="muted">Elige un archivo para verlo.</Text>
        {:else if preview.loading}
          <ProgressBar indeterminate />
        {:else if preview.error}
          <Text class="error">No se pudo leer el archivo: {preview.error}</Text>
        {:else}
          <Scroll>
            <Text class="preview">{preview.value}</Text>
          </Scroll>
        {/if}
      </Panel>
    </Row>

    <Shortcut keys="Ctrl+O" on:activate={choose_folder} />
    <Shortcut keys="F5" on:activate={reload()} />
    <Shortcut keys="Alt+Up" on:activate={go_up} />
    <Shortcut keys="Ctrl+F" on:activate={search.focus()} />
  </Column>
</Window>

<style>
.page { padding: 16px; gap: 12px; }
.toolbar, .filters { gap: 8px; align-items: center; }
.path { color: var(--text-muted); }
.body { gap: 12px; align-items: stretch; }
.list { gap: 2px; }
.muted { color: var(--text-muted); }
.error { color: var(--danger); }
.preview { font-family: monospace; font-size: var(--font-size-sm); }
</style>
