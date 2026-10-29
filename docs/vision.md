# Visión por computador en tiempo real

Plan para que hacer aplicaciones de visión (cámaras, detección, seguimiento, inspección) con JanelKit sea fácil. Parte va en el núcleo y se implementa ya; el resto es un paquete del ecosistema, **`janelkit-vision`**, que de momento solo está planeado.

| Parte | Dónde | Estado |
|---|---|---|
| Mostrar fotogramas a tiempo real: `<Video>` y `Frames` | Núcleo | ✅ (ejemplo sin cámara en `apps/examples/video`) |
| Cámaras, tubería de proceso, coordenadas, grabación, fuentes falsas | `janelkit-vision` | Planeado, sin implementar |
| Reto 5: aplicación de visión en tiempo real | [challenges_to_test.md](challenges_to_test.md#5-visión-en-tiempo-real) | Planeado; necesita `janelkit-vision` |

## Por qué es un distintivo

Hoy una aplicación de visión con una interfaz cuidada se hace, casi siempre, de una de dos maneras:

- **Interfaz web (navegador, Electron, Tauri) con Python detrás.** Hay que levantar un servidor, comprimir cada fotograma (JPEG, WebRTC) o mandarlo por un WebSocket, y se paga en latencia, CPU y dos lenguajes.
- **Tkinter, PyQt a mano o `cv2.imshow`.** Sin servidor, pero la interfaz es pobre o cuesta mucho.

En JanelKit el fotograma es un array de numpy **en el mismo proceso** que la interfaz. El modelo (OpenCV, ONNX Runtime, PyTorch, mediapipe…) lo procesa ahí, y sus resultados (cajas, puntos, conteos) entran en el estado reactivo y se pintan, sin serializar nada ni pasar por la red. Con una interfaz declarativa, eso no lo ofrece ningún otro framework de Python.

## Arquitectura

La regla principal: **los fotogramas no pasan por la reactividad.** A 30–60 fotogramas por segundo, mandar cada uno por un `state` y un binding sería lento. Van por un camino aparte; lo reactivo son los resultados.

```
cámara ──► hilo de captura ──► Frames ──► <Video>  (Qt sube la imagen a la GPU)
                                  │
                                  └──► async for f in frames   (siempre el más reciente)
                                          r = await background(modelo, f)   (otro hilo)
                                          detecciones.value = r  ──► plantilla
```

1. **Captura**, en su hilo. Entrega fotogramas a un `Frames` con `push()`, que se puede llamar desde cualquier hilo.
2. **`<Video source={frames}>`** muestra el más reciente. Si llegan más rápido de lo que se dibuja, se saltan: nunca se encolan.
3. **Proceso**: `async for f in frames` da el más reciente cada vez que el modelo queda libre. Con `background()` el modelo corre en otro hilo (numpy, OpenCV y PyTorch liberan el GIL), así que un modelo a 12 fps no frena la vista previa a 30 ni la interfaz. Lo que hace el modelo vuelve al hilo de la interfaz por `await` y se asigna a un `state`.
4. **Superposiciones declarativas**: los hijos de `<Video>` se colocan sobre la imagen, en una capa del tamaño exacto de lo que se ve de ella. Un `left: 25%` es el 25 % del ancho de la imagen, aunque esté escalada o con bandas. Así las cajas son elementos normales: clicables, con estilo, transiciones y nombre accesible.

## En el núcleo

Lo genérico, útil también sin cámara (vídeo generado, visualización científica, una vista previa remota):

```python
from janelkit import Frames, background, spawn, state

frames = Frames(color="bgr")       # "bgr": el orden de OpenCV; por defecto "rgb"
detecciones = state([])

def capturar():                    # en un hilo propio
    while abierta:
        ok, img = camara.read()
        frames.push(img)           # numpy (alto × ancho × 3), desde cualquier hilo

async def procesar():
    async for img in frames:       # el más reciente; se saltan los que no dio tiempo
        detecciones.value = await background(modelo, img)
```

```html
<Video source={frames} fit="contain" label="Cámara">
  {#each detecciones as d}
    <flex class="caja" style={{"left": pct(d[0], 0), "top": pct(d[1], 1), "width": pct(d[2], 0), "height": pct(d[3], 1)}} />
  {/each}
</Video>
```

`pct(valor, eje)` pasa de píxeles de la imagen a porcentaje de la capa (`100 * valor / frames.size[eje]`); el ejemplo completo está en [lenguaje.md](lenguaje.md#vídeo-video-y-frames). En `janelkit-vision` vendrá hecho.

| Pieza | Qué hace |
|---|---|
| `Frames(color="rgb")` | Canal del último fotograma. `push(img)` desde cualquier hilo: arrays de numpy o cualquier objeto con el protocolo de búfer (`memoryview`) de forma alto × ancho (gris), × 3 (`rgb`/`bgr`) o × 4 (`rgba`/`bgra`), de bytes; también `QImage`. Copia la imagen, así que el búfer se puede reutilizar. |
| `async for img in frames` / `await frames.next()` | El fotograma más reciente que no se había dado aún (el objeto que se pasó a `push`). |
| `frames.size`, `frames.fps` | Reactivos: tamaño `(ancho, alto)` del último fotograma y fotogramas por segundo recibidos (se actualiza cada segundo). |
| `frames.latest()`, `frames.clear()` | El último fotograma (o `None`); dejar de mostrar. |
| `<Video source= fit=>` | Muestra un `Frames` con `VideoOutput` de Qt. `fit`: `contain` (por defecto), `cover`, `fill`. Los hijos van en una capa sobre la imagen. Sin `mirror`: para la cámara frontal se voltea la imagen antes de `push`, y así las coordenadas de las superposiciones siguen coincidiendo. |

Sin numpy como dependencia: el núcleo lee el búfer con `memoryview`. Sin cámara: QtMultimedia viene con PySide6, pero abrir cámaras es de `janelkit-vision`.

## `janelkit-vision` (planeado, sin implementar)

Lo que necesita una aplicación de visión y no hace falta en el núcleo. Depende de numpy; OpenCV opcional.

| Pieza | Para qué |
|---|---|
| `cameras()` y `Camera(id, size=, fps=)` | Listar cámaras (con QtMultimedia, sin OpenCV), elegir resolución y fps, cambiar de cámara en caliente, aviso al conectar o desconectar. Entrega a un `Frames` |
| Otras fuentes | `cv2.VideoCapture`, RTSP, archivos de vídeo, carpetas de imágenes, cámaras industriales (adaptadores) |
| `pipeline(fuente, modelo)` | La tubería de la arquitectura en una línea: hilo de proceso, «el último gana», métricas (fps de captura y de proceso, latencia), pausa |
| Coordenadas | Pasar de píxeles de la imagen a la capa de `<Video>` y al revés (región de interés dibujada con el ratón) |
| Capturar y grabar | Guardar una imagen o un clip (con su marca de tiempo) |
| Fuentes falsas para `inspect` | Una cámara que lee un vídeo o imágenes, para probar en CI y medir de forma reproducible |
| Ejemplos | Rostros (OpenCV + YuNet, sin PyTorch), YOLO (ultralytics), pose (mediapipe), códigos QR |

Se diseñará a partir de lo que el reto 5 demuestre que falta, como los demás paquetes.

## Mediciones del núcleo

`python apps/examples/video/bench.py --ventana` (Windows 11, PySide6 6.12, ventana a la vista): un hilo empuja fotogramas a 60 fps.

| Resolución | Entregados | `push` (en el hilo que lo llama) | De `push` a la entrega (p50 / p95) | CPU del hilo de la interfaz |
|---|---|---|---|---|
| 640 × 480 | 59,6 fps | 0,37 ms | 0,57 / 0,69 ms | 3,1 % |
| 1280 × 720 | 60,1 fps | 0,62 ms | 0,94 / 1,29 ms | 2,6 % |
| 1920 × 1080 | 59,6 fps | 1,07 ms | 1,54 / 1,84 ms | 6,2 % |

`push` copia y convierte la imagen a RGBX en el hilo que lo llama (~1 ms en 1080p), así que el de la interfaz solo entrega un `QVideoFrame` ya listo; Qt lo sube a la GPU en su hilo de dibujado. En el ejemplo, un modelo que tarda 200 ms procesa a ~5 fps y la vista sigue a 30.

## Riesgos y preguntas abiertas

- **Formatos de cámara**: muchas cámaras dan NV12 o MJPEG; convertir a RGB en Python cuesta. `janelkit-vision` podría pasar el `QVideoFrame` de Qt tal cual a `<Video>` y convertir solo lo que procesa el modelo.
- **Empaquetado**: PyTorch y ultralytics pesan ~1 GB; ONNX Runtime u OpenCV DNN son la opción ligera.
- **Varias cámaras**: un hilo de captura por cámara; medir el coste de varias `<Video>` a la vez.
