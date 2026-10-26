# Flujo de desarrollo

## Comandos

| Comando | Qué hace |
|---|---|
| `flux new <nombre> [--path DIR]` | Crea un proyecto con `main.py`, `src/App.flux`, un componente de ejemplo, `pyproject.toml`, README y `.gitignore`. No sobrescribe carpetas con contenido. |
| `python main.py` | Forma canónica de ejecutar la aplicación. No depende de ningún otro comando. |
| `flux dev [carpeta]` | Ejecuta `main.py` en modo desarrollo y recarga al guardar. |
| `flux build [carpeta] [-o DIR]` | Compila **todos** los `.flux` del proyecto (también los que aún no se usan) y escribe el QML generado en `build/qml`. Termina con código 1 si hay errores. |
| `flux compile <archivo.flux> [-o salida.qml]` | Muestra el QML generado para un componente. |
| `flux parse <archivo.flux>` | Muestra el AST o los errores con línea y columna. |

Todos admiten `--help`.

## `flux dev`

- **Al guardar un `.flux`** (el raíz o cualquier componente importado), la vista se recompila y se vuelve a montar en el mismo proceso, conservando la posición y el tamaño de la ventana. Es una **recarga completa**: el estado de la interfaz vuelve a su valor inicial.
- **Si el archivo tiene errores**, se muestran en la consola y en una ventana de errores, con archivo, línea y columna; la última versión correcta sigue abierta. Al corregir y guardar, la ventana de errores se cierra sola.
- **Al guardar un `.py` del proyecto** (por ejemplo, `src/services/…`), se reinicia el proceso: los módulos Python no se pueden recargar de forma fiable dentro del mismo proceso.
- Si la aplicación termina con error, `flux dev` espera a que cambie un `.py` y vuelve a arrancarla. Si se cierra la ventana normalmente, `flux dev` termina.

`flux dev` lanza `python main.py` con la variable `FLUXUI_DEV=1`; lo que funciona con `flux dev` funciona igual con `python main.py`.

La recarga con conservación selectiva del estado (HMR) queda para más adelante: primero hay que validar el ciclo de vida de los componentes con uso real.

## `flux build`

Valida el proyecto completo y deja el QML generado para inspeccionarlo. **No crea un ejecutable**: instalar FluxUI con `pip` y empaquetar una aplicación para distribuirla son pasos distintos; el empaquetado está previsto para una fase posterior.

## Errores en tiempo de ejecución

Las excepciones dentro de bindings, manejadores o regiones `{#each}`/`{#if}` no cierran la aplicación: se registran en el logger `fluxui` con archivo y línea del `.flux`. Para ver además el traceback completo:

```python
import logging
logging.getLogger("fluxui").setLevel(logging.DEBUG)
```

## Resaltado en el editor

`editors/vscode/` contiene una extensión mínima de VS Code con resaltado de sintaxis para `.flux` (Python en `<script>` y en las expresiones, CSS en `<style>`). Ver su [README](../editors/vscode/README.md) para instalarla. Todavía no hay autocompletado ni diagnósticos en el editor.

## Pruebas automáticas de una aplicación

`FLUXUI_EXIT_AFTER_MS=500 python main.py` cierra la aplicación tras 500 ms: útil para pruebas de humo en CI. Con `QT_QPA_PLATFORM=offscreen` no se muestra ninguna ventana.
