# Empaquetar una aplicación (PyInstaller)

JanelKit no tiene un comando propio de empaquetado todavía (está previsto como proyecto aparte, ver [alcance.md](alcance.md)). Mientras tanto, esta receta con [PyInstaller](https://pyinstaller.org) genera una carpeta con un ejecutable que funciona sin Python instalado.

> Verificada en Windows 11 con Python 3.10, PySide6 6.8 y PyInstaller 6.22, empaquetando `examples/files` (componentes, servicios, `<List>`, diálogos y tareas en segundo plano). En Linux y macOS el procedimiento es el mismo, pero aún no se ha probado.

## Receta

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

## Qué hace cada opción

| Opción | Por qué |
|---|---|
| `--add-data "src;src"` | Copia los `.janel` (y los `.qml` propios) dentro del paquete. `main.py` los busca en `src/` junto a sí mismo, igual que en desarrollo. |
| `--collect-data janelkit` | Incluye el módulo QML `Janel` y los demás recursos del paquete `janelkit`. |
| `--collect-submodules janelkit` | JanelKit importa partes de sí mismo bajo demanda; PyInstaller no las ve al analizar `main.py`. |
| `--paths src` + `--hidden-import services.x` | Los módulos que solo importan tus `.janel` (`from services.storage import ...`) no los ve el análisis de PyInstaller: nómbralos para que se incluyan con sus dependencias. Uno por módulo. |
| `--windowed` | Sin ventana de consola (en Windows y macOS). Quítalo mientras pruebas el paquete para ver los errores. |

## Comprobar el paquete

Antes de distribuirlo, arráncalo una vez sin `--windowed`. Para una prueba automática (por ejemplo en la CI), estas variables lo cierran solo:

```bash
set QT_QPA_PLATFORM=offscreen
set JANELKIT_EXIT_AFTER_MS=1500
dist\MiApp\MiApp.exe
echo %ERRORLEVEL%          # 0 = arrancó y montó la vista sin errores
```

Si falta un `.janel`, un módulo o un tipo QML, el ejecutable termina con código 1 y escribe el error en la consola.

## Tamaño

La carpeta incluye Qt completo: con `examples/files` ocupa 341 MB sin comprimir y 146 MB en un .zip. Se puede reducir excluyendo módulos de Qt que la aplicación no usa (`--exclude-module PySide6.QtWebEngineCore`, `QtMultimedia`, `Qt3D*`…). Comprueba siempre el resultado tras excluir.

## Limitaciones conocidas

- Hay que listar a mano (`--hidden-import`) los módulos Python que solo se importan desde los `.janel`.
- No se ha probado `--onefile` (un único ejecutable). Si lo usas, ten en cuenta que arranca más despacio: descomprime todo en cada inicio.
- Firmar el ejecutable y crear instaladores (MSI, DMG, AppImage) queda fuera de esta receta.
