# Patrones para aplicaciones en tiempo real

Lo que cuesta entender al hacer una aplicación que se actualiza sola muchas veces por segundo: visión por computador, adquisición de datos, paneles de máquinas. Sale del primer proyecto real con JanelKit (tres cámaras USB a 30 FPS, detección con YOLO en cada ciclo, una ventana en un proyector). Lo básico está en [lenguaje.md](lenguaje.md#trabajo-asíncrono).

## El ciclo: runner, `Options` y `Snapshot`

El trabajo pesado (leer las cámaras, el modelo) va en un hilo con `background()`. Ese código **no toca `state`**:

- recibe todo lo que necesita en un objeto armado antes del `await` (`Options`);
- devuelve un resultado inmutable (`Snapshot`), que el tic aplica al volver.

```python
# core/runner.py — no importa janelkit: se prueba sin ventana
class Options(NamedTuple):
    threshold: float
    cameras: tuple[int, ...]

class Snapshot(NamedTuple):
    frames: dict[int, QImage]
    detections: tuple[Detection, ...]

def cycle(images, options: Options) -> Snapshot: ...
```

```python
# pages/Live.janel
@interval(15)
async def tick():
    options = runner.Options(threshold.value, tuple(cameras.value))   # se leen los state aquí, en el hilo de la interfaz
    snapshot = await background(runner.cycle, hub.read_all(), options)  # el modelo, en el pool
    for index, frame in snapshot.frames.items():
        previews[index].push(frame)
    detections.value = snapshot.detections                             # una sola asignación
```

- Un `interval` async **se salta los tics** mientras la ejecución anterior no termina: un ciclo de 50 ms con `interval(15)` corre unas 17 veces por segundo, sin acumularse.
- `Frames.push()` funciona desde cualquier hilo y copia la imagen: el hilo de cada cámara puede empujar su frame directamente a la vista previa.
- Leer o asignar `state` desde el código de `background()` lanza `WrongThreadError`, con la forma correcta en el mensaje.

## El estado a medias tras un `await`

Dentro de un manejador o de un tic, todo lo que cambias va en un `batch`: los efectos y la interfaz se actualizan una vez, al final. **Tras un `await` ya no**: cada asignación avisa por separado.

```python
async def tick():
    result = await background(work)
    count.value = result.count     # un efecto que lee count y label corre aquí…
    label.value = result.label     # …y otra vez aquí. La primera vez vio count nuevo y label viejo.
```

Dos formas de evitarlo:

```python
    with batch():                   # 1) agrupar
        count.value = result.count
        label.value = result.label

    status.value = result           # 2) un único valor: un NamedTuple con todo
```

Asignar el estado completo en cada ciclo no cuesta nada si no cambió: asignar un valor igual al actual no avisa a nadie (se compara con `==`), y un `computed` solo se recalcula si alguien lo lee.

## Qué avisa al modificarse por dentro

| Valor en el `state` | Modificarlo en el sitio (`.append`, `x["k"] = …`) | Qué hacer |
|---|---|---|
| `list`, `dict`, `set` (y anidados) | Avisa: se convierten en colecciones reactivas | Nada |
| Tupla, `NamedTuple`, `dataclass(frozen=True)` | No se puede | Asignar uno nuevo: `s.value = s.value._replace(x=1)` |
| Objeto propio, subclase propia de `list`/`dict` | No avisa | Llamar a `s.notify()` tras modificarlo |
| Array de numpy | No avisa | Asignar uno nuevo. Ojo: **siempre** cuenta como cambio (su `==` no da un `bool`), aunque sea igual |

Además, `state(valor)` **copia** las listas, diccionarios y conjuntos: modificar después el original que le pasaste no hace nada. Modifica el que devuelve `s.value`.

## Vistas ocultas que siguen trabajando

Con `sections` (o `{#hidden}`, o en una página de debajo), una vista oculta se conserva: la plantilla deja de actualizarse, pero lo del script sigue funcionando, también sus `interval`. Para no hacer trabajo que nadie ve, condiciona el temporizador a que el componente se vea:

```python
from janelkit import interval, is_visible

visible = is_visible()

@interval(15, when=visible)          # no cuenta mientras el componente no se ve
async def tick():
    ...
```

`when=` acepta cualquier condición reactiva: `when=hub.ready`, `when=lambda: visible.value and hub.ready.value`. Un `effect` puede usar `visible` igual, por ejemplo para soltar la cámara mientras no se ve. (Antes de 0.2 había que comprobarlo a mano al empezar cada tic.)

## Servicios compartidos con `state`

Un servicio (`services/cameras.py`) puede tener `state` como atributos y la plantilla los usa directamente: `{hub.status}`, `{#if hub.ready}`, `{#each hub.errors as e}` se muestran con su valor y se actualizan. Dentro de una operación, pide el valor: `{hub.ready.value and "lista"}`.

Un temporizador del servicio (por ejemplo, el que oculta un aviso) no necesita guardarse: JanelKit lo mantiene vivo mientras está activo. Uno creado en un componente, aunque sea tras un `await`, se detiene al desmontarlo.

## Medir ciclos en Windows

`time.monotonic()` avanza de 15,6 en 15,6 ms en Windows (usa `GetTickCount64`): no sirve para medir un ciclo de 15 ms. Usa `time.perf_counter()`.

El propio temporizador ya mide: `tick.last_duration` (segundos de la última ejecución, también la parte async), `tick.runs` y `tick.skipped` (tics que se saltaron porque la anterior seguía). Si `skipped` crece, el ciclo no cabe en el periodo.

Como referencia, el temporizador de JanelKit (`PreciseTimer` por debajo de 1 s), con la ventana sin trabajo:

| Periodo pedido | 1 ms | 5 ms | 10 ms | 15 ms | 33 ms | 100 ms |
|---|---|---|---|---|---|---|
| Tics por segundo | 971 | 200 | 100 | 67 | 30 | 10 |

## Probar y revisar pantallas sin abrir la aplicación

`janelkit.inspect.mount()` monta la aplicación, actúa como un usuario y ahora también captura:

```python
from janelkit.inspect import mount

with mount("src/App.janel", headless=False) as app:
    app.find(text="Arrancar").click()
    app.wait(1.0)
    app.screenshot("arrancado.png")
```

Con `headless=True` (plataforma `offscreen`) en Windows la captura sale sin fuentes ni vídeo: para revisarla a ojo, `headless=False`.
