# janelkit-desktop

[![PyPI](https://img.shields.io/pypi/v/janelkit-desktop)](https://pypi.org/project/janelkit-desktop/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit-desktop)](https://pypi.org/project/janelkit-desktop/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**Servicios del sistema para aplicaciones [JanelKit](https://pypi.org/project/janelkit/):** diálogos nativos y portapapeles, con `await` y sin bloquear la ventana.

```bash
pip install janelkit-desktop
```

## En un minuto

```python
from janelkit_desktop import clipboard, dialogs

async def abrir():
    ruta = await dialogs.open_file("Abrir nota", filters=["Texto (*.txt *.md)"])
    if ruta is not None:                      # None si el usuario cancela
        texto.value = ruta.read_text()

async def borrar():
    if await dialogs.confirm("¿Borrar la nota?"):
        ...

def copiar():
    clipboard.copy(texto.value)
```

```html
<button on:click={abrir}>Abrir…</button>
<text>En el portapapeles: {clipboard.paste()}</text>
```

## Características

- **Diálogos nativos y asíncronos.** Abrir, guardar, elegir carpeta, mensaje y confirmación. Se esperan con `await`: la ventana sigue respondiendo y el resultado llega como `Path`, una lista, `bool` o `None` si se cancela.
- **Portapapeles reactivo.** `clipboard.paste()` en la plantilla se actualiza cuando cambia el portapapeles, también si cambia desde otra aplicación.
- **Fácil de probar.** Añade métodos a `janelkit.inspect` para responder diálogos en las pruebas, sin ventanas reales.
- **Solo API pública.** Usa `janelkit` y `janelkit.ext`, nada interno del núcleo; una prueba del repositorio lo comprueba.

## Referencia

| Nombre | Descripción |
|---|---|
| `dialogs` | Diálogos del sistema, todos asíncronos (`await`): `open_file`, `open_files`, `save_file` y `choose_folder` (devuelven `Path`, una lista o `None` si se cancela), `message` y `confirm` (devuelve `bool`). Para pruebas, `pending()` lista los abiertos y `kind(d)` dice el tipo de uno (`"MessageDialog"`, `"FileDialog"`, `"FolderDialog"`). |
| `clipboard` | Portapapeles del sistema (texto): `copy(texto)`, `paste()` (el texto que hay, o `""` si no hay nada; reactivo) y `clear()`. |

Las tres piezas necesitan una aplicación en marcha.

## En pruebas

Al importarse, el paquete añade estos métodos a `MountedApp` de `janelkit.inspect`:

| Método | Descripción |
|---|---|
| `app.dialogs()` | Diálogos abiertos, del más antiguo al más reciente. |
| `app.answer_dialog(resultado)` | Responde al último: una ruta (archivos o carpeta), `True` (aceptar) o `False` (cancelar). |

```python
from janelkit import inspect

def test_borrar_pregunta_antes():
    with inspect.mount("src/App.janel") as app:
        app.find(text="Borrar").click()
        app.answer_dialog(False)              # el usuario cancela
        assert app.find(text="Mi nota")
```

Ejemplos: [`apps/examples/files`](https://github.com/janelkit/janelkit/tree/main/apps/examples/files) (elegir carpeta), [`apps/challenges/gestor`](https://github.com/janelkit/janelkit/tree/main/apps/challenges/gestor) (confirmaciones) y [`apps/challenges/hoja`](https://github.com/janelkit/janelkit/tree/main/apps/challenges/hoja) (abrir y guardar CSV, portapapeles).

## Compatibilidad

| janelkit-desktop | janelkit | Python |
|---|---|---|
| 0.2.x.x | 0.2.x.x | ≥ 3.10 |
| 0.1.x | 0.1.x | ≥ 3.10 |

Comparte la serie con el núcleo: janelkit-desktop 0.2.x.x va con janelkit 0.2.x.x. Los dos últimos números son suyos ([política de versiones](https://github.com/janelkit/janelkit/blob/main/docs/api.md#paquetes-del-ecosistema)).

## Cambios

### 0.2.0.0 (2026-11-05)

- **Se quitan las notificaciones:** `notify`, el icono de la bandeja del sistema y `app.notifications()` en `janelkit.inspect`. El paquete se queda con lo que casi toda aplicación de escritorio necesita: diálogos de archivos, carpeta, mensaje y confirmación, y el portapapeles. Para avisar dentro de la aplicación, usa un aviso en la propia ventana (por ejemplo, un `{#if}` con un `timeout`). Importar `notify` da un error que lo explica.

### 0.1.0

- Primera versión publicada. Antes eran los módulos `janelkit.dialogs`, `janelkit.clipboard` y `janelkit.notifications` del núcleo: cambia `from janelkit import dialogs, clipboard, notify` por `from janelkit_desktop import dialogs, clipboard, notify`.
- Compatible con `janelkit` 0.1 (`janelkit>=0.1,<0.2`).

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).
