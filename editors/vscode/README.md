# Resaltado de `.flux` para VS Code

Extensión mínima (solo gramática) para los componentes de FluxUI:

- Python en `<script lang="python">` y dentro de `{expresiones}` y bloques `{#if}`, `{#each}`, `{#key}`.
- CSS en `<style>`.
- Directivas `on:`, `bind:` y `class:` destacadas.

## Instalarla localmente

Copia esta carpeta en la carpeta de extensiones de VS Code y reinicia el editor:

| Sistema | Carpeta |
|---|---|
| Windows | `%USERPROFILE%\.vscode\extensions\fluxui-flux` |
| macOS / Linux | `~/.vscode/extensions/fluxui-flux` |

O empaquétala con `npx @vscode/vsce package` e instala el `.vsix` resultante con
`code --install-extension fluxui-flux-0.0.1.vsix`.

No hay autocompletado ni diagnósticos en el editor todavía: para ver errores usa
`flux build` o `flux dev`, que los muestran con archivo, línea y columna.
