# Patrones para aplicaciones en tiempo real

Lo que cuesta entender al hacer una aplicación que se actualiza sola muchas veces por segundo: visión por computador, adquisición de datos, paneles de máquinas. Lo básico está en [lenguaje.md](lenguaje.md#trabajo-asíncrono).

## Fotogramas y resultados van por caminos distintos

El fotograma es un array de numpy **en el mismo proceso** que la interfaz: el modelo (OpenCV, ONNX Runtime, PyTorch…) lo procesa ahí y sus resultados (cajas, puntos, conteos) entran en el estado reactivo, sin servidor ni serializar nada. La regla: **los fotogramas no pasan por la reactividad** (a 30–60 por segundo, un `state` por fotograma sería lento); lo reactivo son los resultados.

```
cámara ──► hilo de captura ──► Frames ──► <video>  (Qt sube la imagen a la GPU)
                                  │
                                  └──► async for f in frames   (siempre el más reciente)
                                          r = await background(modelo, f)   (otro hilo)
                                          detecciones.value = r  ──► plantilla
```

- La captura corre en su propio hilo (`cv2.VideoCapture`) y entrega con `frames.push(img)`, que se puede llamar desde cualquier hilo. QtMultimedia también puede abrir cámaras, pero está en PySide6-Addons, que JanelKit no instala (`pip install PySide6-Addons`); con OpenCV no hace falta.
- `<video source={frames}>` muestra el más reciente; si llegan más rápido de lo que se dibuja, se saltan, nunca se encolan.
- `async for f in frames` da el más reciente cada vez que el modelo queda libre. Con `background()`, un modelo a 12 fps no frena la vista previa a 30 ni la interfaz (numpy, OpenCV y PyTorch liberan el GIL).
- Los hijos de `<video>` se colocan sobre la imagen, en una capa de su tamaño exacto: las cajas de detección son elementos normales, con estilo y clic. Ver [Vídeo](lenguaje.md#vídeo-video-y-frames).

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

## Vídeo y modelos en el mismo proceso

### Las bibliotecas nativas pesadas, al arrancar

PyTorch, ultralytics (YOLO), MediaPipe o TensorFlow cargan bibliotecas nativas grandes al importarse. Impórtalas en el hilo principal y al principio, antes de `run()`; en `background()` crea solo los modelos.

```python
# main.py
import torch                    # noqa: F401 — se carga aquí, en el hilo principal
from ultralytics import YOLO    # noqa: F401
from janelkit import run
```

Si la primera importación ocurre dentro de `background()` mientras OpenCV lee cámaras en otros hilos, se ha visto caer el proceso con un fallo de memoria (`access violation` en Windows).

### Dónde llamar a `push`

`push` copia y convierte el fotograma en el hilo que lo llama: unos 0,4 ms a 640 × 480 y 1,1 ms a 1920 × 1080 en el equipo de referencia ([arquitectura.md](arquitectura.md#rendimiento)).

- En el hilo de cada cámara, o dentro de la función que corre en `background()`, ese coste no lo paga la interfaz.
- En el tic, después del `await` (como en el ejemplo de arriba), sí: con cuatro vistas de 1080p son unos 4 ms de cada ciclo en el hilo de la interfaz. Si el ciclo va justo, pasa los `Frames` a la función de `background()` y haz el `push` allí: `Frames` no necesita el hilo de la interfaz para recibir fotogramas.

### Un fotograma lo pueden tener varios

`async for` y `frames.latest()` dan el mismo objeto que se pasó a `push`, no una copia, y el fotograma de una cámara suele estar a la vez en la vista previa, en el modelo y en una grabación. Nadie debe modificarlo en su sitio:

- Para dibujar encima, copia antes (`img = frame.copy()`). Mejor aún, no dibujes en el array: las cajas y las etiquetas pueden ser hijos de `<video>`, colocados en porcentajes de la imagen ([Vídeo](lenguaje.md#vídeo-video-y-frames)).
- Para que un error así salte en vez de ensuciar en silencio la vista de otro, marca el array como de solo lectura al leerlo de la cámara: `frame.flags.writeable = False`. Escribir en él da error al primer intento (numpy: `ValueError: assignment destination is read-only`; las funciones de dibujo de OpenCV también lo rechazan), y `push` lo acepta igual.

### Marcar sobre la imagen y saber si la fuente se paró

- `<video on:click={marcar}>` da en `event.image_x` y `event.image_y` el píxel de la imagen, con cualquier `fit`: puntos de calibración, zonas, elegir un objeto. Sin capa hija ni regla de tres.
- `frames.stalled` pasa a `True` tras `stall_after` segundos sin `push` (`Frames(stall_after=1.5)`): `{#if frames.stalled}<text>Sin señal</text>{/if}`. Solo ve los `push`: una cámara desconectada cuyo último fotograma se sigue empujando en cada ciclo no se detecta así. Eso lo sabe quien lee la cámara, por ejemplo comparando el instante de cada lectura.

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

`when=` acepta cualquier condición reactiva: `when=hub.ready`, `when=lambda: visible.value and hub.ready.value`. Un `effect` puede usar `visible` igual, por ejemplo para soltar la cámara mientras no se ve.

## Datos compartidos: store o `state` en un servicio

- Lo que comparten varias vistas o ventanas (el usuario, los documentos, el carrito) va en un **store** de [`janelkit-store`](../packages/janelkit-store/README.md): una instancia por aplicación (`use(Carrito)`), acciones que agrupan y anotan cada cambio, modo estricto si se quiere, y una instancia nueva en cada prueba.
- `state` en un `.py` queda para lo que no es «los datos de la aplicación»: un objeto con estado propio del que hay varios (una `Camara` por cámara con `self.estado = state(...)`), una biblioteca que ofrece una API reactiva, o lógica que se prueba sin Qt.

Un servicio con `state` como atributos se usa directamente en la plantilla: `{hub.status}`, `{#if hub.ready}`, `{#each hub.errors as e}` se muestran con su valor y se actualizan. Dentro de una operación, pide el valor: `{hub.ready.value and "lista"}`. `@computed` sobre un método da un derivado por instancia.

Un temporizador creado en el servicio (por ejemplo, el que oculta un aviso) no hace falta guardarlo: sigue vivo mientras está activo.

## Medir ciclos en Windows

`time.monotonic()` avanza de 15,6 en 15,6 ms en Windows (usa `GetTickCount64`): no sirve para medir un ciclo de 15 ms. Usa `time.perf_counter()`.

El propio temporizador ya mide: `tick.last_duration` (segundos de la última ejecución, también la parte async), `tick.runs` y `tick.skipped` (tics que se saltaron porque la anterior seguía). Si `skipped` crece, el ciclo no cabe en el periodo.

Como referencia, el temporizador de JanelKit (`PreciseTimer` por debajo de 1 s), con la ventana sin trabajo:

| Periodo pedido | 1 ms | 5 ms | 10 ms | 15 ms | 33 ms | 100 ms |
|---|---|---|---|---|---|---|
| Tics por segundo | 971 | 200 | 100 | 67 | 30 | 10 |
