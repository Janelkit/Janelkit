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

- **Al guardar un `.flux`** (el raíz o cualquier componente importado), la vista se recompila y se vuelve a montar en el mismo proceso, conservando la posición y el tamaño de la ventana y **el estado**: cada componente cuyo script no cambió recupera el valor de sus `state` (lo escrito en un formulario, la página de una lista…). Si cambiaste el script de un componente, ese componente empieza de cero y la consola lo indica:

  ```
  [flux dev] App.flux recargado en 38 ms; estado conservado en 4 componente(s); script cambiado, estado reiniciado: Contador.flux
  ```

  Cada componente se reconoce por su sitio en el árbol (qué componente es, cuántos iguales tiene delante en la plantilla de su padre y la clave de la fila de `{#each}` en la que está), así que añadir líneas o estilos no lo pierde. No se conservan el foco, la selección de texto ni las ventanas abiertas con `open_window`.
- **Si el archivo tiene errores**, se muestran en la consola y en una ventana de errores, con archivo, línea y columna; la última versión correcta sigue abierta. Al corregir y guardar, la ventana de errores se cierra sola.
- **Al guardar un `.py` o un `.qml` propio del proyecto** (por ejemplo, `src/services/…` o `src/widgets/…`), se reinicia el proceso: los módulos Python no se pueden recargar de forma fiable dentro del mismo proceso, y Qt no siempre vuelve a leer un `.qml` ya cargado.
- Si la aplicación termina con error, `flux dev` espera a que cambie un `.py` y vuelve a arrancarla. Si se cierra la ventana normalmente, `flux dev` termina.

`flux dev` lanza `python main.py` con la variable `FLUXUI_DEV=1`; lo que funciona con `flux dev` funciona igual con `python main.py`.


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

`fluxui.inspect` monta la aplicación sin ventana y la maneja como lo haría un usuario. Funciona con pytest o con cualquier otro sistema de pruebas:

```python
# tests/test_app.py
from fluxui.inspect import mount

def test_añadir_tarea():
    with mount("src/App.flux") as app:
        app.find(placeholder="¿Qué hay que hacer?").type("Comprar pan").submit()
        tarea = app.find("Checkbox", text="Comprar pan")
        tarea.check()
        assert app.get("todos")[-1]["done"] is True

def test_búsqueda_asíncrona():
    with mount("src/App.flux") as app:
        app.find(text="Buscar").click()
        app.wait(until=lambda: not app.get("resultados").loading)
        assert "Sin resultados" not in app.texts()
```

- `find` exige que haya **exactamente un** elemento que cumpla los criterios (etiqueta, `text`, `id`, `placeholder`); `find_all` devuelve todos. Solo se consideran los visibles.
- Las acciones (`click`, `type`, `check`, `choose`, `slide`, `submit`) emiten las mismas señales que el usuario: pasan por los manejadores y los `bind:` reales. Sobre un control desactivado fallan, como fallaría el usuario.
- `app.texts()` devuelve los textos visibles en orden de lectura.
- `app.wait(segundos)` o `app.wait(until=condición)` deja correr las tareas asíncronas y los temporizadores.
- Diálogos: `app.answer_dialog(ruta)` responde a un diálogo de archivo; `app.answer_dialog(True/False)`, a una confirmación.

Ver la referencia en [api.md](api.md#fluxuiinspect-pruebas-y-herramientas).

**Pruebas de humo:**

`FLUXUI_EXIT_AFTER_MS=500 python main.py` cierra la aplicación tras 500 ms: útil para pruebas de humo en CI. Con `QT_QPA_PLATFORM=offscreen` no se muestra ninguna ventana.
