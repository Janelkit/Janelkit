# Formato `.flux` — especificación v0 (provisional)

Esta especificación describe **lo que el compilador acepta hoy**. Es provisional y puede cambiar antes de declarar estable el lenguaje (ver «Registro de decisiones pendientes» en el plan).

## Secciones

Un archivo `.flux` tiene hasta tres partes, en cualquier orden:

| Sección | Obligatoria | Reglas |
|---|---|---|
| `<script lang="python">…</script>` | No | Como máximo una. `lang` es opcional y solo admite `python`. El contenido puede ir indentado (se quita la indentación común). |
| Plantilla | Sí | Todo lo que queda fuera de `<script>` y `<style>`. Debe tener **un único elemento raíz**. |
| `<style>…</style>` | No | Como máximo una. Subconjunto CSS: ver [estilos.md](estilos.md). |

Los comentarios `<!-- … -->` se ignoran en la plantilla.

El componente raíz de la aplicación (`src/App.flux`) puede tener `<Window>` como raíz; si no la tiene, el compilador lo envuelve en una ventana de 640×480 y su contenido ocupa toda la ventana. Los componentes usados dentro de otros **no** pueden tener `<Window>` como raíz.

## El script

- Se ejecuta **una vez por instancia** del componente, en un espacio de nombres propio: dos instancias nunca comparten estado local.
- Es Python normal: puede importar módulos del proyecto. La carpeta del componente raíz (`src/`) se añade a `sys.path`, de modo que `from services.users import display_name` funciona.
- Los errores de sintaxis se detectan al compilar, con archivo, línea y columna. Los errores al ejecutarse apuntan a la línea real del `.flux` en el traceback.
- **El código del componente se ejecuta como código del proyecto.** No hay aislamiento: no cargues componentes no confiables.

### Estado reactivo

```python
from fluxui import state, computed, batch

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

### Colecciones reactivas

Un `list`, `dict` o `set` guardado en un `state` se convierte (también los anidados) en una versión reactiva que sigue siendo una subclase de `list`/`dict`/`set`: `append`, `remove`, `sort`, `todo["done"] = True`, `del d[k]`, `s.add(x)`… actualizan la interfaz.

- Cada colección avisa solo a quien la leyó: cambiar `todos.value[0]["done"]` actualiza la fila de esa tarea y lo que dependa de ese diccionario, no toda la lista.
- Lo que se inserta en una colección reactiva también se convierte.
- La conversión **copia** el contenedor: modifica el objeto que devuelve el `state`, no el original que le pasaste.
- Las tuplas, las subclases propias de `list`/`dict` y otros objetos no se convierten. Si modificas uno en el sitio, llama a `estado.notify()`.

### Trabajo asíncrono

Las corrutinas se ejecutan en el **hilo de la interfaz**, sobre el bucle de Qt (FluxUI integra `asyncio` con `qasync`): tras cada `await` se puede modificar el estado directamente, y mientras esperan la ventana sigue respondiendo.

```python
from fluxui import state, task, background, spawn

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
- Los errores de un manejador asíncrono se registran con archivo y línea, como los síncronos. Los de una `@task` quedan en `.error` para mostrarlos.
- El trabajo de `background` en curso no se puede interrumpir (es un hilo), pero su resultado se descarta si la tarea se canceló.

Ejemplo completo: `examples/books` (busca en la API de Open Library).

### Temporizadores

```python
from fluxui import interval, timeout

@interval(250)                        # cada 250 ms mientras exista el componente
def muestrear():
    cpu.value = leer_cpu()

@interval(1000)
async def procesos():                 # async: el siguiente tic se salta si este no ha terminado
    lista.value = await background(leer_procesos)

ocultar = timeout(3000, lambda: aviso.set(""))
ocultar.restart()                     # vuelve a contar los 3 s (p. ej. con cada «escribiendo…»)
```

- Se detienen solos al desmontar el componente que los creó. Fuera de un componente (en un servicio), viven hasta `.stop()`.
- Cada ejecución agrupa sus cambios de estado en un solo `batch`: actualizar 50 métricas en un tic recalcula la interfaz una vez.
- `.active` es reactivo (`{#if muestrear.active}`); `.stop()`, `.start()` y `.restart()` lo controlan. Para cambiar el periodo: `muestrear.ms = 500` y `muestrear.restart()`.
- Un error en la función se registra con su nombre en el logger `fluxui` y el temporizador sigue.

## Expresiones en la plantilla

`{expresión}` admite **expresiones** Python (no sentencias). Se evalúan en Python; QML nunca ejecuta lógica del usuario.

- **Desenvolvido automático:** un nombre que apunta a un `state`, `computed` o prop se sustituye por su valor. `{count + 1}` equivale a `count.value + 1`. Por eso, en la plantilla **no** se escribe `.value`.
- Para modificar estado desde un evento se usa un [manejador en línea](#manejadores-de-eventos) (`on:click={count += 1}`) o una función del script. Dentro de una `lambda`, `count.set(0)` falla, porque `count` ya es un número; el error lo explica.
- Los nombres se resuelven **al evaluarse**, también dentro de `lambda`: un manejador de una fila de `{#each}` siempre ve el elemento actual de esa fila.
- Las dependencias se registran solas: cada binding se recalcula solo cuando cambia algo de lo que leyó, y solo se notifica a QML la propiedad afectada.
- **Nombres no definidos:** si una expresión usa un nombre que no define el script (ni un `{#each}` que la contenga, ni Python), es un error de compilación con sugerencia: `'cuont' no está definido — ¿quisiste decir 'count'?`. Si el script usa `from x import *` o `globals()`, esta comprobación se desactiva.
- `None` se muestra como texto vacío.
- **Formato** (solo en el texto, como en un f-string): `{cpu:.1f} %`, `{total:,}`, `{nombre!r}`, `{n:>4}`. Los dos puntos dentro de corchetes, paréntesis o cadenas no cuentan (`{lista[1:3]}`); una `lambda` necesita paréntesis.
- Si una expresión lanza una excepción al ejecutarse, se registra un error con archivo y línea en el logger `fluxui` y la aplicación sigue funcionando.

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

El contenido de `<Text>`, `<Button>` y `<Checkbox>` es su texto: `<Button>Clicks: {count}</Button>`. Los espacios se colapsan como en HTML. Texto suelto dentro de un contenedor se convierte en un `<Text>`.

`<Text format="markdown">` interpreta Markdown (negrita, cursiva, enlaces, código, listas); `format="html"`, el subconjunto de HTML de Qt. Los enlaces muestran la mano al pasar por encima y, al pulsarlos, emiten `on:link` con la URL; si nadie escucha `on:link`, se abren en el navegador:

```html
<Text format="markdown" on:link={abrir}>{mensaje["texto"]}</Text>
```

El Markdown de Qt también acepta HTML. Si el texto viene de otras personas (un chat, una web), escapa `<` y `&` antes de mostrarlo (`texto.replace("&", "&amp;").replace("<", "&lt;")`).

## Bloques

### `{#if}`

```html
{#if count >= 5}
  <Text>Cinco o más</Text>
{:else if count > 0}
  <Text>Algunos</Text>
{:else}
  <Text>Ninguno</Text>
{/if}
```

Solo existe la rama activa: al cambiar de rama, los elementos de la anterior se **destruyen** y sus bindings dejan de escuchar el estado. Lo que se muestra de nuevo se crea desde cero (con estado local nuevo).

### `{#each}`

```html
{#each todos as todo, i (todo["id"])}
  <Row>
    <Text>{i + 1}. {todo["title"]}</Text>
    <Button on:click={lambda: remove(todo["id"])}>Eliminar</Button>
  </Row>
{:else}
  <Text>No hay tareas.</Text>
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
2. entra en otra instancia de **la misma declaración** `{#each}` (el mismo sitio del mismo `.flux`: por ejemplo, la lista de tarjetas de dos `Columna`, o un `{#each}` dentro de otro `{#each}`),
3. con la misma clave.

```html
<!-- Columna.flux: cada columna es una instancia de este {#each} -->
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
- La vista (QML) sí se crea de nuevo en la otra lista. Los elementos de la fila que no son componentes (`<flex>`, `<Text>`) no tienen estado propio y también se recrean.
- *El mismo cambio* es un manejador (`on:click`, `on:drop`…), un `batch()` o un único cambio de una colección. Quitar en un manejador y añadir más tarde, tras un `await`, son dos cambios: la fila se destruye y se crea otra.
- No se traslada: entre declaraciones distintas (aunque usen el mismo componente y la misma clave), en `{#each}` sin clave, ni un componente que recibe contenido de slot. Si la misma clave aparece a la vez en las dos listas, son dos filas.

### Transiciones al entrar y salir

En el elemento raíz de un bloque `{#if}`, `{#each}` o `{#key}`:

```html
{#if aviso}
  <Text class="aviso" transition:fade>{aviso}</Text>
{/if}

{#each tareas as t (t["id"])}
  <Row in:slide out:fade={120}>…</Row>
{/each}
```

- `transition:x` anima la entrada y la salida; `in:x` y `out:x`, solo una. Tipos: `fade` (opacidad), `scale` (opacidad y escala), `slide` (opacidad y un pequeño desplazamiento). Duración opcional en milisegundos: `transition:fade={300}` (por defecto, 200).
- Al salir, la fila **deja de contar enseguida** (para las posiciones, el `{:else}`, etc.), pero su vista y sus bindings siguen vivos hasta que termina la animación; entonces se libera.
- En `<List>`, usa `<List animate>`: anima las filas que entran, salen y cambian de sitio.
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
- Lo que escribes en el script **sigue funcionando**: `effect`, `interval`, `timeout`, tareas y `on_destroy`. Un `effect` que guarda o sincroniza datos no se detiene por ocultar su componente.
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

Si una rama o una fila tiene varios elementos, se agrupan en un contenedor implícito con la orientación del contenedor padre, que hereda su dirección, separación y alineación. Normalmente no se nota; si necesitas controlar la disposición, envuélvelos tú en un `<Column>` o `<Row>`.

## Componentes

Un componente es otro archivo `.flux`. Se importa desde el script con sintaxis Python y se usa como una etiqueta que empieza por mayúscula:

```python
from components.TodoItem import TodoItem      # src/components/TodoItem.flux
from components import TodoItem               # equivalente
from .TodoItem import TodoItem                # relativo al archivo actual
```

```html
<TodoItem todo={todo} on:removed={remove} />
```

- Los imports absolutos se resuelven desde la carpeta del componente raíz (`src/`); los relativos, desde el archivo que importa.
- El compilador compila los componentes importados (una vez cada uno) y valida su uso: props y eventos desconocidos, props obligatorias que faltan, etc. Los componentes pueden ser recursivos.

### Props y eventos (en el hijo)

```python
from fluxui import prop, event, state

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

Un componente puede recibir contenido del padre. En el hijo, `<Slot />` marca dónde va; `<Slot name="x" />` es un slot con nombre, y lo que haya dentro de `<Slot>` es el contenido de reserva si el padre no pasa nada:

```html
<!-- components/Card.flux -->
<Column class="card">
  <Text class="title">{title}</Text>
  <Slot />
  <Row class="footer"><Slot name="footer"><Text>Sin acciones</Text></Slot></Row>
</Column>
```

```html
<!-- el padre -->
<Card title="Tarea">
  <Text>{todo["title"]}</Text>
  <Checkbox bind:checked={done}>Hecha</Checkbox>
  <Button slot="footer" on:click={borrar(todo)}>Eliminar</Button>
</Card>
```

- El contenido se evalúa en el ámbito del **padre**: ve su estado, sus funciones y las variables de los `{#each}` que lo rodean, y es reactivo como el resto de su plantilla.
- Lo que no lleva `slot="..."` va al slot por defecto; varios elementos se apilan en columna. Un elemento con `slot="nombre"` va a ese slot (para varios, agrúpalos en un `<Row>` o `<Column>`).
- El contenido vive mientras viva el `<Slot>` que lo muestra: si el hijo lo pone dentro de un `{#if}`, se crea y se libera con esa rama.
- Pasar contenido a un slot que el hijo no declara es un error de compilación que lista los slots disponibles.

### Estilos en la etiqueta del componente

Lo que la etiqueta lleva y el componente no declara como prop o evento se aplica a su **raíz**, si esta es una caja (`<flex>`, `Column` o `Row`): así un componente se usa como un elemento más.

```html
<Boton text="Guardar" class="primary" on:click={guardar} disabled={ocupado} ref={boton} />
<Tarjeta class="celda" title="..." />
```

- Pasan a la raíz: `class` y `class:x={...}`, `style`, `id`, `label`, `title`, `tabindex`, `disabled`, `as`, `flex`, `width`, `height`, `visible`, `ref` y los eventos nativos (`on:click`, `on:keydown`, `on:contextmenu`…).
- Las reglas de `<style>` del padre se aplican a la raíz, también sus estados: `.celda:hover` en el padre reacciona al ratón sobre la raíz del componente. Lo que fija la etiqueta gana a los estilos propios del componente.
- Las clases de la etiqueta activan además las reglas del componente que las combinan con la clase de su raíz: con `<Boton class="primary">`, la regla `.boton.primary` de `Boton.flux` se aplica.
- `ref` en la etiqueta apunta a la raíz (`boton.focus()` enfoca el `<flex>` del botón); `disabled` activa `:disabled` en la raíz.
- Si el componente declara una prop o un evento con ese nombre, gana lo declarado.
- `inherit_attrs = False` en el script del componente lo desactiva: la etiqueta solo admite sus props y eventos, y `class`, `id`, `flex`, `width`, `height` y `visible` van a una caja exterior que lo envuelve, como cuando la raíz no es una caja.
- Si la raíz no es una caja (un `<Button>`, varios elementos, un `{#if}`), esos seis atributos van a una **caja exterior** que lo envuelve, y un evento sin declarar es un error de compilación.
- Algunas cosas no se pueden fijar desde fuera en la raíz: una `transition` o el texto heredado (`color`, la fuente) y las variables (`--x`) puestos desde el padre. Con ellas el componente lleva también una caja exterior, que se encarga de eso; el resultado se ve igual.

### Ciclo de vida

- Cada uso de un componente crea una instancia con su propio script y estado.
- Al desmontarse (rama `{#if}` inactiva, fila de `{#each}` eliminada, recarga), se liberan sus bindings, sus props dejan de escuchar al padre y sus hijos se desmontan también.

```python
from fluxui import on_mount, on_destroy, effect, ref

campo = ref()                 # <TextField ref={campo} />

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
| `select_all()` | Selecciona todo el texto (`TextField`, `TextArea`). |
| `exists` | `True` si el elemento existe. |
| `value` | El objeto Qt Quick (`QQuickItem`). Es interfaz de Qt, no de FluxUI: úsalo como último recurso. |

Los métodos no hacen nada si el elemento aún no existe. Dentro de un `{#each}`, la referencia apunta a la última fila creada.

### Contexto: compartir valores con los descendientes

```python
# En un componente antecesor
from fluxui import provide, state
sesion = state({"usuario": "ana"})
provide("sesion", sesion)

# En cualquier descendiente, a cualquier profundidad
from fluxui import inject
sesion = inject("sesion")            # LookupError si nadie la provee
tema = inject("tema", "claro")       # con valor por defecto
```

- `inject` devuelve el valor del antecesor **más cercano** que lo provee: un componente intermedio puede proveer otro valor para su subárbol.
- Lo que se comparte es el objeto tal cual: para que sea reactivo, comparte un `state` (o un objeto que los contenga).
- Para estado global de toda la aplicación sigue valiendo un módulo Python (`services/store.py`). El contexto es para valores que dependen de dónde está el componente en el árbol.

## Estado que se recuerda: `persisted`

Lo que la aplicación debe recordar al volver a abrirse (el tema, la última sección, el tamaño de un panel, los archivos recientes) es un `persisted`: un `state` que se guarda solo.

```python
from fluxui import persisted

tema = persisted("tema", "claro")
recientes = persisted("recientes", [])

def abrir(ruta):
    recientes.value.insert(0, ruta)   # los cambios en el sitio también se guardan
```

- Se usa igual que un `state` (`.value`, `bind:`, en la plantilla sin `.value`). Al crearse lee el valor guardado; si no hay ninguno, toma el inicial.
- Los cambios se escriben agrupados (como mucho cada 300 ms) y al cerrar la aplicación. La escritura es atómica: un corte no deja el archivo a medias.
- La clave es de toda la aplicación: `persisted("tema", ...)` en dos módulos es el mismo objeto. Letras, cifras, `.`, `_` y `-`; para agrupar, `prefs.tema`.
- Solo valores JSON: textos, números, booleanos, `None`, listas y diccionarios con claves de texto. Otro valor da `TypeError` al crearlo o al asignarlo.
- Cada clave es un archivo `<clave>.json` en la carpeta de datos del usuario más el nombre del proyecto (`%APPDATA%\gestor` en Windows, `~/Library/Application Support/gestor` en macOS, `~/.config/gestor` en Linux). `FLUXUI_DATA_DIR` la cambia.
- En las pruebas con `fluxui.inspect.mount`, cada montaje usa una carpeta temporal vacía: no se tocan los datos reales. Para probar que algo se recuerda entre dos montajes, fija `FLUXUI_DATA_DIR`.
- Es para preferencias y datos pequeños: cada cambio reescribe el archivo de esa clave. Los datos grandes de la aplicación (documentos, bases de datos) siguen en sus propios archivos.
- Lo habitual es reunirlos en un módulo (`services/prefs.py`). `bind:value={prefs.tema}` enlaza con el del módulo; para leerlo en la plantilla sin `.value`, impórtalo por su nombre (`from services.prefs import tema`): la plantilla desenvuelve nombres, no atributos (`{prefs.tema}` es el `state`, `{prefs.tema.value}` su valor).

Ejemplo: `examples/preferencias` (nombre, tema, tamaño de letra, notas y un contador de aperturas; `python examples/preferencias/main.py`, ciérrala y vuelve a abrirla).

## Listas grandes: `<List>`

`<Scroll>` crea todas sus filas. Para cientos o miles de elementos, `<List>` solo crea las que se ven (más un margen):

```html
<List class="lista">
  {#each tareas as tarea (tarea["id"])}
    <Row class="fila">
      <Checkbox bind:checked={...}>{tarea["titulo"]}</Checkbox>
    </Row>
  {/each}
</List>
```

- Debe contener exactamente un `{#each}` (con clave, como siempre). El resto funciona igual: claves, índice, manejadores, componentes dentro de la fila y colecciones reactivas.
- Cada fila se crea —su parte Python y su vista— la primera vez que se hace visible. Su parte Python se conserva hasta que la fila sale de la lista; la vista se destruye al salir de pantalla y se vuelve a crear al volver. Por eso, lo que el usuario esté escribiendo en una fila debe ir a un `state` (`bind:`), no quedarse solo en el control.
- Las filas ocupan el ancho de la lista. Admite `gap`, `padding`, fondo, borde y radio desde `<style>`; por defecto ocupa el espacio libre (`flex: 1`).
- Añadir filas (al final, al principio o en medio, en cualquier cantidad) se aplica por bloques y la vista conserva su posición. Borrar o mover pocas filas se aplica una a una (con `animate`, animado). A partir de 64 borrados o movimientos a la vez (ordenar, invertir, sustituir la lista) se aplican de golpe: las filas visibles se vuelven a crear y la vista conserva su posición (la fila que estaba arriba, por su número, sigue arriba), como al reordenar una tabla.
- `{:else}` no está disponible dentro de `<List>`: muestra el estado vacío con un `{#if}` fuera.

### Desplazamiento

Para chats, registros y cualquier lista que crece:

```html
<List follow ref={lista} on:top={cargar_anteriores} on:scroll={al_desplazar}>
  {#each mensajes as m (m["id"])}
    <Mensaje msg={m} />
  {/each}
</List>
```

- **`follow`**: la lista empieza abajo; si el usuario está abajo, sigue a las filas nuevas (también cuando una fila crece, p. ej. al cargar una imagen); si subió a leer, no se mueve. Al insertar filas por arriba (historial), lo que se estaba viendo se queda en el mismo sitio de la pantalla.
- **`on:top`** y **`on:bottom`**: el usuario llegó al principio o al final (solo si el contenido no cabe entero).
- **`on:scroll`**: como mucho una vez por fotograma, con `event = {"top": bool, "bottom": bool, "y": píxeles desde arriba, "height": alto del contenido}`. Sirve para saber si el usuario está abajo (`on:scroll={abajo = event["bottom"]}`).
- Con `lista = ref()`: `lista.scroll_to_end()` (y con `follow` vuelve a seguir las nuevas), `lista.scroll_to_start()` y `lista.scroll_to(índice)` (lo justo para que se vea esa fila).

Con 10 000 filas, crear la lista tarda unos 40 ms (ver `python tools/bench.py`).

## Accesibilidad

- **Teclado:** Tab y Mayús+Tab recorren los controles en el orden de la plantilla. Un `Column`/`Row` con `on:click` también entra en ese recorrido y se activa con Espacio o Intro, como un botón. El foco se ve siempre (borde del color `--primary`).
- **Lectores de pantalla:** los controles anuncian su texto (botones, casillas, opciones, pestañas) o su `placeholder` (campos). `label="..."` en cualquier elemento fija o sustituye ese nombre; úsalo en campos sin texto visible y en tarjetas pulsables. `Image` usa `alt`.
- **Atajos:** `<Shortcut>` para las acciones frecuentes.

```html
<TextField bind:value={busqueda} placeholder="Buscar…" label="Buscar en las notas" />
<Row class="tarjeta" on:click={abrir(nota)} label={f"Abrir {nota['titulo']}"}>…</Row>
<Image src="logo.png" alt="Logotipo de la empresa" />
```

## Idiomas

```python
from pathlib import Path
from fluxui import i18n, t

i18n.load(Path(__file__).parent / "locales")   # locales/es.json, en.json, ar.json…
i18n.set("es")
```

```json
{ "saludo": "Hola, {nombre}", "archivos": {"zero": "Ningún archivo", "one": "{n} archivo", "other": "{n} archivos"} }
```

```html
<Text>{t("saludo", nombre=nombre)}</Text>
<Text>{t("archivos", n=len(archivos))}</Text>
<Text>{i18n.number(total, 2)} · {i18n.date(hoy, "long")}</Text>
```

- `t` lee el idioma activo: al llamar a `i18n.set("en")` se actualiza todo lo que traduce, sin reiniciar.
- Plurales: un diccionario con `zero` (opcional), `one` y `other`, elegido con el parámetro `n`.
- Si falta una clave en el idioma activo, se usa la de `i18n.default` (por defecto `"es"`) y, si tampoco está, la propia clave, con un aviso en el logger `fluxui`.
- `i18n.number(x, decimales)`, `i18n.currency(x, "€")` e `i18n.date(fecha, "short" | "long")` dan formato según el idioma activo (separadores, nombres de meses, cifras árabes…).
- En idiomas de **derecha a izquierda** (`ar`, `he`, `fa`, `ur`…) toda la interfaz se refleja: filas, alineación del texto e indicadores de los controles. `i18n.rtl` dice si el idioma activo lo es.

Ejemplo: `examples/idiomas` (español, inglés y árabe).

## Navegación entre pantallas

```python
from fluxui import pages
from pages.Inicio import Inicio
from pages.Detalle import Detalle

nav = pages(Inicio)

def abrir(item):
    nav.push(Detalle, item=item, on_borrado=borrar)
```

```html
<Row class="barra">
  <Button on:click={nav.pop()} enabled={nav.can_go_back}>← Volver</Button>
  <Text>{nav.current}</Text>
</Row>
<Pages stack={nav} />
```

- `<Pages stack={nav} />` muestra la página de arriba de la pila y ocupa el espacio libre (`flex: 1`).
- `push` muestra una página nueva encima; la de debajo **sigue viva** y, al volver con `pop()`, conserva su estado. Mientras está debajo, lo que muestra espera, como en [`{#hidden}`](#hidden): se pone al día al volver a verse. `replace` sustituye la actual; `reset` vacía la pila y empieza de nuevo. Las páginas descartadas se liberan (sus `on_destroy` se ejecutan).
- Cada página ocupa todo su `<Pages>` (y cada sección, su `<Sections>`) y se estrecha con la ventana hasta el mínimo de su contenido; lo que deba desplazarse, con `overflow: auto`. La raíz de la página puede cambiarlo con CSS, como un bloque en una columna:

  ```css
  .pagina { max-width: 720px; margin: 0 auto; }   /* una columna centrada */
  .pagina { width: 400px; height: 300px; }         /* tamaño fijo, arriba a la izquierda */
  .pagina { align-self: center; }                  /* su ancho natural, centrada */
  .pagina { margin: 24px; }                        /* llena, con margen alrededor */
  ```
- Las palabras clave son props y eventos (`on_...`) de la página, como en `open_window`. Las páginas heredan el contexto (`inject`) del componente que declara la pila.
- `nav.current` (nombre de la página visible), `nav.depth` y `nav.can_go_back` son reactivos; `nav.page` da la instancia visible.
- **Transiciones:** `<Pages stack={nav} transition:slide />` anima la página que entra: al avanzar llega desde la derecha y al volver desde la izquierda. También `fade` y `scale`, y la duración: `transition:fade={150}`. En `<Sections>`, la transición se aplica al cambiar de sección y a las páginas de cada una.
- **Atrás con el teclado y el ratón:** Alt+← y el botón «atrás» del ratón vuelven a la página anterior, en la pila visible más interna. Alt+← actúa cuando el foco está dentro de la pila (si está, por ejemplo, en un botón de la barra lateral, no hace nada); el ratón, al pulsar sobre ella. Si un elemento de la página ya usa Alt+← (por ejemplo, para mover una tarjeta), gana el elemento.

### Navegar desde una página

Dentro de una página (o de cualquier componente que contenga), `navigation()` da su pila, sin pasarla como prop:

```python
from fluxui import navigation
from pages.Detalle import Detalle

nav = navigation()

def abrir(item):
    nav.push(Detalle, item=item)
```

### Devolver un resultado

`push` se puede esperar: `await` devuelve el valor con el que la página vuelve con `nav.back(valor)` (o `None` si se descarta de otra forma, con `pop`, `replace` o `reset`).

```python
async def elegir_responsable():                  # en la página que pregunta
    persona = await nav.push(ElegirPersona)
    if persona is not None:
        tarjeta["responsable"] = persona["id"]
```

```html
<!-- en ElegirPersona.flux -->
<Button on:click={nav.back(p)}>{p["nombre"]}</Button>
```

### Secciones

Una aplicación con barra lateral o pestañas tiene varias secciones, y cada una necesita su pila. `sections()` las crea; `<Sections of={...} />` muestra la actual:

```python
from fluxui import sections
from pages.Proyectos import Proyectos
from pages.Personas import Personas

secciones = sections(proyectos=Proyectos, personas=Personas)
```

```html
<flex>
  <flex direction="column" class="barra">
    <Button on:click={secciones.show("proyectos")} class:activa={secciones.current == "proyectos"}>Proyectos</Button>
    <Button on:click={secciones.show("personas")} class:activa={secciones.current == "personas"}>Personas</Button>
  </flex>
  <Sections of={secciones} />
</flex>
```

- Cada sección es una pila (`secciones["personas"]`, o `secciones.stack` para la visible) y empieza en el componente indicado. Dentro, `navigation()` da la pila de su sección.
- Una sección se crea la primera vez que se muestra. Al cambiar a otra **se conserva entera**, con todas sus páginas y su estado; volver a ella cuesta lo mismo que mostrarla. Mientras no se ve, lo que muestra espera (como en [`{#hidden}`](#hidden)): un cambio de datos en otra sección no la recalcula.
- `secciones.current` (el nombre de la visible) es reactivo; `secciones.names` lista los nombres.

### Preguntar antes de salir

`before_leave(fn)` en el script de un componente registra una pregunta: si `fn()` devuelve `False`, no se sale. Puede ser `async`, para preguntar con un diálogo:

```python
from fluxui import before_leave, dialogs

@before_leave
async def salir():
    return not cambios.value or await dialogs.confirm("Hay cambios sin guardar. ¿Salir igualmente?")
```

- Se consulta al descartar la página que contiene el componente (`pop`, `back`, `replace`, `reset`, Alt+←) y al cerrar con la X la ventana que lo muestra. Cerrar la ventana principal consulta también las ventanas que abrió.
- Cambiar de sección no pregunta: la sección se conserva y no se pierde nada.
- Para encadenar navegaciones, espera la salida: `pop`, `back`, `replace` y `reset` devuelven `True` si se salió y `False` si un `before_leave` lo impidió (la respuesta puede llegar después de un diálogo):

```python
async def ir_a_tarjeta(pid, tid):
    if await nav.reset(Proyectos):      # un detalle con cambios puede pedir quedarse
        nav.push(Proyecto, ident=pid, enfocar=tid)
```
- Cerrar desde el código (`ventana.close()`) no pregunta.

## Varias ventanas

Cualquier componente importado se puede abrir en una ventana propia:

```python
from fluxui import open_window
from components.Ajustes import Ajustes      # un .flux (con <Window> como raíz, o sin ella)

def abrir_ajustes():
    ventana = open_window(Ajustes, usuario=usuario, on_guardado=guardar, modal=True)
```

- Las palabras clave son las **props** del componente; las que empiezan por `on_`, sus **eventos** (`on_guardado` → `guardado = event()`). Una prop desconocida es un `TypeError` que lista las disponibles. Un `state` pasado como prop sigue siendo reactivo en la ventana.
- La ventana hereda el **contexto** (`inject`) del componente que la abre, queda por delante de su ventana y se **cierra sola** cuando ese componente se desmonta. Al cerrar la ventana principal se cierran las que abrió.
- `modal=True` bloquea la ventana que la abrió mientras está abierta. `theme="dark"` le da un tema propio (también a los componentes que contiene), sin cambiar el de la aplicación.
- Devuelve un objeto con `is_open` (reactivo: úsalo en la plantilla o en un `computed`), `close()`, `focus()` e `instance`.

## Diálogos del sistema

```python
from fluxui import dialogs

async def abrir():                                # on:click={abrir}
    ruta = await dialogs.open_file("Abrir nota", filters=["Notas (*.md *.txt)", "Todos (*)"])
    if ruta is not None:                          # None: el usuario canceló
        texto.value = ruta.read_text(encoding="utf-8")

async def borrar():
    if await dialogs.confirm("¿Borrar la nota?", details="No se puede deshacer."):
        ...
```

| Función | Devuelve |
|---|---|
| `open_file(title, filters, folder)` | `Path` o `None` |
| `open_files(title, filters, folder)` | `list[Path]` (vacía si se cancela) |
| `save_file(title, filters, folder, name)` | `Path` o `None` |
| `choose_folder(title, folder)` | `Path` o `None` |
| `message(text, title, details)` | `None` al cerrarse |
| `confirm(text, title, details)` | `True` si se acepta |

Son nativos cuando la plataforma los ofrece y se muestran sobre la ventana de la aplicación. Al ser `async`, se usan desde un manejador `async def`, y se cierran solos si el componente que los abrió se desmonta.

## Elementos propios en QML

Cuando FluxUI no ofrece un control, se puede escribir en QML y usarlo como un elemento más. Un archivo `.qml` del proyecto se importa igual que un componente:

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
    color: fxtheme.border           // los tokens del tema están en `fxtheme`
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
- Disposición: sin `width`/`height` toma su tamaño natural (`implicitWidth`/`implicitHeight`), como un botón. `flex={1}` lo hace crecer en el eje del contenedor igual que a los elementos de FluxUI (`<LineChart flex={1} />` ocupa el alto libre de una columna).
- Props: las propiedades que no son `readonly`, con su tipo (`string`, `int`, `real`, `bool`, `color`; el resto acepta cualquier valor). Además, las comunes: `width`, `height`, `flex`, `visible`, `enabled`, `opacity`, y `id`, `class`, `ref`.
- Eventos: cada `signal`. El manejador recibe sus parámetros (`def elegido(step):`; en línea, `event`).
- `bind:prop={estado}` funciona con cualquier propiedad escribible: los cambios que haga el QML (también por asignación, `root.value = 3`) vuelven al `state`. Los números de QML (`real`) llegan como `float`.
- `flux dev` reinicia la aplicación al guardar el `.qml` (Qt no siempre vuelve a leer en el mismo proceso un `.qml` ya cargado).
- El QML es **interfaz de Qt, no de FluxUI**: su contenido no está cubierto por la política de versiones, y sus errores se muestran tal como los da Qt.

**Tipos escritos en Python.** Un `QQuickItem` (o `QQuickPaintedItem`) registrado con `@QmlElement` se usa desde un `.qml` como cualquier tipo QML (`import dials` → `PyDial { ... }`). El módulo que lo registra debe importarse **antes** de `run()`, en `main.py`, porque Qt resuelve los imports al cargar la vista.

Ejemplo: `examples/counter` (`src/widgets/Meter.qml`).

## Elementos disponibles

**Elementos base, en minúscula; componentes y controles, en mayúscula.** Las etiquetas en minúscula están reservadas para los elementos base de FluxUI, a partir de los que se construyen otros elementos sin escribir QML (como `<div>` frente a `<Boton>` en la web). Hoy hay uno, [`<flex>`](flex.md); el de la entrada de datos llegará después. Una etiqueta en minúscula desconocida es un error que lista los elementos base.

| Elemento base | Qt Quick | Propiedades | Eventos |
|---|---|---|---|
| `flex` | caja propia con el motor flexbox (`FxFlex`) | `direction` (`row` por defecto, `column`, `row-reverse`, `column-reverse`), `wrap`, `gap`, `padding`, `align` (`align-items`), `justify` (`justify-content`), `as`, `tabindex`, `disabled`, `title`, `checked`, `selected`, `expanded`, `style` | `on:click`, `on:dblclick`, `on:contextmenu`, `on:pointerdown`, `on:pointerup`, `on:pointermove`, `on:pointerenter`, `on:pointerleave`, `on:wheel`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur`, `on:resize` |

`<flex>` es la caja de la web: fila por defecto, `align-items: stretch` y el resto del flexbox de CSS en `<style>` (`flex-wrap`, márgenes y `margin: auto`, `space-between`, `order`, `%`, bordes por lado, radio por esquina, `overflow`), con estados (`:hover`, `:pressed`, `:focus-visible`…), selectores de descendiente (`.tarjeta:hover .acciones`), sombra, `outline`, `transform` y `cursor`. Ver [estilos.md](estilos.md) y el diseño completo, con lo que llegará en las fases siguientes, en [flex.md](flex.md). Los atributos de texto se comprueban al compilar: `<flex direction="diagonal">` es un error.

### Eventos de las cajas

`<flex>`, `Column` y `Row` reciben los eventos de la tabla. Como en la web, un evento **sube** desde el elemento más profundo bajo el puntero (o desde el que tiene el foco, para las teclas) hacia sus contenedores. El manejador recibe un objeto con lo ocurrido (`PointerEvent`, `KeyEvent`, `WheelEvent`, `FocusEvent`, `ResizeEvent`; ver [api.md](api.md)) y dos métodos:

- `event.stop()`: los contenedores de fuera no lo reciben (el ✕ de un chip no elige el chip).
- `event.prevent()`: Qt no hace lo que haría (escribir la tecla en un campo, desplazar con la rueda, pulsar con Espacio).

```python
def tecla(event):
    if event.key == "ArrowDown":
        siguiente()
        event.prevent()
```

- `on:pointerenter` y `on:pointerleave` no suben (como en la web). `on:focus`/`on:blur` tampoco; `event.reason` dice si llegó con Tab, con un clic o por código.
- `on:click` sigue siendo el de siempre: si un control de Qt (un `<Button>`) se queda el clic, la caja que lo contiene no lo recibe. Entre cajas, sí sube (y se corta con `stop()`). Desde el teclado (Espacio o Intro) llega con `event.pointer == "keyboard"`.
- `on:contextmenu`: clic derecho o tecla de menú.
- `prevent()` y `stop()` solo cuentan antes del primer `await` de un manejador `async def`. `prevent()` no impide que se dispare un `<Shortcut>`.

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

Propiedades comunes a todos salvo `Window`: `width`, `height`, `flex`, `visible`, `enabled`, `opacity` y `label` (nombre para lectores de pantalla; ver [Accesibilidad](#accesibilidad)).

| Elemento | Qt Quick | Propiedades | Eventos | `bind:` |
|---|---|---|---|---|
| `Window` | `ApplicationWindow` | `title`, `width`, `height`, `minWidth`, `minHeight`, `background` | `on:activate`, `on:deactivate` | — |
| `Column` | `<flex direction="column">` | `gap`, `padding` | `on:click` | — |
| `Row` | `<flex direction="row">` | `gap`, `padding` | `on:click` | — |
| `Scroll` | `ScrollView` + columna | `gap`, `padding` | — | — |
| `List` | `ListView` | `gap`, `padding`, `animate`, `follow` | `on:top`, `on:bottom`, `on:scroll(info)` | — |
| `Text` | `Label` | `text`, `color`, `format` (`plain`, `markdown`, `html`) | `on:link(url)` | — |
| `Button` | `Button` | `text`, `variant` (`default`, `primary`, `danger`, `ghost`), `flat` | `on:click` | — |
| `TextField` | `TextField` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:submit(texto)`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur` | `bind:value` |
| `TextArea` | `TextArea` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur` | `bind:value` |
| `Checkbox` | `CheckBox` | `checked`, `text` | `on:change(marcado)` | `bind:checked` |
| `Switch` | `Switch` | `checked`, `text` | `on:change(activado)` | `bind:checked` |
| `Slider` | `Slider` | `value`, `min` (0), `max` (100), `step` | `on:change(valor)` | `bind:value` |
| `Select` | `ComboBox` | `options`, `value`, `placeholder` | `on:change(valor)`, `on:keydown`, `on:keyup`, `on:focus`, `on:blur` | `bind:value` |
| `RadioGroup` | `RadioButton`s | `options`, `value`, `horizontal` | `on:change(valor)` | `bind:value` |
| `Tabs` | `TabBar` | `options`, `value` | `on:change(valor)` | `bind:value` |
| `ProgressBar` | `ProgressBar` | `value`, `max` (1), `indeterminate` | — | — |
| `Image` | `Image` | `src`, `fit` (`contain`, `cover`, `fill`, `none`), `alt` | — | — |
| `Shortcut` | `Shortcut` | `keys` | `on:activate` | — |
| `Spacer` | `Item` | — | — | — |

- **`List`** es una lista virtualizada para colecciones grandes; ver [Listas grandes](#listas-grandes-list) y [Desplazamiento](#desplazamiento).
- **`Window`**: `on:activate` y `on:deactivate` avisan cuando la ventana pasa a primer plano o deja de estarlo (para marcar como leído o decidir si mostrar una notificación con `notify`).
- **Opciones** (`Select`, `RadioGroup`, `Tabs`): `options` es una lista de textos (`["rojo", "verde"]`) o de diccionarios `{"label": "Mediano", "value": 2}`; `value` es el valor elegido. La elección del usuario se ve al momento; si Python cambia `value`, manda Python.
- `Tabs` es solo la barra: el contenido de cada pestaña se elige con `{#if pestaña == "general"}`.
- `Image`: `src` puede ser una ruta relativa a la carpeta del `.flux`, una ruta absoluta o una URL (`https:`, `qrc:`, `data:`). Sin `width`/`height`, toma el tamaño de la imagen.
- `Shortcut` no ocupa espacio: escucha el teclado de su ventana mientras existe (`<Shortcut keys="Ctrl+S" on:activate={guardar} />`; teclas como en Qt: `Ctrl+Shift+N`, `F5`, `Esc`). Dentro de un `{#if}`, solo está activo con la rama.
- `TextArea` emite `on:input` solo con los cambios del usuario, no con los que llegan de Python.
- **Teclado y foco en los campos** (`TextField`, `TextArea`, `Select`): `on:keydown`, `on:keyup`, `on:focus` y `on:blur` funcionan como en `<flex>` ([eventos](flex.md)): suben a los contenedores, `event.stop()` corta la subida y `event.prevent()` hace que la tecla no llegue al campo (no se escribe). Por ejemplo, Escape para cancelar una edición y guardar al salir del campo:

  ```html
  <TextField bind:value={nombre} on:keydown={event.key == "Escape" and cancelar()} on:blur={guardar()} />
  ```
- `Column` y `Row` son atajos de `<flex>` con sus valores por defecto de siempre: en una columna, texto y cajas ocupan el ancho y los controles se quedan a la izquierda; en una fila, los hijos se centran en vertical; solo encoge lo que tiene `flex`. Admiten todo el flexbox de `<flex>` en `<style>` (también `flex-wrap`). Si solo usan lo básico (`gap`, `padding`, alineación, márgenes fijos, un hijo con `flex`), se colocan con un layout de Qt, más rápido; no hay que hacer nada para ello ([Vía rápida](flex.md#vía-rápida-layouts-de-qt)).
- `<flex>`, `Column` y `Row` con `on:click` se pueden pulsar en toda su superficie (tarjetas, filas): muestran cursor de mano y un resaltado al pasar el ratón. Un botón dentro sigue funcionando por separado.
- `Scroll` es una columna con desplazamiento vertical; por defecto ocupa el espacio libre (`flex: 1`).
- `Spacer` ocupa el espacio libre y empuja a sus hermanos hacia los extremos.
- `width`/`height` fijan el tamaño preferido dentro del contenedor; `flex={1}` hace crecer el elemento en el eje del contenedor. Ver [estilos.md](estilos.md#disposición).

Un elemento, propiedad, evento o directiva desconocidos producen un error con las opciones válidas y, si hay uno parecido, «¿quisiste decir…?».

## Diagnósticos

Todos los errores siguen el formato `archivo:línea:columna: error: mensaje`, con la línea de origen, un `^` y, cuando existe, una sugerencia. Si Qt rechaza el QML generado, el error se remite al elemento `.flux` correspondiente y muestra además la línea QML implicada.

Para depurar: `flux parse src/App.flux` muestra el AST, `flux compile src/App.flux` el QML generado y `flux build` valida todos los componentes del proyecto.
