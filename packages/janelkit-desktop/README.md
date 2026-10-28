# janelkit-desktop

Servicios del sistema para aplicaciones [JanelKit](../../README.md): diálogos nativos, portapapeles y notificaciones.

```bash
pip install janelkit-desktop      # en el repositorio: pip install -e packages/janelkit-desktop
```

```python
from janelkit_desktop import clipboard, dialogs, notify

async def abrir():
    ruta = await dialogs.open_file("Abrir nota", filters=["Texto (*.txt *.md)"])
    if ruta is not None:              # None si el usuario cancela
        texto.value = ruta.read_text()
```

Solo usa la API pública del núcleo (`janelkit` y `janelkit.ext`). Las tres piezas necesitan una aplicación en marcha.

## Referencia

| Nombre | Descripción |
|---|---|
| `dialogs` | Diálogos del sistema, todos asíncronos (`await`): `open_file`, `open_files`, `save_file`, `choose_folder` (devuelven `Path`, lista o `None` si se cancela), `message` y `confirm` (devuelve `bool`). `pending()` lista los abiertos y `kind(d)` dice el tipo de uno (`"MessageDialog"`, `"FileDialog"`, `"FolderDialog"`), para pruebas. |
| `clipboard` | Portapapeles del sistema (texto): `copy(texto)`, `paste()` (el texto que hay, `""` si no hay; reactivo: se actualiza cuando cambia, también desde otra aplicación) y `clear()`. |
| `notify` | `notify(título, mensaje="", on_click=None)` muestra una notificación del sistema (con un icono en la bandeja). Pulsarla trae la ventana al frente y llama a `on_click`. Donde no hay bandeja no se ve, pero queda registrada. |

## En pruebas

Al importarse, añade estos métodos a `MountedApp` de `janelkit.inspect` (con `janelkit.ext.inspector`):

| Método | Descripción |
|---|---|
| `app.dialogs()` | Diálogos abiertos, del más antiguo al más reciente. |
| `app.answer_dialog(resultado)` | Responde al último: una ruta (archivos o carpeta), `True` (aceptar) o `False` (cancelar). |
| `app.notifications()` | Notificaciones enviadas (`{"title", "message"}`), de la más antigua a la más reciente. |

Ejemplos: `apps/examples/files` (elegir carpeta), `apps/challenges/gestor` (confirmaciones) y `apps/challenges/chat` (notificaciones).

## Cambios

### 0.0.1.dev0 (sin publicar)

- Primera versión como paquete propio. Antes eran los módulos `janelkit.dialogs`, `janelkit.clipboard` y `janelkit.notifications` del núcleo: cambia `from janelkit import dialogs, clipboard, notify` por `from janelkit_desktop import dialogs, clipboard, notify`.
- Compatible con `janelkit` 0.0.1.dev0 (prealfa); se ampliará al publicarse la 0.1 (`janelkit>=0.0.1.dev0,<0.1`).
