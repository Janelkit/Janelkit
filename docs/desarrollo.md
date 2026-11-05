# Flujo de desarrollo

## Comandos

| Comando | Qué hace |
|---|---|
| `janel new <nombre> [--path DIR]` | Crea un proyecto con `main.py`, `src/App.janel`, un componente de ejemplo, `pyproject.toml`, README y `.gitignore`. No sobrescribe carpetas con contenido. |
| `python main.py` | Forma canónica de ejecutar la aplicación. No depende de ningún otro comando. |
| `janel dev [carpeta]` | Ejecuta `main.py` en modo desarrollo y recarga al guardar. |
| `janel build [carpeta] [-o DIR]` | Compila **todos** los `.janel` del proyecto (también los que aún no se usan) y escribe el QML generado en `build/qml`. Termina con código 1 si hay errores. |
| `janel compile <archivo.janel> [-o salida.qml]` | Muestra el QML generado para un componente. |
| `janel parse <archivo.janel>` | Muestra el AST o los errores con línea y columna. |
| `janel migrate [carpeta] [--write] [--tests]` | Actualiza un proyecto a esta versión de JanelKit. Sin `--write` solo muestra los cambios (un diff); con `--write` los aplica. Con `--tests`, también las plantillas dentro de las pruebas `.py` y `find("Text")`. Lista aparte lo que hay que revisar a mano. En 0.2: los elementos del núcleo en minúscula (`<Text>` → `<text>`, también al cerrar y en los selectores de `<style>`), sin tocar las etiquetas de componentes importados; los imports de la navegación pasan a `janelkit_router` (y se añaden `Pages`/`Sections` si la plantilla los usa). |

Todos admiten `--help`.

## `janel dev`

- **Al guardar un `.janel`** (el raíz o cualquier componente importado), la vista se recompila y se vuelve a montar en el mismo proceso, conservando la posición y el tamaño de la ventana y **el estado**: cada componente cuyo script no cambió recupera el valor de sus `state` (lo escrito en un formulario, la página de una lista…). Si cambiaste el script de un componente, ese componente empieza de cero y la consola lo indica:

  ```
  [janel dev] App.janel recargado en 38 ms; estado conservado en 4 componente(s); script cambiado, estado reiniciado: Contador.janel
  ```

  Añadir líneas o estilos no pierde el estado. No se conservan el foco, la selección de texto ni las ventanas abiertas con `open_window`.
- **Si el archivo tiene errores**, se muestran en la consola y en una ventana de errores, con archivo, línea y columna; la última versión correcta sigue abierta. Al corregir y guardar, la ventana de errores se cierra sola.
- **Al guardar un `.py` o un `.qml` propio del proyecto** (por ejemplo, `src/services/…` o `src/widgets/…`), se reinicia el proceso: los módulos Python no se pueden recargar de forma fiable dentro del mismo proceso, y Qt no siempre vuelve a leer un `.qml` ya cargado.
- Si la aplicación termina con error, `janel dev` espera a que cambie un `.py` y vuelve a arrancarla. Si se cierra la ventana normalmente, `janel dev` termina.

`janel dev` lanza `python main.py` con la variable `JANELKIT_DEV=1`; lo que funciona con `janel dev` funciona igual con `python main.py`.


## `janel build`

Valida el proyecto completo y deja el QML generado para inspeccionarlo. **No crea un ejecutable**: instalar JanelKit con `pip` y empaquetar una aplicación para distribuirla son pasos distintos (ver [Distribuir](#distribuir-un-ejecutable-con-pyinstaller)).

## Errores en tiempo de ejecución

Las excepciones dentro de bindings, manejadores o regiones `{#each}`/`{#if}` no cierran la aplicación: se registran en el logger `janelkit` con archivo y línea del `.janel`. Para ver además el traceback completo:

```python
import logging
logging.getLogger("janelkit").setLevel(logging.DEBUG)
```

## Resaltado en el editor

`packages/janelkit-vscode/` contiene una extensión mínima de VS Code con resaltado de sintaxis para `.janel` (Python en `<script>` y en las expresiones, CSS en `<style>`). Ver su [README](../packages/janelkit-vscode/README.md) para instalarla. No tiene autocompletado ni diagnósticos: los errores los muestran `janel dev` y `janel build`.

## Pruebas automáticas de una aplicación

`janelkit.inspect` monta la aplicación sin ventana y la maneja como lo haría un usuario. Funciona con pytest o con cualquier otro sistema de pruebas:

```python
# tests/test_app.py
from janelkit.inspect import mount

def test_añadir_tarea():
    with mount("src/App.janel") as app:
        app.find(placeholder="¿Qué hay que hacer?").type("Comprar pan").submit()
        tarea = app.find("checkbox", text="Comprar pan")
        tarea.check()
        assert app.get("todos")[-1]["done"] is True

def test_búsqueda_asíncrona():
    with mount("src/App.janel") as app:
        app.find(text="Buscar").click()
        app.wait(until=lambda: not app.get("resultados").loading)
        assert "Sin resultados" not in app.texts()
```

- `find` exige que haya **exactamente un** elemento que cumpla los criterios (etiqueta, `text`, `id`, `placeholder`); `find_all` devuelve todos. Solo se consideran los visibles.
- Las acciones (`click`, `type`, `check`, `choose`, `slide`, `submit`) emiten las mismas señales que el usuario: pasan por los manejadores y los `bind:` reales. Sobre un control desactivado fallan, como fallaría el usuario.
- `app.texts()` devuelve los textos visibles en orden de lectura.
- `app.wait(segundos)` o `app.wait(until=condición)` deja correr las tareas asíncronas y los temporizadores.
- Diálogos y notificaciones de `janelkit-desktop`: `app.answer_dialog(...)`, `app.notifications()` (ver su [README](../packages/janelkit-desktop/README.md#en-pruebas)).
- Capturas: `app.screenshot("pantalla.png")` o `elemento.screenshot(...)` devuelven un `QImage` (y lo guardan si se da una ruta). Con `headless=True` (por defecto) en Windows la captura sale sin fuentes ni vídeo; para revisarla a ojo, `mount(..., headless=False)`.

Ver la referencia en [api.md](api.md#janelkitinspect-pruebas-y-herramientas).

**Pruebas de humo:**

`JANELKIT_EXIT_AFTER_MS=500 python main.py` cierra la aplicación tras 500 ms: útil para pruebas de humo en CI. Con `QT_QPA_PLATFORM=offscreen` no se muestra ninguna ventana.

## Distribuir: un ejecutable con PyInstaller

[PyInstaller](https://pyinstaller.org) genera una carpeta con un ejecutable que funciona sin Python instalado. La receta se probó en Windows 11 (Python 3.10, PySide6 6.8, PyInstaller 6.22) empaquetando `apps/examples/files`; en Linux y macOS el procedimiento es el mismo.

### Receta

Desde la carpeta del proyecto (la que tiene `main.py` y `src/`), con el entorno de la aplicación activado:

```bash
pip install pyinstaller

# Windows (separador ";" en --add-data)
pyinstaller --noconfirm --windowed --name MiApp ^
  --add-data "src;src" ^
  --collect-data janelkit --collect-submodules janelkit ^
  --paths src ^
  --hidden-import services.storage ^
  main.py

# Linux / macOS (separador ":")
pyinstaller --noconfirm --windowed --name MiApp \
  --add-data "src:src" \
  --collect-data janelkit --collect-submodules janelkit \
  --paths src \
  --hidden-import services.storage \
  main.py
```

El resultado queda en `dist/MiApp/`: distribuye la carpeta entera (el ejecutable más `_internal/`).

### Qué hace cada opción

| Opción | Por qué |
|---|---|
| `--add-data "src;src"` | Copia los `.janel` (y los `.qml` propios) dentro del paquete. `main.py` los busca en `src/` junto a sí mismo, igual que en desarrollo. |
| `--collect-data janelkit` | Incluye el módulo QML `Janel` y los demás recursos del paquete `janelkit`. |
| `--collect-submodules janelkit` | JanelKit importa partes de sí mismo bajo demanda; PyInstaller no las ve al analizar `main.py`. |
| `--paths src` + `--hidden-import services.x` | Los módulos que solo importan tus `.janel` (`from services.storage import ...`) no los ve el análisis de PyInstaller: nómbralos para que se incluyan con sus dependencias. Uno por módulo. |
| `--windowed` | Sin ventana de consola (en Windows y macOS). Quítalo mientras pruebas el paquete para ver los errores. |

### Comprobar el paquete

Antes de distribuirlo, arráncalo una vez sin `--windowed`. Para una prueba automática (por ejemplo en la CI), estas variables lo cierran solo:

```bash
set QT_QPA_PLATFORM=offscreen
set JANELKIT_EXIT_AFTER_MS=1500
dist\MiApp\MiApp.exe
echo %ERRORLEVEL%          # 0 = arrancó y montó la vista sin errores
```

Si falta un `.janel`, un módulo o un tipo QML, el ejecutable termina con código 1 y escribe el error en la consola.

### Tamaño

La carpeta incluye Qt completo: con `apps/examples/files` ocupa 341 MB sin comprimir y 146 MB en un .zip. Se puede reducir excluyendo módulos de Qt que la aplicación no usa (`--exclude-module PySide6.QtWebEngineCore`, `QtMultimedia`, `Qt3D*`…). Comprueba siempre el resultado tras excluir.

### Límites

- Hay que listar a mano (`--hidden-import`) los módulos Python que solo se importan desde los `.janel`.
- Con `--onefile` (un único ejecutable) arranca más despacio: descomprime todo en cada inicio.
- Firmar el ejecutable y crear instaladores (MSI, DMG, AppImage) queda fuera de esta receta.
