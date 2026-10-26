# FluxUI

> **Prealfa.** Nombre, extensión y API son provisionales. No está publicado en PyPI.

Componentes de archivo único (`.flux`) para aplicaciones de escritorio: **Python** para la lógica, una plantilla declarativa reactiva y **Qt Quick** (PySide6) para el renderizado. Sin JavaScript ni QML escrito a mano.

```html
<script lang="python">
from fluxui import state, computed

count = state(0)
name = state("")

@computed
def greeting():
    return f"Hola, {name.value or 'invitado'}"

def increment():
    count.value += 1
</script>

<Window title="Mi aplicación" width={640} height={400}>
  <Column class="page">
    <Text class="heading">{greeting}</Text>
    <TextField bind:value={name} placeholder="Tu nombre" />
    <Button on:click={increment}>Clicks: {count}</Button>
    {#if count >= 5}
      <Text>Has llegado a cinco clicks.</Text>
    {/if}
  </Column>
</Window>

<style>
.page { padding: 24px; gap: 16px; }
.heading { font-size: 24px; font-weight: 600; }
</style>
```

## Probarlo (desde el repositorio)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
python -m pip install -e ".[dev]"

flux new mi-app
cd mi-app
python main.py
```

O el ejemplo incluido: `python examples/counter/main.py`.

## Comandos

| Comando | Qué hace |
|---|---|
| `flux new <nombre> [--path DIR]` | Crea un proyecto con `main.py` y `src/App.flux`. No sobrescribe carpetas con contenido. |
| `flux parse <archivo.flux>` | Muestra el AST o los errores con línea y columna. |
| `flux compile <archivo.flux> [-o salida.qml]` | Muestra el QML generado. |
| `python main.py` | Forma canónica de ejecutar una aplicación. |

## Cómo funciona

```
App.flux ─► parser (AST con ubicaciones) ─► IR ─┬─► QML generado (solo lee propiedades del puente)
                                                └─► runtime Python: script por instancia, bindings reactivos
                                                         │
                                       puente QObject por instancia (propiedad notificable por binding)
```

Las expresiones de la plantilla se evalúan en **Python**; cuando cambia un `state`, solo se recalculan los bindings que lo leyeron y solo se notifica a QML la propiedad afectada.

## Documentación

- [docs/lenguaje.md](docs/lenguaje.md) — formato `.flux`, expresiones, directivas y elementos disponibles.
- [docs/estilos.md](docs/estilos.md) — subconjunto CSS soportado.
- [docs/estado.md](docs/estado.md) — avance frente al plan, decisiones provisionales y limitaciones.
- [spikes/qt_bridge_counter/NOTES.md](spikes/qt_bridge_counter/NOTES.md) — validación técnica del puente Python ↔ Qt Quick.

## Desarrollo

```bash
python -m pytest                 # pruebas (Qt en modo offscreen)
python tools/check_wheel.py      # construye wheel/sdist, instala en un venv limpio y prueba flux new + python main.py
```
