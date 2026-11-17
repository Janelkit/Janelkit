# JanelKit (.janel) para VS Code

Resaltado de sintaxis y errores del compilador para los componentes `.janel` de [JanelKit](https://github.com/janelkit/janelkit), el framework de aplicaciones de escritorio con Python y Qt Quick.

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
code --install-extension janelkit-janel-0.2.0.vsix
```

## Errores mientras escribes

La extensión subraya los errores y avisos del compilador en su línea y columna y los lista en el panel de problemas, con la sugerencia cuando la hay. Son los mismos que dan `janel dev` y `janel build`.

- Se comprueba el texto del editor, guardado o no, y no se ejecuta el script.
- Un error en un componente importado aparece en la línea que lo importa, con el archivo y la línea donde está. Los componentes importados se leen del disco: al guardar cualquier archivo se vuelven a comprobar todos los `.janel` abiertos.
- No hay autocompletado ni comprobación de tipos del Python de `<script>`: es lo siguiente.

Los errores los calcula `janel lsp`, un comando de `janelkit` 0.2.1 o posterior. La extensión lo lanza con el Python del proyecto, que busca en este orden:

1. El ajuste `janelkit.pythonPath`.
2. `.venv` o `venv` en la carpeta del proyecto.
3. El intérprete por defecto de la extensión de Python (`python.defaultInterpreterPath`).
4. `python` (`python3` en Linux y macOS).

Si ese Python no tiene `janelkit`, la extensión lo avisa una vez y sigue coloreando. El canal de salida «JanelKit» muestra qué comando se lanzó y lo que respondió.

| Ajuste o comando | Qué hace |
|---|---|
| `janelkit.diagnostics` | `false` desactiva la comprobación de errores. Por defecto, `true`. |
| `janelkit.pythonPath` | El intérprete de Python con `janelkit` instalado. |
| «JanelKit: reiniciar la comprobación de errores» | Vuelve a lanzar `janel lsp`, por ejemplo tras instalar `janelkit` o cambiar de entorno. |

## Requisitos

VS Code 1.80 o posterior. Para los errores y para ejecutar las aplicaciones, `pip install janelkit`.

## Cambios

### 0.2.0

- Los errores y avisos del compilador en el editor, mientras escribes. Necesita `janelkit` 0.2.1 o posterior. Ajustes `janelkit.diagnostics` y `janelkit.pythonPath`; comando para reiniciar la comprobación.

### 0.1.0

- Primera versión publicada: gramática de `.janel` (Python, plantilla y CSS), comentarios, cierre automático y plegado.

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).


## Local
cd packages/janelkit-vscode
npx @vscode/vsce package          # crea janelkit-janel-0.2.0.vsix (necesita Node.js)
code --install-extension janelkit-janel-0.2.0.vsix