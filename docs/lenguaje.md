# Formato `.janel`

Esta especificación describe **lo que el compilador acepta hoy**. Los cambios entre versiones y cómo migrar están en [cambios.md](cambios.md); la política de versiones del formato (`FORMAT_VERSION`), en [api.md](api.md).

## Secciones

Un archivo `.janel` tiene hasta tres partes, en cualquier orden:

| Sección | Obligatoria | Reglas |
|---|---|---|
| `<script lang="python">…</script>` | No | Como máximo una. `lang` es opcional y solo admite `python`. El contenido puede ir indentado (se quita la indentación común). |
| Plantilla | Sí | Todo lo que queda fuera de `<script>` y `<style>`. Debe tener **un único elemento raíz**. |
| `<style>…</style>` | No | Como máximo una. Subconjunto CSS: ver [estilos.md](estilos.md). |

Los comentarios `<!-- … -->` se ignoran en la plantilla.

El componente raíz de la aplicación (`src/App.janel`) puede tener `<window>` como raíz; si no la tiene, el compilador lo envuelve en una ventana de 640×480 y su contenido ocupa toda la ventana. Los componentes usados dentro de otros **no** pueden tener `<window>` como raíz.

## El script

- Se ejecuta **una vez por instancia** del componente, en un espacio de nombres propio: dos instancias nunca comparten estado local.
- Se ejecuta en un módulo propio, registrado en `sys.modules` mientras la instancia existe: `@dataclass` (también con `from __future__ import annotations`), `typing.get_type_hints` y `pickle` funcionan con las clases que defina.
- Es Python normal: puede importar módulos del proyecto. La carpeta del componente raíz (`src/`) se añade a `sys.path`, de modo que `from services.users import display_name` funciona.
- Los errores de sintaxis se detectan al compilar, con archivo, línea y columna. Los errores al ejecutarse apuntan a la línea real del `.janel` en el traceback.
- **El código del componente se ejecuta como código del proyecto.** No hay aislamiento: no cargues componentes no confiables.

### Estado reactivo

```python
from janelkit import state, computed, batch

count = state(0)          # leer: count.value · escribir: count.value = 1
items = state([])         # listas, diccionarios y conjuntos son reactivos:
items.value.append("nuevo")             # modificar en el sitio notifica
items.value = [*items.value, "otro"]    # reasignar también

@computed                 # perezoso y cacheado; se invalida solo
def total():
    return count.value * 2

def reset():
    with batch():         # los manejadores de eventos ya se ejecutan en un lote
        count.value = 0
        items.value = []
```

Otras utilidades: `count.set(v)`, `count.update(fn)`, `count.peek()` (lee sin registrar dependencia). Asignar un valor igual (mismo tipo y `==`) no notifica.

En una clase (un servicio con estado propio), `@computed` sobre un método da un `computed` por instancia, que vive lo que vive la instancia:

```python
class Camara:
    def __init__(self):
        self.fps = state(0.0)

    @computed
    def estado(self):
        return "en marcha" if self.fps.value > 0 else "parada"
```

En Python se lee `camara.estado.value`; en la plantilla, `{camara.estado}`.

### Colecciones reactivas

Un `list`, `dict` o `set` guardado en un `state` se convierte (también los anidados) en una versión reactiva que sigue siendo una subclase de `list`/`dict`/`set`: `append`, `remove`, `sort`, `todo["done"] = True`, `del d[k]`, `s.add(x)`… actualizan la interfaz.

- Cada colección avisa solo a quien la leyó: cambiar `todos.value[0]["done"]` actualiza la fila de esa tarea y lo que dependa de ese diccionario, no toda la lista.
- Lo que se inserta en una colección reactiva también se convierte.
- La conversión **copia** el contenedor: modifica el objeto que devuelve el `state`, no el original que le pasaste.
- Las tuplas, las subclases propias de `list`/`dict` y otros objetos no se convierten. Si modificas uno en el sitio, llama a `estado.notify()`.

### Trabajo asíncrono

Las corrutinas se ejecutan en el **hilo de la interfaz**, sobre el bucle de Qt (JanelKit integra `asyncio` con `qasync`): tras cada `await` se puede modificar el estado directamente, y mientras esperan la ventana sigue respondiendo.

```python
from janelkit import state, task, background, spawn

async def guardar():                  # on:click={guardar}: se lanza sola
    estado.value = "guardando…"
    await api.guardar(datos.value)    # cualquier biblioteca asyncio (httpx, aiohttp…)
    estado.value = "guardado"

@task                                 # estado reactivo: .loading, .error, .value
async def resultados(consulta):
    return await background(buscar, consulta)   # buscar() bloquea: va a otro hilo

def enviar():
    resultados.run(consulta.value)    # cancela la búsqueda anterior si seguía en curso
```

| Herramienta | Para qué |
|---|---|
| Manejador `async def` | `on:click={guardar}` o `on:click={guardar(item)}`: la corrutina se lanza sola. |
| `@task` | Una operación con estado para la plantilla: `{#if resultados.loading}`, `{resultados.error}`, `{resultados.value}`. `.run(*args)` la reinicia y `.cancel()` la detiene. |
| `background(fn, *args)` | Código que bloquea (disco, CPU, bibliotecas síncronas como `urllib` o `requests`): `await background(fn, ...)` lo ejecuta en otro hilo y devuelve el resultado. `fn` no debe tocar estado ni interfaz. |
| `spawn(corrutina)` | Lanzar una corrutina sin esperarla, por ejemplo desde `on_mount`. |
| `interval(ms, fn)`, `timeout(ms, fn)` | Repetir algo cada cierto tiempo, o hacerlo una vez más tarde. Ver [Temporizadores](#temporizadores). |

- Lo lanzado desde un componente (manejadores, `@task`, `spawn`, `on_mount` asíncrono) se **cancela al desmontarlo**: una corrutina nunca actualiza una vista que ya no existe. Una fila de `{#each}` cancela lo suyo al eliminarse.
- Una corrutina lanzada desde un componente sigue perteneciéndole **después de cada `await`**: un `timeout`, `interval`, `effect` o `spawn` creado tras `await` se libera al desmontar, igual que si se hubiera creado antes. El patrón «guardar, esperar y mostrar un aviso que se va solo» funciona sin guardar el temporizador:

  ```python
  async def guardar():
      await background(escribir, datos.value)
      aviso.value = "Guardado"
      timeout(3000, lambda: aviso.set(""))
  ```
- Tras un `await` los cambios ya no van en el `batch` del manejador: cada asignación avisa por separado. Para aplicar varios a la vez, usa `with batch():` o asigna un único valor (p. ej. un `NamedTuple`). Ver [patrones.md](patrones.md#el-estado-a-medias-tras-un-await).
- Los errores de un manejador asíncrono se registran con archivo y línea, como los síncronos. Los de una `@task` quedan en `.error` para mostrarlos.
- El trabajo de `background` en curso no se puede interrumpir (es un hilo), pero su resultado se descarta si la tarea se canceló.

Ejemplo completo: `apps/examples/books` (busca en la API de Open Library).

### Temporizadores

```python
from janelkit import interval, timeout

@interval(250)                        # cada 250 ms mientras exista el componente
def muestrear():
    cpu.value = leer_cpu()

@interval(1000)
async def procesos():                 # async: el siguiente tic se salta si este no ha terminado
    lista.value = await background(leer_procesos)

ocultar = timeout(3000, lambda: aviso.set(""))
ocultar.restart()                     # vuelve a contar los 3 s (p. ej. con cada «escribiendo…»)
```

- Se detienen solos al desmontar el componente que los creó, también si se crearon tras un `await`. Fuera de un componente (en un servicio), viven hasta `.stop()`; JanelKit los mantiene vivos aunque no guardes la referencia.
- Cada ejecución agrupa sus cambios de estado en un solo `batch`: actualizar 50 métricas en un tic recalcula la interfaz una vez.
- `.active` es reactivo (`{#if muestrear.active}`); `.stop()`, `.start()` y `.restart()` lo controlan. Para cambiar el periodo: `muestrear.ms = 500` y `muestrear.restart()`.
- `when=` lo condiciona a algo reactivo: `@interval(33, when=visible)` con `visible = is_visible()` solo muestrea mientras el componente se ve (no en otra sección, en una página de debajo ni en un `{#hidden}`). Mientras la condición es falsa no cuenta; al volver a cumplirse, cuenta desde cero. `.stop()` le gana: parado a mano, no vuelve a arrancar solo.
- Un error en la función se registra con su nombre en el logger `janelkit` y el temporizador sigue.
- Para medir: `muestrear.runs`, `muestrear.skipped` (tics saltados) y `muestrear.last_duration` (segundos de la última ejecución, también la parte async). No son reactivos; `repr(muestrear)` los resume.

## Expresiones en la plantilla

`{expresión}` admite **expresiones** Python (no sentencias). Se evalúan en Python; QML nunca ejecuta lógica del usuario.

- **Desenvolvido automático:** un nombre que apunta a un `state`, `computed` o prop se sustituye por su valor. `{count + 1}` equivale a `count.value + 1`. Por eso, en la plantilla **no** se escribe `.value`.
- **Un `state` que es atributo** (un servicio con `self.status = state(...)`) se muestra con su valor y se actualiza: `{hub.status}`, `{f"cámara: {hub.status}"}`, `{hub.count:.1f}`, `{#if hub.ready}` y `{#each hub.items as item}` funcionan, porque al final se desenvuelve el resultado y `str()`/`format()` de un `state` dan su valor. Dentro de una operación hay que pedir el valor: `{hub.ready.value and "lista"}`, `{hub.items.value[0]}`; o asignarlo a un nombre del script (`status = hub.status`) y usar el nombre.
- Para modificar estado desde un evento se usa un [manejador en línea](#manejadores-de-eventos) (`on:click={count += 1}`) o una función del script. Dentro de una `lambda`, `count.set(0)` falla, porque `count` ya es un número; el error lo explica.
- Los nombres se resuelven **al evaluarse**, también dentro de `lambda`: un manejador de una fila de `{#each}` siempre ve el elemento actual de esa fila.
- Las dependencias se registran solas: cada binding se recalcula solo cuando cambia algo de lo que leyó, y solo se notifica a QML la propiedad afectada.
- **Nombres no definidos:** si una expresión usa un nombre que no define el script (ni un `{#each}` que la contenga, ni Python), es un error de compilación con sugerencia: `'cuont' no está definido — ¿quisiste decir 'count'?`. Si el script usa `from x import *` o `globals()`, esta comprobación se desactiva.
- `None` se muestra como texto vacío.
- **Formato** (solo en el texto, como en un f-string): `{cpu:.1f} %`, `{total:,}`, `{nombre!r}`, `{n:>4}`. Los dos puntos dentro de corchetes, paréntesis o cadenas no cuentan (`{lista[1:3]}`); una `lambda` necesita paréntesis.
- Si una expresión lanza una excepción al ejecutarse, se registra un error con archivo y línea en el logger `janelkit` y la aplicación sigue funcionando.

Las llaves pueden contener cadenas y diccionarios con llaves: `{ {"a": "}"}["a"] }`.

## Atributos

| Forma | Ejemplo | Significado |
|---|---|---|
| Literal | `title="Hola"` | Texto. En propiedades numéricas se admite `width="640"`. |
| Expresión | `width={640}`, `enabled={count > 0}` | Si es un literal Python se incrusta en el QML; si no, es un binding reactivo. |
| Booleano | `flat` | Equivale a `flat={True}`. |
| Abreviado | `{enabled}` | Equivale a `enabled={enabled}`. |
| `id` | `id="guardar"` | Se convierte en `objectName` (útil para pruebas). |
| `class` | `class="a b"`, `class={["tarjeta", variante, {"activa": sel}]}` | Clases para `<style>`. Con llaves admite texto, listas (anidables) y diccionarios `{clase: condición}`; se recalcula al cambiar lo que lee. Una clase sin reglas en `<style>` produce un aviso. |
| Clase condicional | `class:activa={sel == id}` | Aplica los estilos de `.activa` mientras la condición sea verdadera. `class:activa` equivale a `class:activa={activa}`. |
| Evento | `on:click={increment}`, `on:click={count += 1}` | Ver [manejadores de eventos](#manejadores-de-eventos). |
| Enlace | `bind:value={name}`, `bind:value={prefs.tema}` | Enlace bidireccional con un `state`: un nombre (no una variable de `{#each}` ni una prop) o un camino de atributos que termina en un `state` (el de un módulo, un objeto o una fila: `bind:checked={t.hecha}`). Si el final no es un `state`, se avisa al escribir. |

### Manejadores de eventos

`on:evento={...}` acepta dos formas:

| Forma | Ejemplos | Qué hace |
|---|---|---|
| **Función** | `on:click={guardar}`, `on:click={lambda: borrar(todo["id"])}`, `on:click={acciones["x"]}` | El valor es una función: se llama con los argumentos del evento que acepte (`def enviar():` y `def enviar(texto):` valen para `on:submit`). |
| **En línea** | `on:click={count += 1}`, `on:click={count = 0; query = ""}`, `on:click={todos.remove(todo)}`, `on:change={todo["done"] = event}` | Se ejecuta tal cual al ocurrir el evento. Admite llamadas y sentencias simples (asignaciones, `+=`…) separadas por `;`. `event` es el argumento del evento (o una tupla si hay varios). |

- Es función si la expresión es un nombre, un atributo, un índice, una `lambda` o un `x if c else y`; cualquier otra cosa (una llamada, una asignación) es en línea. Por eso `on:click={crear_manejador(x)}` **ejecuta** `crear_manejador(x)` al pulsar; no llama a lo que devuelve.
- Asignar a un nombre (`n = 1`, `n += 1`) solo es válido si es un `state` del script. Asignar a una prop o a una variable de `{#each}` es un error de compilación; para cambiar un elemento de la lista, modifícalo en el sitio (`todo["done"] = True`).
- `if`, `for`, `def` y otras sentencias compuestas no se admiten: escribe una función en el `<script>`.
- Dentro de un manejador en línea, `event` tapa cualquier variable del script con ese nombre.

## Texto

El contenido de `<text>`, `<button>` y `<checkbox>` es su texto: `<button>Clicks: {count}</button>`. Los espacios se colapsan como en HTML. Texto suelto dentro de un contenedor se convierte en un `<text>`.

`<text format="markdown">` interpreta Markdown (negrita, cursiva, enlaces, código, listas); `format="html"`, el subconjunto de HTML de Qt. Los enlaces muestran la mano al pasar por encima y, al pulsarlos, emiten `on:link` con la URL; si nadie escucha `on:link`, se abren en el navegador:

```html
<text format="markdown" on:link={abrir}>{mensaje["texto"]}</text>
```

`format="markdown"` **no interpreta HTML**: `<b>`, `<img>` o `<span style=…>` se muestran tal cual. Así, el texto de otras personas (un chat, una web) se puede mostrar directamente, sin escaparlo. Si quieres HTML, usa `format="html"`.

- Dentro de código (`` `list<int>` `` o un bloque con ```` ``` ````) el texto se ve exactamente como se escribió.
- Los enlaces automáticos con `<…>` tampoco se interpretan; las direcciones sueltas (`https://…`) y `[texto](url)` sí son enlaces.
- En casos raros en los que el código de un mensaje se lee de forma ambigua, puede verse una `\` antes de un `<` dentro del código; nunca pasa HTML.

### Texto seleccionable

Por defecto, un `<text>` no se puede seleccionar, como una etiqueta de escritorio. Con `selectable` (o `user-select: text` en el estilo) se selecciona arrastrando el ratón y se copia con Ctrl+C; con el foco en él, Ctrl+A lo selecciona todo. Sirve para números de pedido, mensajes de error o el texto de un chat. Los enlaces siguen funcionando, y un clic sin arrastrar sigue pulsando la caja con `on:click` que lo contenga:

```html
<text selectable>Pedido {pedido["id"]}</text>
```

Para copiar desde el código, `clipboard` de [`janelkit-desktop`](../packages/janelkit-desktop/README.md).

Límites de `selectable`: con `text-overflow: ellipsis` corta el texto en el borde, sin puntos suspensivos, y no tiene menú contextual. Además, crear un texto seleccionable cuesta unas 2,8 veces lo que uno normal (unos 0,35 ms frente a 0,12 ms), así que en listas de miles de filas conviene usarlo solo donde haga falta. Un texto sin `selectable` no paga nada.

## Bloques

### `{#if}`

```html
{#if count >= 5}
  <text>Cinco o más</text>
{:else if count > 0}
  <text>Algunos</text>
{:else}
  <text>Ninguno</text>
{/if}
```

Solo existe la rama activa: al cambiar de rama, los elementos de la anterior se **destruyen** y sus bindings dejan de escuchar el estado. Lo que se muestra de nuevo se crea desde cero (con estado local nuevo).

### `{#each}`

```html
{#each todos as todo, i (todo["id"])}
  <row>
    <text>{i + 1}. {todo["title"]}</text>
    <button on:click={lambda: remove(todo["id"])}>Eliminar</button>
  </row>
{:else}
  <text>No hay tareas.</text>
{/each}
```

- `todos` es cualquier expresión iterable; `todo` el elemento y `i` (opcional) su posición. Ambos solo existen dentro del bloque.
- `(clave)` identifica cada elemento. **Úsala siempre que la lista cambie**: al insertar, borrar o reordenar, cada fila conserva su identidad (su estado local, el foco, el texto escrito) y solo se crean, mueven o destruyen las filas afectadas. Sin clave, las filas se identifican por posición.
- Las claves deben ser únicas y hashables (números, textos, tuplas). Una clave repetida se informa como error y la fila se muestra igualmente.
- Si cambia un elemento con la misma clave, la fila se actualiza en su sitio.
- `{:else}` es opcional y se muestra cuando la lista está vacía.

#### Trasladar filas entre listas

Cuando un elemento pasa de una lista a otra (una tarjeta de una columna a otra), su fila **se traslada** en vez de destruirse y crearse de nuevo, si en el mismo cambio:

1. sale de un `{#each}` con clave,
2. entra en otra instancia de **la misma declaración** `{#each}` (el mismo sitio del mismo `.janel`: por ejemplo, la lista de tarjetas de dos `Columna`, o un `{#each}` dentro de otro `{#each}`),
3. con la misma clave.

```html
<!-- Columna.janel: cada columna es una instancia de este {#each} -->
{#each columna["tarjetas"] as t (t["id"])}
  <Tarjeta t={t} />
{/each}
```

```python
def mover(tarjeta, desde, hacia):           # un manejador: todo es un mismo cambio
    desde["tarjetas"].remove(tarjeta)
    hacia["tarjetas"].insert(0, tarjeta)
```

- Los componentes de la fila (`<Tarjeta>`) **conservan su estado**, sus `ref`, temporizadores y tareas; `on_mount` no se repite ni llega `on_destroy`. Si tenían el foco, lo recuperan en su nuevo sitio.
- Sus props y sus `on:` pasan a evaluarse en la fila nueva (con las variables de la columna destino). Lo obtenido con `inject` se conserva.
- La vista (QML) sí se crea de nuevo en la otra lista. Los elementos de la fila que no son componentes (`<flex>`, `<text>`) no tienen estado propio y también se recrean.
- *El mismo cambio* es un manejador (`on:click`, `on:drop`…), un `batch()` o un único cambio de una colección. Quitar en un manejador y añadir más tarde, tras un `await`, son dos cambios: la fila se destruye y se crea otra.
- No se traslada: entre declaraciones distintas (aunque usen el mismo componente y la misma clave), en `{#each}` sin clave, ni un componente que recibe contenido de slot. Si la misma clave aparece a la vez en las dos listas, son dos filas.

### Transiciones al entrar y salir

En el elemento raíz de un bloque `{#if}`, `{#each}` o `{#key}`:

```html
{#if aviso}
  <text class="aviso" transition:fade>{aviso}</text>
{/if}

{#each tareas as t (t["id"])}
  <row in:slide out:fade={120}>…</row>
{/each}
```

- `transition:x` anima la entrada y la salida; `in:x` y `out:x`, solo una. Tipos: `fade` (opacidad), `scale` (opacidad y escala), `slide` (opacidad y un pequeño desplazamiento). Duración opcional en milisegundos: `transition:fade={300}` (por defecto, 200).
- Al salir, la fila **deja de contar enseguida** (para las posiciones, el `{:else}`, etc.), pero su vista y sus bindings siguen vivos hasta que termina la animación; entonces se libera.
- En `<list>`, usa `<list animate>`: anima las filas que entran, salen y cambian de sitio.
- Para animar cambios de color, opacidad o tamaño, usa `transition` en `<style>` (ver [estilos.md](estilos.md)).

### `{#key}`

```html
{#key selected_id}
  <NoteEditor note={current} />
{/key}
```

Vuelve a crear el contenido cuando cambia el valor de la expresión. Útil para reiniciar el estado local de un componente (por ejemplo, el borrador de un formulario al cambiar de nota).

### `{#hidden}`

```html
{#hidden pestaña != "buscar"}
  <Buscador />
{/hidden}
```

Oculta el contenido mientras la condición es verdadera, **sin destruirlo**: al volver a mostrarlo conserva su estado (lo escrito, el desplazamiento, la página de una lista). Es lo contrario de `{#if}`, que destruye lo que deja de mostrarse.

- El contenido se crea la primera vez que la condición es falsa. Si empieza oculto, no cuesta nada hasta que se muestra.
- Después, ocultar y mostrar solo cambia su visibilidad: `on_mount` no se repite y `on_destroy` no llega hasta que se desmonta lo que contiene el bloque.
- Mientras está oculto no ocupa sitio y **lo que muestra espera**: sus textos, estilos, props, `{#if}` y `{#each}` no se recalculan aunque cambien los datos, ni se recoloca. Al volver a verse se ponen al día una sola vez, con los valores de ese momento.
- Lo que escribes en el script **sigue funcionando**: `effect`, `interval`, `timeout`, tareas y `on_destroy`. Un `effect` que guarda o sincroniza datos no se detiene por ocultar su componente. Para parar algo a propósito, `is_visible()` dice si el componente se ve, y `interval(ms, when=…)` lo usa directamente (ver [Temporizadores](#temporizadores)).
- Úsalo para lo que se alterna a menudo y es caro de crear o tiene estado que importa. Para lo demás, `{#if}` libera memoria.
- `{:else}` es lo contrario: se muestra mientras la condición es verdadera, y también se crea la primera vez que se muestra y después solo se oculta.
- Las transiciones (`transition:fade`, `in:`, `out:`) en la raíz del bloque se reproducen al mostrar y al ocultar; el contenido desaparece al terminar la salida.

```html
{#hidden cargando}
  <Resultados filas={filas} />
{:else}
  <flex transition:fade><Spinner /></flex>
{/hidden}
```

### Varios elementos en un bloque

Si una rama o una fila tiene varios elementos, se agrupan en un contenedor implícito con la orientación del contenedor padre, que hereda su dirección, separación y alineación. Normalmente no se nota; si necesitas controlar la disposición, envuélvelos tú en un `<column>` o `<row>`.

## Componentes

Un componente es otro archivo `.janel`. Se importa desde el script con sintaxis Python y se usa como una etiqueta que empieza por mayúscula:

```python
from components.TodoItem import TodoItem      # src/components/TodoItem.janel
from components import TodoItem               # equivalente
from .TodoItem import TodoItem                # relativo al archivo actual
```

```html
<TodoItem todo={todo} on:removed={remove} />
```

- Los imports absolutos se resuelven desde la carpeta del componente raíz (`src/`); los relativos, desde el archivo que importa.
- **Desde un paquete instalado:** si no está en `src/`, se busca en el paquete de Python con ese nombre (sin importarlo): `from janelkit_router import Pages` usa `Pages.qml` o `Pages.janel` de la carpeta del paquete, y `from mi_ui.formularios import Campo`, el de su subcarpeta. Así un paquete de `pip` reparte componentes. Dentro del paquete, sus componentes se importan entre sí con imports relativos (`from .Campo import Campo`) o con el nombre del paquete.
- El compilador compila los componentes importados (una vez cada uno) y valida su uso: props y eventos desconocidos, props obligatorias que faltan, etc. Los componentes pueden ser recursivos.

### Props y eventos (en el hijo)

```python
from janelkit import prop, event, state

todo = prop()          # obligatoria
compact = prop(False)  # opcional, con valor por defecto
removed = event()      # el padre escucha con on:removed={...}

editing = state(False) # estado local

def remove():
    removed.emit(todo.value["id"])     # admite argumentos posicionales y con nombre
```

- `prop()` y `event()` solo pueden declararse en el nivel superior del script: `nombre = prop(...)`.
- **Tipos:** una anotación declara el tipo de la prop: `edad: int = prop(0)`, `nota: str | None = prop(None)`, `etiquetas: list[str] = prop([])`. El compilador comprueba los valores literales que pasa el padre (`<Ficha edad="3" />` es un error: espera `int`). Al ejecutarse, cada valor que llega se comprueba con `isinstance` y, si no encaja, se registra un error que señala el uso en el padre (la aplicación sigue funcionando). `float` admite enteros; `list[str]` comprueba que sea una lista, no su contenido; las props sin anotación aceptan cualquier valor.
- Las props son **de solo lectura** en el hijo y reactivas: si el padre cambia el valor, se actualiza todo lo que las lee. En la plantilla se usan sin `.value`. Para editarlas, cópialas en un `state` o emite un evento para que el padre las cambie.
- Un evento sin manejador en el padre no hace nada.
- En el padre, un atributo con literal (`compact`, `title="x"`) se pasa como constante; una expresión (`todo={t}`) se reevalúa cuando cambia lo que lee.

### Slots: contenido entre etiquetas

Un componente puede recibir contenido del padre. En el hijo, `<slot />` marca dónde va; `<slot name="x" />` es un slot con nombre, y lo que haya dentro de `<slot>` es el contenido de reserva si el padre no pasa nada:

```html
<!-- components/Card.janel -->
<column class="card">
  <text class="title">{title}</text>
  <slot />
  <row class="footer"><slot name="footer"><text>Sin acciones</text></slot></row>
</column>
```

```html
<!-- el padre -->
<Card title="Tarea">
  <text>{todo["title"]}</text>
  <checkbox bind:checked={done}>Hecha</checkbox>
  <button slot="footer" on:click={borrar(todo)}>Eliminar</button>
</Card>
```

- El contenido se evalúa en el ámbito del **padre**: ve su estado, sus funciones y las variables de los `{#each}` que lo rodean, y es reactivo como el resto de su plantilla.
- Lo que no lleva `slot="..."` va al slot por defecto; varios elementos se apilan en columna. Un elemento con `slot="nombre"` va a ese slot (para varios, agrúpalos en un `<row>` o `<column>`).
- El contenido vive mientras viva el `<slot>` que lo muestra: si el hijo lo pone dentro de un `{#if}`, se crea y se libera con esa rama.
- Pasar contenido a un slot que el hijo no declara es un error de compilación que lista los slots disponibles.

### Estilos en la etiqueta del componente

Lo que la etiqueta lleva y el componente no declara como prop o evento se aplica a su **raíz**, si esta es una caja (`<flex>`, `column` o `row`): así un componente se usa como un elemento más.

```html
<Boton text="Guardar" class="primary" on:click={guardar} disabled={ocupado} ref={boton} />
<Tarjeta class="celda" title="..." />
```

- Pasan a la raíz: `class` y `class:x={...}`, `style`, `id`, `label`, `title`, `tabindex`, `disabled`, `as`, `flex`, `width`, `height`, `visible`, `ref` y los eventos nativos (`on:click`, `on:keydown`, `on:contextmenu`…).
- Las reglas de `<style>` del padre se aplican a la raíz, también sus estados: `.celda:hover` en el padre reacciona al ratón sobre la raíz del componente. Lo que fija la etiqueta gana a los estilos propios del componente.
- Las clases de la etiqueta activan además las reglas del componente que las combinan con la clase de su raíz: con `<Boton class="primary">`, la regla `.boton.primary` de `Boton.janel` se aplica.
- `ref` en la etiqueta apunta a la raíz (`boton.focus()` enfoca el `<flex>` del botón); `disabled` activa `:disabled` en la raíz.
- Si el componente declara una prop o un evento con ese nombre, gana lo declarado.
- `inherit_attrs = False` en el script del componente lo desactiva: la etiqueta solo admite sus props y eventos, y `class`, `id`, `flex`, `width`, `height` y `visible` van a una caja exterior que lo envuelve, como cuando la raíz no es una caja.
- Si la raíz no es una caja (un `<button>`, varios elementos, un `{#if}`), esos seis atributos van a una **caja exterior** que lo envuelve, y un evento sin declarar es un error de compilación.

### Ciclo de vida

- Cada uso de un componente crea una instancia con su propio script y estado.
- Al desmontarse (rama `{#if}` inactiva, fila de `{#each}` eliminada, recarga), se liberan sus bindings, sus props dejan de escuchar al padre y sus hijos se desmontan también.

```python
from janelkit import on_mount, on_destroy, effect, ref

campo = ref()                 # <textfield ref={campo} />

@on_mount                     # la vista ya existe (también la de los hijos)
def preparar():
    campo.focus()
    timer = iniciar_reloj()
    return timer.stop         # opcional: se llama al desmontar

on_destroy(lambda: print("adiós"))

def sincronizar():
    conexion = abrir(servidor.value)
    return conexion.close     # limpieza: antes de volver a ejecutarse y al desmontar

effect(sincronizar)
```

- `on_mount` se ejecuta una vez, cuando la vista del componente existe; los hijos antes que el padre. `on_destroy` y las limpiezas se ejecutan al desmontar, en orden inverso al de registro.
- Un `effect` creado en el script se libera con el componente. Si su función devuelve otra función, es su limpieza.
- Estas funciones (y `provide`/`inject`) solo pueden llamarse mientras se ejecuta el script del componente, no más tarde desde un evento.
- Los errores dentro de ellas se registran con el archivo del componente y no cierran la aplicación.

### Referencias a elementos

`ref={nombre}` en un elemento asigna ese elemento a `nombre = ref()` del script. `nombre.value` es reactivo: vale `None` hasta que el elemento existe y vuelve a `None` cuando se destruye (por ejemplo, al cerrarse un `{#if}`).

| Método | Qué hace |
|---|---|
| `focus()` / `blur()` | Da o quita el foco del teclado. |
| `select_all()` | Selecciona todo el texto (`textfield`, `textarea`). |
| `exists` | `True` si el elemento existe. |
| `value` | El objeto Qt Quick (`QQuickItem`). Es interfaz de Qt, no de JanelKit: úsalo como último recurso. |

Los métodos no hacen nada si el elemento aún no existe. Dentro de un `{#each}`, la referencia apunta a la última fila creada.

### Contexto: compartir valores con los descendientes

```python
# En un componente antecesor
from janelkit import provide, state
sesion = state({"usuario": "ana"})
provide("sesion", sesion)

# En cualquier descendiente, a cualquier profundidad
from janelkit import inject
sesion = inject("sesion")            # LookupError si nadie la provee
tema = inject("tema", "claro")       # con valor por defecto
```

- `inject` devuelve el valor del antecesor **más cercano** que lo provee: un componente intermedio puede proveer otro valor para su subárbol.
- Lo que se comparte es el objeto tal cual: para que sea reactivo, comparte un `state` (o un objeto que los contenga).
- Para estado global de toda la aplicación sigue valiendo un módulo Python (`services/store.py`). El contexto es para valores que dependen de dónde está el componente en el árbol.

## Datos compartidos y estado que se recuerda

Lo que comparten varias vistas o ventanas va en un **store**, y lo que la aplicación debe recordar al volver a abrirse, en un `persisted` o un store con `persist=`. Los dos son del paquete [`janelkit-store`](../packages/janelkit-store/README.md):

```python
from janelkit_store import persisted, store, use

tema = persisted("tema", "claro")      # un state que se guarda solo

@store(persist="carrito")
class Carrito:
    items: list[dict] = []

    def agregar(self, item):
        self.items.append(item)

carrito = use(Carrito)                 # la misma instancia en todas las vistas y ventanas
```

Ejemplos: `apps/examples/carrito` (dos ventanas con el mismo store) y `apps/examples/preferencias` (`persisted`).

## Vídeo: `<video>` y `Frames`

Para mostrar vídeo a tiempo real (una cámara, un vídeo procesado, una simulación) los fotogramas no pasan por la reactividad: van por un `Frames`, que se puede alimentar desde cualquier hilo, y `<video>` muestra siempre el más reciente. El patrón completo, con cámara y modelo, está en [patrones.md](patrones.md#fotogramas-y-resultados-van-por-caminos-distintos).

```python
import threading
from janelkit import Frames, background, on_mount, spawn, state

frames = Frames(color="bgr")       # "bgr" para OpenCV; por defecto "rgb"
caras = state([])

def capturar():                    # en un hilo propio: aquí no se toca el estado
    while True:
        ok, img = camara.read()
        frames.push(img)

async def detectar():
    async for img in frames:       # el más reciente cada vez que el modelo queda libre
        caras.value = await background(modelo, img)

on_mount(lambda: (threading.Thread(target=capturar, daemon=True).start(), spawn(detectar())))

def pct(valor, eje):               # de píxeles de la imagen a % de la capa (eje 0: x, 1: y)
    tamaño = frames.size or (1, 1)
    return f"{100 * valor / tamaño[eje]}%"
```

```html
<video source={frames} flex={1} label="Cámara">
  {#each caras as c}
    <flex class="cara" style={{"left": pct(c[0], 0), "top": pct(c[1], 1), "width": pct(c[2], 0), "height": pct(c[3], 1)}} />
  {/each}
</video>
<text>{frames.fps:.0f} fps</text>
```

- `frames.push(img)` acepta un array de numpy o cualquier objeto con el protocolo de búfer, de bytes y forma alto × ancho (gris), alto × ancho × 3 (`color="rgb"` o `"bgr"`) o × 4 (`"rgba"`, `"bgra"`); también un `QImage`. Copia la imagen (el búfer se puede reutilizar) y la convierte en el hilo que llama, no en el de la interfaz.
- Si llegan fotogramas más deprisa de lo que la interfaz los entrega, se saltan: nunca se encolan. `<video>` y `async for` reciben siempre el último.
- `async for img in frames` da el objeto que se pasó a `push`. Con `background()`, el modelo corre en otro hilo y la vista previa no espera por él. `await frames.next()` espera al próximo.
- `frames.size` (`(ancho, alto)` o `None`) y `frames.fps` son reactivos. `frames.latest()` es el último fotograma; `frames.clear()` deja la vista en blanco.
- Los hijos de `<video>` van en una caja con `position: relative` del tamaño exacto de la imagen que se ve, así que los porcentajes son de la imagen, también con `fit="contain"` (bandas) o `"cover"` (recortada). Para un espejo (cámara frontal), voltea la imagen antes de `push` (`cv2.flip(img, 1)`): así las coordenadas siguen coincidiendo.
- Abrir cámaras no es del núcleo: con OpenCV (`cv2.VideoCapture`) o QtMultimedia, en un hilo propio.

## Listas grandes: `<list>`

`<scroll>` crea todas sus filas. Para cientos o miles de elementos, `<list>` solo crea las que se ven (más un margen):

```html
<list class="lista">
  {#each tareas as tarea (tarea["id"])}
    <row class="fila">
      <checkbox bind:checked={...}>{tarea["titulo"]}</checkbox>
    </row>
  {/each}
</list>
```

- Debe contener exactamente un `{#each}` (con clave, como siempre). El resto funciona igual: claves, índice, manejadores, componentes dentro de la fila y colecciones reactivas.
- Cada fila se crea —su parte Python y su vista— la primera vez que se hace visible. Su parte Python se conserva hasta que la fila sale de la lista; la vista se destruye al salir de pantalla y se vuelve a crear al volver. Por eso, lo que el usuario esté escribiendo en una fila debe ir a un `state` (`bind:`), no quedarse solo en el control.
- Mientras una fila no tiene vista, lo que muestra no se recalcula (como en `{#hidden}`): se pone al día una vez, al volver a verse. Sus `effect`, temporizadores y tareas siguen funcionando.
- Si todas las filas leen un mismo estado (la fila elegida, la selección de una hoja de cálculo), calcula en cada fila con un `computed` la parte que le toca: un binding que solo lee `computed` no se reevalúa si su valor no cambió, así que al cambiar la selección solo se actualizan las filas afectadas.

  ```python
  @computed
  def elegida():          # en el componente de la fila
      return seleccion.value == fila.value["id"]
  ```
- Las filas ocupan el ancho de la lista. Admite `gap`, `padding`, fondo, borde y radio desde `<style>`; por defecto ocupa el espacio libre (`flex: 1`).
- Añadir filas (al final, al principio o en medio, en cualquier cantidad) se aplica por bloques y la vista conserva su posición. Borrar o mover pocas filas se aplica una a una (con `animate`, animado). A partir de 64 borrados o movimientos a la vez (ordenar, invertir, sustituir la lista) se aplican de golpe: las filas visibles se vuelven a crear y la vista conserva su posición (la fila que estaba arriba, por su número, sigue arriba), como al reordenar una tabla.
- `{:else}` no está disponible dentro de `<list>`: muestra el estado vacío con un `{#if}` fuera.

### Desplazamiento

Para chats, registros y cualquier lista que crece:

```html
<list follow ref={lista} on:top={cargar_anteriores} on:scroll={al_desplazar}>
  {#each mensajes as m (m["id"])}
    <Mensaje msg={m} />
  {/each}
</list>
```

- **`follow`**: la lista empieza abajo; si el usuario está abajo, sigue a las filas nuevas (también cuando una fila crece, p. ej. al cargar una imagen); si subió a leer, no se mueve. Al insertar filas por arriba (historial), lo que se estaba viendo se queda en el mismo sitio de la pantalla.
- **`on:top`** y **`on:bottom`**: el usuario llegó al principio o al final (solo si el contenido no cabe entero).
- **`on:scroll`**: como mucho una vez por fotograma, con `event = {"top": bool, "bottom": bool, "y": píxeles desde arriba, "height": alto del contenido}`. Sirve para saber si el usuario está abajo (`on:scroll={abajo = event["bottom"]}`).
- Con `lista = ref()`: `lista.scroll_to_end()` (y con `follow` vuelve a seguir las nuevas), `lista.scroll_to_start()` y `lista.scroll_to(índice)` (lo justo para que se vea esa fila).

`<scroll>` admite lo mismo, para contenido que no es una lista de filas iguales (un registro corto, un formulario largo, un documento):

```html
<scroll follow ref={zona} on:bottom={leido = True}>
  ...
  <text ref={aviso}>Condiciones</text>
</scroll>
```

- `follow`, `on:top`, `on:bottom` y `on:scroll` funcionan como en `<list>`.
- `zona.scroll_to_start()`, `zona.scroll_to_end()` y `zona.scroll_to(aviso)`: con el `ref` de un elemento de dentro, desplaza lo justo para que se vea entero (si ya se ve, no se mueve).

Con 10 000 filas, crear la lista tarda unos 40 ms (ver `python tools/bench.py`).

## Accesibilidad

- **Teclado:** Tab y Mayús+Tab recorren los controles en el orden de la plantilla. Un `column`/`row` con `on:click` también entra en ese recorrido y se activa con Espacio o Intro, como un botón. El foco se ve siempre (borde del color `--primary`).
- **Lectores de pantalla:** los controles anuncian su texto (botones, casillas, opciones, pestañas) o su `placeholder` (campos). `label="..."` en cualquier elemento fija o sustituye ese nombre; úsalo en campos sin texto visible y en tarjetas pulsables. `image` usa `alt`.
- **Atajos:** `<shortcut>` para las acciones frecuentes.

```html
<textfield bind:value={busqueda} placeholder="Buscar…" label="Buscar en las notas" />
<row class="tarjeta" on:click={abrir(nota)} label={f"Abrir {nota['titulo']}"}>…</row>
<image src="logo.png" alt="Logotipo de la empresa" />
```

## Idioma y dirección de escritura

`janelkit.locale` es el idioma de la interfaz: `locale.set("ar")` refleja toda la interfaz (filas, alineación del texto, indicadores de los controles) en los idiomas de derecha a izquierda y hace que Qt use ese idioma en sus controles. `locale.rtl` dice si el activo se escribe de derecha a izquierda. Es reactivo.

Las traducciones (catálogos, plurales, formatos de número y fecha) son del paquete [`janelkit-i18n`](../packages/janelkit-i18n/README.md), cuyo `i18n.set()` cambia también este idioma. Ejemplo: `apps/examples/idiomas`.

## Navegación entre pantallas

Las pilas de páginas (`pages`, `<Pages>`), las secciones (`sections`, `<Sections>`), `navigation()` y los resultados con `await nav.push(...)` son del paquete [`janelkit-router`](../packages/janelkit-router/README.md):

```python
from janelkit_router import pages, Pages
from pages.Inicio import Inicio

nav = pages(Inicio)
```

```html
<Pages stack={nav} transition:slide />
```

## Preguntar antes de salir

`before_leave(fn)` en el script de un componente registra una pregunta: si `fn()` devuelve `False`, no se sale. Puede ser `async`, para preguntar con un diálogo:

```python
from janelkit import before_leave
from janelkit_desktop import dialogs

@before_leave
async def salir():
    return not cambios.value or await dialogs.confirm("Hay cambios sin guardar. ¿Salir igualmente?")
```

- Se consulta al cerrar con la X la ventana que muestra el componente; cerrar la ventana principal consulta también las ventanas que abrió. Cerrar desde el código (`ventana.close()`) no pregunta.
- También lo consulta un anfitrión que va a descartar el componente: en `janelkit-router`, `pop`, `back`, `replace`, `reset` y Alt+← sobre la página que lo contiene.

## Varias ventanas

Cualquier componente importado se puede abrir en una ventana propia:

```python
from janelkit import open_window
from components.Ajustes import Ajustes      # un .janel (con <window> como raíz, o sin ella)

def abrir_ajustes():
    ventana = open_window(Ajustes, usuario=usuario, on_guardado=guardar, modal=True)
```

- Las palabras clave son las **props** del componente; las que empiezan por `on_`, sus **eventos** (`on_guardado` → `guardado = event()`). Una prop desconocida es un `TypeError` que lista las disponibles. Un `state` pasado como prop sigue siendo reactivo en la ventana.
- La ventana hereda el **contexto** (`inject`) del componente que la abre, queda por delante de su ventana y se **cierra sola** cuando ese componente se desmonta. Al cerrar la ventana principal se cierran las que abrió.
- `modal=True` bloquea la ventana que la abrió mientras está abierta. `theme="dark"` le da un tema propio (también a los componentes que contiene), sin cambiar el de la aplicación.
- Devuelve un objeto con `is_open` (reactivo: úsalo en la plantilla o en un `computed`), `close()`, `focus()` e `instance`.
- `single=True`: si ya hay una ventana abierta de ese componente, la trae al frente y la devuelve en vez de abrir otra (las props nuevas no se aplican). Sirve para «Ajustes» o «Acerca de», que se abren desde un menú o un atajo.

## Diálogos y portapapeles

Son del paquete [`janelkit-desktop`](../packages/janelkit-desktop/README.md): diálogos nativos que se esperan con `await` (`await dialogs.open_file(...)`, `await dialogs.confirm(...)`) y el portapapeles reactivo.

## Elementos propios en QML

Cuando JanelKit no ofrece un control, se puede escribir en QML y usarlo como un elemento más. Un archivo `.qml` del proyecto se importa igual que un componente:

```qml
// src/widgets/Meter.qml
import QtQuick

Rectangle {
    id: root
    property real value: 0          // prop: value={...}  y  bind:value={...}
    property real max: 5
    readonly property bool full: value >= max   // solo lectura: no se puede pasar
    signal picked(int step)         // evento: on:picked={...}  (event = step)
    implicitWidth: 320; implicitHeight: 14
    color: jktheme.border           // los tokens del tema están en `jktheme`
    // ...
}
```

```html
<script>
from widgets.Meter import Meter
</script>
<Meter value={count} max={5} on:picked={count = event} />
```

- El compilador lee las `property` y `signal` del **objeto raíz** del archivo (sin ejecutarlo) y valida el uso: una prop o un evento que no existe es un error con sugerencia.
- Disposición: sin `width`/`height` toma su tamaño natural (`implicitWidth`/`implicitHeight`), como un botón. `flex={1}` lo hace crecer en el eje del contenedor igual que a los elementos de JanelKit (`<LineChart flex={1} />` ocupa el alto libre de una columna).
- Props: las propiedades que no son `readonly`, con su tipo (`string`, `int`, `real`, `bool`, `color`; el resto acepta cualquier valor). Además, las comunes: `width`, `height`, `flex`, `visible`, `enabled`, `opacity`, y `id`, `class`, `ref`.
- Eventos: cada `signal`. El manejador recibe sus parámetros (`def elegido(step):`; en línea, `event`).
- `bind:prop={estado}` funciona con cualquier propiedad escribible: los cambios que haga el QML (también por asignación, `root.value = 3`) vuelven al `state`. Los números de QML (`real`) llegan como `float`.
- `janel dev` reinicia la aplicación al guardar el `.qml` (Qt no siempre vuelve a leer en el mismo proceso un `.qml` ya cargado).
- Las `property` y `signal` cuyo nombre empieza por `jk` son internas: no se pueden pasar ni escuchar desde la plantilla.
- **Montar componentes desde Python.** Un elemento cuya raíz es `JkDeck` (`import Janel`) es un mazo: muestra uno de sus hijos, que ocupa todo el sitio; crece solo (`flex: 1`) y admite `transition:`. Si además declara `property JkHost nombre`, `<Elemento nombre={objeto} />` le pasa el elemento a `objeto`, un `janelkit.ext.Host`, que monta componentes dentro con `container.mount(...)`. Así están hechos `<Pages>` y `<Sections>` de `janelkit-router` ([api.md](api.md#janelkitext-extensiones)).
- El QML es **interfaz de Qt, no de JanelKit**: su contenido no está cubierto por la política de versiones, y sus errores se muestran tal como los da Qt. Son de JanelKit `jktheme`, `JkDeck` (su `currentIndex` y las propiedades de `transition:`) y `JkHost`.

**Tipos escritos en Python.** Un `QQuickItem` (o `QQuickPaintedItem`) registrado con `@QmlElement` se usa desde un `.qml` como cualquier tipo QML (`import dials` → `PyDial { ... }`). El módulo que lo registra debe importarse **antes** de `run()`, en `main.py`, porque Qt resuelve los imports al cargar la vista.

Ejemplo: `apps/examples/counter` (`src/widgets/Meter.qml`).

## Elementos disponibles

**Elementos del núcleo en minúscula; componentes en mayúscula.** Como en HTML, las etiquetas en minúscula son lo que da la plataforma: los elementos de JanelKit, todos en las tablas de esta sección (`<window>`, `<flex>`, `<text>`, `<button>`, `<checkbox>`…). Una etiqueta en mayúscula es un componente que el script importa: un `.janel` (`<TodoItem>`) o un `.qml` ([Elementos propios en QML](#elementos-propios-en-qml)). Así un componente propio puede llamarse `Button` sin chocar con `<button>`. Una etiqueta en minúscula desconocida es un error que lista los elementos del núcleo.

Los nombres de 0.1 en mayúscula (`<Text>`, `Text { … }` en `<style>`) aún compilan, con un aviso, si el script no importa un componente con ese nombre; dejan de valer en 0.3. `janel migrate` actualiza el proyecto ([desarrollo.md](desarrollo.md#comandos)).

`<flex>` es la caja con la que se construyen otros elementos sin escribir QML (como `<div>` en la web):

| Caja | Qt Quick | Propiedades | Eventos |
|---|---|---|---|
| `flex` | caja propia con el motor flexbox (`JkFlex`) | `direction` (`row` por defecto, `column`, `row-reverse`, `column-reverse`), `wrap`, `gap`, `padding`, `align` (`align-items`), `justify` (`justify-content`), `as`, `tabindex`, `disabled`, `title`, `checked`, `selected`, `expanded`, `draggable`, `style` | `on:click`, `on:dblclick`, `on:contextmenu`, `on:pointerdown`, `on:pointerup`, `on:pointermove`, `on:pointerenter`, `on:pointerleave`, `on:wheel`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur`, `on:resize`, `on:dragstart`, `on:dragover`, `on:drop`, `on:dragend` |

`<flex>` es la caja de la web: fila por defecto, `align-items: stretch` y el resto del flexbox de CSS en `<style>` (`flex-wrap`, márgenes y `margin: auto`, `space-between`, `order`, `%`, bordes por lado, radio por esquina, `overflow`), con estados (`:hover`, `:pressed`, `:focus-visible`…), selectores de descendiente (`.tarjeta:hover .acciones`), sombra, `outline`, `transform` y `cursor`. Ver [estilos.md](estilos.md); hay botones, tarjetas, menús y diálogos hechos con `<flex>` en `apps/examples/flex`. Los atributos de texto se comprueban al compilar: `<flex direction="diagonal">` es un error.

### Eventos de las cajas

`<flex>`, `column` y `row` reciben los eventos de la tabla. Como en la web, un evento **sube** desde el elemento más profundo bajo el puntero (o desde el que tiene el foco, para las teclas) hacia sus contenedores. El manejador recibe un objeto con lo ocurrido (`PointerEvent`, `KeyEvent`, `WheelEvent`, `FocusEvent`, `ResizeEvent`; ver [api.md](api.md)) y dos métodos:

- `event.stop()`: los contenedores de fuera no lo reciben (el ✕ de un chip no elige el chip).
- `event.prevent()`: Qt no hace lo que haría (escribir la tecla en un campo, desplazar con la rueda, pulsar con Espacio).

```python
def tecla(event):
    if event.key == "ArrowDown":
        siguiente()
        event.prevent()
```

- `on:pointerenter` y `on:pointerleave` no suben (como en la web). `on:focus`/`on:blur` tampoco; `event.reason` dice si llegó con Tab, con un clic o por código.
- `on:click` sigue siendo el de siempre: si un control de Qt (un `<button>`) se queda el clic, la caja que lo contiene no lo recibe. Entre cajas, sí sube (y se corta con `stop()`). Desde el teclado (Espacio o Intro) llega con `event.pointer == "keyboard"`.
- `on:contextmenu`: clic derecho o tecla de menú (sin pulsación larga).
- `on:resize` llega una vez por vuelta del bucle de eventos, aunque el tamaño cambie varias veces.
- `on:pointermove` solo se envía si hay manejador: es frecuente.
- `prevent()` y `stop()` solo cuentan antes del primer `await` de un manejador `async def`. `prevent()` no impide que se dispare un `<shortcut>`.

### Arrastrar y soltar

Una caja con `draggable` se arrastra al pulsarla y mover el puntero más que la distancia de arrastre del sistema (una pulsación corta sigue siendo un clic). Lo que se arrastra es un valor de Python:

```html
<flex class="tarjeta" draggable on:dragstart={event.data = tarjeta["id"]}>…</flex>

<flex class="columna" on:drop={mover(event.data, columna)}>…</flex>

<style>
.tarjeta:dragging { opacity: 0.4; }      /* la original, mientras su imagen sigue al puntero */
.columna:drag-over { background: var(--surface-alt); }
</style>
```

| Evento | Dónde | Cuándo |
|---|---|---|
| `on:dragstart` | la caja `draggable` y sus antecesores | Empieza el arrastre. Pon `event.data`; `event.prevent()` lo cancela. |
| `on:dragover` | las cajas bajo el puntero | El puntero se mueve; `event.x`/`event.y` dicen dónde se soltaría. |
| `on:drop` | la caja con `on:drop` más profunda bajo el puntero (y las de fuera si no hace `stop()`) | Se suelta. Solo las cajas con `on:drop` son destino y se marcan con `:drag-over`. |
| `on:dragend` | la caja `draggable` y sus antecesores | Termina, con `event.dropped` (`False` si se soltó fuera o con Escape). Si `on:drop` quitó la caja, no llega. |

- Todos reciben un `DragEvent`: lo de `PointerEvent` más `.data` y `.dropped`.
- Mientras se arrastra, Escape cancela y no hay clic al soltar. Cerca del borde (40 px) de una zona con desplazamiento (`<list>`, `<scroll>`, `overflow: auto`), esta avanza sola.
- Funciona dentro de una ventana; no entre ventanas ni desde otras aplicaciones (archivos).
- En pruebas: `Element.drag_to(destino)` de `janelkit.inspect`.

### Papel, teclado y accesibilidad: `as`

`as` dice qué es la caja para el teclado y los lectores de pantalla. No cambia el aspecto.

| `as` | Tab | Teclado | Para el lector de pantalla |
|---|---|---|---|
| (sin `as`) | con `on:click`, como `button` | ídem | ídem |
| `box` | no | — | se ignora |
| `button` | sí | Espacio (al soltar) o Intro → `on:click` | botón (`:pressed`, `:disabled`) |
| `link` | sí | Intro | enlace |
| `checkbox`, `switch` | sí | Espacio | casilla, con `checked` |
| `tab`, `menuitem`, `option` | con `tabindex` | Espacio o Intro; las flechas las programa el componente con `on:keydown` | con `selected` |
| `listitem`, `list`, `menu`, `tablist`, `dialog`, `heading`, `region` | no | — | su papel |

- `tabindex={0}` mete la caja en el orden de Tab; `tabindex={-1}` la saca (sigue pudiendo recibir el foco con `ref.focus()`).
- `disabled={True}`: no recibe eventos, sale del orden de Tab y activa `:disabled`.
- `title="..."`: descripción emergente al dejar el ratón encima, también para los lectores de pantalla.
- Una caja con papel de botón (o con `on:click`) sin texto ni `label` produce una advertencia: el lector de pantalla no sabría qué es.
- El anillo de foco por defecto (un borde del color `--primary`) se sustituye con una regla `outline` (`.boton:focus-visible { outline: 2px solid var(--primary) }`) o se quita con `outline: none`.

Propiedades comunes a todos salvo `window`: `width`, `height`, `flex`, `visible`, `enabled`, `opacity` y `label` (nombre para lectores de pantalla; ver [Accesibilidad](#accesibilidad)).

| Elemento | Qt Quick | Propiedades | Eventos | `bind:` |
|---|---|---|---|---|
| `window` | `ApplicationWindow` | `title`, `width`, `height`, `minWidth`, `minHeight`, `background`, `screen`, `fullscreen` | `on:activate`, `on:deactivate` | — |
| `column` | `<flex direction="column">` | `gap`, `padding` | `on:click` | — |
| `row` | `<flex direction="row">` | `gap`, `padding` | `on:click` | — |
| `scroll` | `ScrollView` + columna | `gap`, `padding`, `follow` | `on:top`, `on:bottom`, `on:scroll(info)` | — |
| `list` | `ListView` | `gap`, `padding`, `animate`, `follow` | `on:top`, `on:bottom`, `on:scroll(info)` | — |
| `text` | `Label` | `text`, `color`, `format` (`plain`, `markdown`, `html`), `selectable` | `on:link(url)` | — |
| `button` | `Button` | `text`, `variant` (`default`, `primary`, `danger`, `ghost`), `flat` | `on:click` | — |
| `textfield` | `TextField` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:submit(texto)`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur` | `bind:value` |
| `textarea` | `TextArea` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur` | `bind:value` |
| `checkbox` | `CheckBox` | `checked`, `text` | `on:change(marcado)` | `bind:checked` |
| `switch` | `Switch` | `checked`, `text` | `on:change(activado)` | `bind:checked` |
| `slider` | `Slider` | `value`, `min` (0), `max` (100), `step` | `on:change(valor)` | `bind:value` |
| `select` | `ComboBox` | `options`, `value`, `placeholder` | `on:change(valor)`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur` | `bind:value` |
| `radiogroup` | `RadioButton`s | `options`, `value`, `horizontal` | `on:change(valor)` | `bind:value` |
| `tabs` | `TabBar` | `options`, `value` | `on:change(valor)` | `bind:value` |
| `progressbar` | `ProgressBar` | `value`, `max` (1), `indeterminate` | — | — |
| `image` | `Image` | `src`, `fit` (`contain`, `cover`, `fill`, `none`), `alt` | — | — |
| `video` | `VideoOutput` | `source` (un `Frames`), `fit` (`contain`, `cover`, `fill`) | — | — |
| `shortcut` | `Shortcut` | `keys` | `on:activate` | — |
| `spacer` | `Item` | — | — | — |

- **`list`** es una lista virtualizada para colecciones grandes; ver [Listas grandes](#listas-grandes-list) y [Desplazamiento](#desplazamiento).
- **`window`**: `on:activate` y `on:deactivate` avisan cuando la ventana pasa a primer plano o deja de estarlo (para marcar como leído, o pausar lo que solo importa mientras se mira).
- **`window` en otra pantalla:** `screen={i}` la abre en la pantalla `i` de `screens` (o `screen={"nombre"}`, por su nombre), centrada; `fullscreen={bool}` la pone a pantalla completa o la saca. Los dos son reactivos: cambiar `screen` estando a pantalla completa mueve la ventana a la otra pantalla y la deja a pantalla completa allí. Si la pantalla no existe (un proyector desconectado), la ventana se queda donde está y vuelve a colocarse cuando se conecta. `screens` es la lista reactiva de pantallas (`Screen`: `index`, `name`, `width`, `height`, `x`, `y`, `primary`, `scale`):

  ```html
  <script>
  from janelkit import screens, computed
  proyector = computed(lambda: 1 if len(screens.value) > 1 else 0)
  </script>
  <window title="Proyección" screen={proyector} fullscreen={True}>…</window>
  ```
- **Opciones** (`select`, `radiogroup`, `tabs`): `options` es una lista de textos (`["rojo", "verde"]`) o de diccionarios `{"label": "Mediano", "value": 2}`; `value` es el valor elegido. La elección del usuario se ve al momento; si Python cambia `value`, manda Python.
- `tabs` es solo la barra: el contenido de cada pestaña se elige con `{#if pestaña == "general"}`.
- `image`: `src` puede ser una ruta relativa a la carpeta del `.janel`, una ruta absoluta o una URL (`https:`, `qrc:`, `data:`). Sin `width`/`height`, toma el tamaño de la imagen.
- `video` muestra los fotogramas de un `Frames` ([Vídeo](#vídeo-video-y-frames)). Sus hijos van en una capa sobre la imagen.
- `shortcut` no ocupa espacio: escucha el teclado de su ventana mientras existe (`<shortcut keys="Ctrl+S" on:activate={guardar} />`; teclas como en Qt: `Ctrl+Shift+N`, `F5`, `Esc`). Dentro de un `{#if}`, solo está activo con la rama.
- `textarea` emite `on:input` solo con los cambios del usuario, no con los que llegan de Python.
- **Teclado y foco en los campos** (`textfield`, `textarea`, `select`): `on:keydown`, `on:keyup`, `on:focus` y `on:blur` funcionan como en `<flex>` ([eventos](#eventos-de-las-cajas)): suben a los contenedores, `event.stop()` corta la subida y `event.prevent()` hace que la tecla no llegue al campo (no se escribe). Por ejemplo, Escape para cancelar una edición y guardar al salir del campo:

  ```html
  <textfield bind:value={nombre} on:keydown={event.key == "Escape" and cancelar()} on:blur={guardar()} />
  ```
- `column` y `row` son atajos de `<flex>` con sus valores por defecto de siempre: en una columna, texto y cajas ocupan el ancho y los controles se quedan a la izquierda; en una fila, los hijos se centran en vertical; solo encoge lo que tiene `flex`. Admiten todo el flexbox de `<flex>` en `<style>` (también `flex-wrap`). Si solo usan lo básico (`gap`, `padding`, alineación, márgenes fijos, un hijo con `flex`), se colocan con un layout de Qt, más rápido; no hay que hacer nada para ello.
- `<flex>`, `column` y `row` con `on:click` se pueden pulsar en toda su superficie (tarjetas, filas): muestran cursor de mano y un resaltado al pasar el ratón. Un botón dentro sigue funcionando por separado.
- `scroll` es una columna con desplazamiento vertical; por defecto ocupa el espacio libre (`flex: 1`). Para moverlo desde el código, ver [Desplazamiento](#desplazamiento).
- `spacer` ocupa el espacio libre y empuja a sus hermanos hacia los extremos.
- Los campos (`textfield`, `textarea`, `slider`, `select`, `radiogroup`, `tabs`) y los demás elementos sin contenido (`image`, `progressbar`, `spacer`, `shortcut`, `Pages`, `Sections`) se escriben con cierre automático: `<textfield bind:value={nombre} />`. Un campo no tiene texto dentro: lo escrito o elegido es su `value`. `<textfield>Pan</textfield>` y `<textfield></textfield>` son errores de compilación.
- `width`/`height` fijan el tamaño preferido dentro del contenedor; `flex={1}` hace crecer el elemento en el eje del contenedor. Ver [estilos.md](estilos.md#disposición).

Un elemento, propiedad, evento o directiva desconocidos producen un error con las opciones válidas y, si hay uno parecido, «¿quisiste decir…?».

## Diagnósticos

Todos los errores siguen el formato `archivo:línea:columna: error: mensaje`, con la línea de origen, un `^` y, cuando existe, una sugerencia. Si Qt rechaza el QML generado, el error se remite al elemento `.janel` correspondiente y muestra además la línea QML implicada.

Para depurar: `janel parse src/App.janel` muestra el AST, `janel compile src/App.janel` el QML generado y `janel build` valida todos los componentes del proyecto.
