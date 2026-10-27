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

- Lo lanzado desde un componente (manejadores, `@task`, `spawn`, `on_mount` asíncrono) se **cancela al desmontarlo**: una corrutina nunca actualiza una vista que ya no existe. Una fila de `{#each}` cancela lo suyo al eliminarse.
- Los errores de un manejador asíncrono se registran con archivo y línea, como los síncronos. Los de una `@task` quedan en `.error` para mostrarlos.
- El trabajo de `background` en curso no se puede interrumpir (es un hilo), pero su resultado se descarta si la tarea se canceló.

Ejemplo completo: `examples/books` (busca en la API de Open Library).

## Expresiones en la plantilla

`{expresión}` admite **expresiones** Python (no sentencias). Se evalúan en Python; QML nunca ejecuta lógica del usuario.

- **Desenvolvido automático:** un nombre que apunta a un `state`, `computed` o prop se sustituye por su valor. `{count + 1}` equivale a `count.value + 1`. Por eso, en la plantilla **no** se escribe `.value`.
- Para modificar estado desde un evento se usa un [manejador en línea](#manejadores-de-eventos) (`on:click={count += 1}`) o una función del script. Dentro de una `lambda`, `count.set(0)` falla, porque `count` ya es un número; el error lo explica.
- Los nombres se resuelven **al evaluarse**, también dentro de `lambda`: un manejador de una fila de `{#each}` siempre ve el elemento actual de esa fila.
- Las dependencias se registran solas: cada binding se recalcula solo cuando cambia algo de lo que leyó, y solo se notifica a QML la propiedad afectada.
- **Nombres no definidos:** si una expresión usa un nombre que no define el script (ni un `{#each}` que la contenga, ni Python), es un error de compilación con sugerencia: `'cuont' no está definido — ¿quisiste decir 'count'?`. Si el script usa `from x import *` o `globals()`, esta comprobación se desactiva.
- `None` se muestra como texto vacío.
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
| Enlace | `bind:value={name}` | Enlace bidireccional con un `state` (nombre simple; no una variable de `{#each}` ni una prop). |

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

### Varios elementos en un bloque

Si una rama o una fila tiene varios elementos, se agrupan en un contenedor implícito con la orientación del contenedor padre (`Column` o `Row`), que hereda su separación y alineación. Normalmente no se nota; si necesitas controlar la disposición, envuélvelos tú en un `<Column>` o `<Row>`.

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

`class`, `class:x={...}`, `id`, `flex`, `width`, `height` y `visible` en la etiqueta de un componente (si el hijo no declara una prop con ese nombre) se aplican a una **caja exterior** que lo envuelve:

```html
<Card class="destacada" flex={1} title="..." />
```

Sirve para la disposición (tamaño, `flex`, márgenes interiores, fondo, borde). Los estilos de texto no se heredan hacia dentro del componente.

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
- Añadir filas (al final, al principio o en medio, en cualquier cantidad) se aplica por bloques y la vista conserva su posición. Borrar o mover pocas filas se aplica una a una. A partir de 64 borrados o movimientos a la vez (ordenar, invertir, sustituir la lista) se aplican de golpe y la lista vuelve al principio.
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
- `push` muestra una página nueva encima; la de debajo **sigue viva** y, al volver con `pop()`, conserva su estado. `replace` sustituye la actual; `reset` vacía la pila y empieza de nuevo. Las páginas descartadas se liberan (sus `on_destroy` se ejecutan).
- Las palabras clave son props y eventos (`on_...`) de la página, como en `open_window`. Las páginas heredan el contexto (`inject`) del componente que declara la pila.
- `nav.current` (nombre de la página visible), `nav.depth` y `nav.can_go_back` son reactivos; `nav.page` da la instancia visible.

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
- Props: las propiedades que no son `readonly`, con su tipo (`string`, `int`, `real`, `bool`, `color`; el resto acepta cualquier valor). Además, las comunes: `width`, `height`, `flex`, `visible`, `enabled`, `opacity`, y `id`, `class`, `ref`.
- Eventos: cada `signal`. El manejador recibe sus parámetros (`def elegido(step):`; en línea, `event`).
- `bind:prop={estado}` funciona con cualquier propiedad escribible: los cambios que haga el QML (también por asignación, `root.value = 3`) vuelven al `state`. Los números de QML (`real`) llegan como `float`.
- `flux dev` reinicia la aplicación al guardar el `.qml` (Qt no siempre vuelve a leer en el mismo proceso un `.qml` ya cargado).
- El QML es **interfaz de Qt, no de FluxUI**: su contenido no está cubierto por la política de versiones, y sus errores se muestran tal como los da Qt.

**Tipos escritos en Python.** Un `QQuickItem` (o `QQuickPaintedItem`) registrado con `@QmlElement` se usa desde un `.qml` como cualquier tipo QML (`import dials` → `PyDial { ... }`). El módulo que lo registra debe importarse **antes** de `run()`, en `main.py`, porque Qt resuelve los imports al cargar la vista.

Ejemplo: `examples/counter` (`src/widgets/Meter.qml`).

## Elementos disponibles

Propiedades comunes a todos salvo `Window`: `width`, `height`, `flex`, `visible`, `enabled`, `opacity` y `label` (nombre para lectores de pantalla; ver [Accesibilidad](#accesibilidad)).

| Elemento | Qt Quick | Propiedades | Eventos | `bind:` |
|---|---|---|---|---|
| `Window` | `ApplicationWindow` | `title`, `width`, `height`, `minWidth`, `minHeight`, `background` | `on:activate`, `on:deactivate` | — |
| `Column` | `ColumnLayout` | `gap`, `padding` | `on:click` | — |
| `Row` | `RowLayout` | `gap`, `padding` | `on:click` | — |
| `Scroll` | `ScrollView` + columna | `gap`, `padding` | — | — |
| `List` | `ListView` | `gap`, `padding`, `animate`, `follow` | `on:top`, `on:bottom`, `on:scroll(info)` | — |
| `Text` | `Label` | `text`, `color`, `format` (`plain`, `markdown`, `html`) | `on:link(url)` | — |
| `Button` | `Button` | `text`, `variant` (`default`, `primary`, `danger`, `ghost`), `flat` | `on:click` | — |
| `TextField` | `TextField` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:submit(texto)` | `bind:value` |
| `TextArea` | `TextArea` | `value`, `placeholder`, `readonly` | `on:input(texto)` | `bind:value` |
| `Checkbox` | `CheckBox` | `checked`, `text` | `on:change(marcado)` | `bind:checked` |
| `Switch` | `Switch` | `checked`, `text` | `on:change(activado)` | `bind:checked` |
| `Slider` | `Slider` | `value`, `min` (0), `max` (100), `step` | `on:change(valor)` | `bind:value` |
| `Select` | `ComboBox` | `options`, `value`, `placeholder` | `on:change(valor)` | `bind:value` |
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
- `Column`/`Row` con `on:click` se pueden pulsar en toda su superficie (tarjetas, filas): muestran cursor de mano y un resaltado al pasar el ratón. Un botón dentro sigue funcionando por separado.
- `Scroll` es una columna con desplazamiento vertical; por defecto ocupa el espacio libre (`flex: 1`).
- `Spacer` ocupa el espacio libre y empuja a sus hermanos hacia los extremos.
- `width`/`height` fijan el tamaño preferido dentro del contenedor; `flex={1}` hace crecer el elemento en el eje del contenedor. Ver [estilos.md](estilos.md#disposición).

Un elemento, propiedad, evento o directiva desconocidos producen un error con las opciones válidas y, si hay uno parecido, «¿quisiste decir…?».

## Diagnósticos

Todos los errores siguen el formato `archivo:línea:columna: error: mensaje`, con la línea de origen, un `^` y, cuando existe, una sugerencia. Si Qt rechaza el QML generado, el error se remite al elemento `.flux` correspondiente y muestra además la línea QML implicada.

Para depurar: `flux parse src/App.flux` muestra el AST, `flux compile src/App.flux` el QML generado y `flux build` valida todos los componentes del proyecto.
