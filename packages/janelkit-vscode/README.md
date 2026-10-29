# JanelKit (.janel) para VS Code

Resaltado de sintaxis para los componentes `.janel` de [JanelKit](https://github.com/janelkit/janelkit), el framework de aplicaciones de escritorio con Python y Qt Quick.

Un archivo `.janel` mezcla tres lenguajes, y la extensión colorea cada uno como tal:

- **Python** en `<script lang="python">`, dentro de las `{expresiones}` y en los bloques `{#if}`, `{#each}`, `{#key}` y `{#hidden}`.
- **CSS** en `<style>`.
- **La plantilla**: etiquetas, atributos y directivas `on:`, `bind:`, `class:` y `transition:`, que se destacan.

Además añade:

- Comentarios con `<!-- -->` (Ctrl+/).
- Cierre automático de llaves, corchetes, paréntesis y comillas.
- Plegado de `<script>`, `<style>` y de los bloques `{#…}` … `{/…}`.

## Instalación

Busca **JanelKit** en la vista de extensiones de VS Code o ejecuta:

```bash
code --install-extension janelkit.janelkit-janel
```

También puedes instalarla desde el repositorio:

```bash
cd packages/janelkit-vscode
npx @vscode/vsce package
code --install-extension janelkit-janel-0.1.0.vsix
```

## Errores y diagnósticos

La extensión solo colorea: todavía no tiene autocompletado ni marca errores. Para ver los errores usa `janel dev` o `janel build`. Los muestran con archivo, línea, columna y sugerencias, y la terminal integrada de VS Code permite hacer clic en la ubicación para ir a ella.

## Requisitos

VS Code 1.80 o posterior. Para ejecutar las aplicaciones, `pip install janelkit`.

## Cambios

### 0.1.0

- Primera versión publicada: gramática de `.janel` (Python, plantilla y CSS), comentarios, cierre automático y plegado.

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).
