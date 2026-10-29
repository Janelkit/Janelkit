# janelkit-desktop

[![PyPI](https://img.shields.io/pypi/v/janelkit-desktop)](https://pypi.org/project/janelkit-desktop/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit-desktop)](https://pypi.org/project/janelkit-desktop/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**Servicios del sistema para aplicaciones [JanelKit](https://pypi.org/project/janelkit/):** diálogos nativos, portapapeles y notificaciones, con `await` y sin bloquear la ventana.

```bash
pip install janelkit-desktop
```

## En un minuto

```python
from janelkit_desktop import clipboard, dialogs, notify

async def abrir():
    ruta = await dialogs.open_file("Abrir nota", filters=["Texto (*.txt *.md)"])
    if ruta is not None:                      # None si el usuario cancela
        texto.value = ruta.read_text()

async def borrar():
    if await dialogs.confirm("¿Borrar la nota?"):
        ...

def copiar():
    clipboard.copy(texto.value)
    notify("Copiado", "La nota está en el portapapeles")
```

```html
<Button on:click={abrir}>Abrir…</Button>
<Text>En el portapapeles: {clipboard.paste()}</Text>
```

## Características

- **Diálogos nativos y asíncronos.** Abrir, guardar, elegir carpeta, mensaje y confirmación. Se esperan con `await`: la ventana sigue respondiendo y el resultado llega como `Path`, una lista, `bool` o `None` si se cancela.
- **Portapapeles reactivo.** `clipboard.paste()` en la plantilla se actualiza cuando cambia el portapapeles, también si cambia desde otra aplicación.
- **Notificaciones del sistema.** Con icono en la bandeja. Al pulsar una, la ventana pasa al frente y se llama a `on_click`.
- **Fácil de probar.** Añade métodos a `janelkit.inspect` para responder diálogos y leer notificaciones en las pruebas, sin ventanas reales.
- **Solo API pública.** Usa `janelkit` y `janelkit.ext`, nada interno del núcleo; una prueba del repositorio lo comprueba.

## Referencia

| Nombre | Descripción |
|---|---|
| `dialogs` | Diálogos del sistema, todos asíncronos (`await`): `open_file`, `open_files`, `save_file` y `choose_folder` (devuelven `Path`, una lista o `None` si se cancela), `message` y `confirm` (devuelve `bool`). Para pruebas, `pending()` lista los abiertos y `kind(d)` dice el tipo de uno (`"MessageDialog"`, `"FileDialog"`, `"FolderDialog"`). |
| `clipboard` | Portapapeles del sistema (texto): `copy(texto)`, `paste()` (el texto que hay, o `""` si no hay nada; reactivo) y `clear()`. |
| `notify` | `notify(título, mensaje="", on_click=None)` muestra una notificación del sistema. Donde no hay bandeja no se ve, pero queda registrada. |

Las tres piezas necesitan una aplicación en marcha.

## En pruebas

Al importarse, el paquete añade estos métodos a `MountedApp` de `janelkit.inspect`:

| Método | Descripción |
|---|---|
| `app.dialogs()` | Diálogos abiertos, del más antiguo al más reciente. |
| `app.answer_dialog(resultado)` | Responde al último: una ruta (archivos o carpeta), `True` (aceptar) o `False` (cancelar). |
| `app.notifications()` | Notificaciones enviadas (`{"title", "message"}`), de la más antigua a la más reciente. |

```python
from janelkit import inspect

def test_borrar_pregunta_antes():
    with inspect.mount("src/App.janel") as app:
        app.find(text="Borrar").click()
        app.answer_dialog(False)              # el usuario cancela
        assert app.find(text="Mi nota")
```

Ejemplos: [`apps/examples/files`](https://github.com/janelkit/janelkit/tree/main/apps/examples/files) (elegir carpeta), [`apps/challenges/gestor`](https://github.com/janelkit/janelkit/tree/main/apps/challenges/gestor) (confirmaciones) y [`apps/challenges/chat`](https://github.com/janelkit/janelkit/tree/main/apps/challenges/chat) (notificaciones).

## Compatibilidad

| janelkit-desktop | janelkit | Python |
|---|---|---|
| 0.1.x | ≥ 0.1, < 0.2 | ≥ 3.10 |

Sigue la misma [política de versiones](https://github.com/janelkit/janelkit/blob/main/docs/api.md#paquetes-del-ecosistema) que el núcleo, con versión propia.

## Cambios

### 0.1.0

- Primera versión publicada. Antes eran los módulos `janelkit.dialogs`, `janelkit.clipboard` y `janelkit.notifications` del núcleo: cambia `from janelkit import dialogs, clipboard, notify` por `from janelkit_desktop import dialogs, clipboard, notify`.
- Compatible con `janelkit` 0.1 (`janelkit>=0.1,<0.2`).

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).
