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
items = state([])         # las mutaciones internas NO se detectan:
items.value = [*items.value, "nuevo"]   # asigna un valor nuevo

@computed                 # perezoso y cacheado; se invalida solo
def total():
    return count.value * 2

def reset():
    with batch():         # los manejadores de eventos ya se ejecutan en un lote
        count.value = 0
        items.value = []
```

Otras utilidades: `count.set(v)`, `count.update(fn)`, `count.peek()` (lee sin registrar dependencia). Asignar un valor igual (mismo tipo y `==`) no notifica.

## Expresiones en la plantilla

`{expresión}` admite **expresiones** Python (no sentencias). Se evalúan en Python; QML nunca ejecuta lógica del usuario.

- **Desenvolvido automático:** un nombre que apunta a un `state`, `computed` o prop se sustituye por su valor. `{count + 1}` equivale a `count.value + 1`. Por eso, en la plantilla **no** se escribe `.value`.
- Consecuencia: en la plantilla no se puede modificar un `state` directamente (`lambda: count.set(0)` falla, porque `count` ya es un número). Llama a una función del script: `on:click={reset}` o `on:click={lambda: remove(item["id"])}`. El error, si ocurre, lo explica.
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
| `class` | `class="a b"` | Clases para `<style>`. Solo texto literal. |
| Clase condicional | `class:activa={sel == id}` | Aplica los estilos de `.activa` mientras la condición sea verdadera. `class:activa` equivale a `class:activa={activa}`. |
| Evento | `on:click={increment}` | Llama a la función. Ver eventos por elemento. |
| Enlace | `bind:value={name}` | Enlace bidireccional con un `state` (nombre simple; no una variable de `{#each}` ni una prop). |

Los manejadores reciben los argumentos del evento que acepten: `def enviar():` y `def enviar(texto):` son válidos para `on:submit`.

## Texto

El contenido de `<Text>`, `<Button>` y `<Checkbox>` es su texto: `<Button>Clicks: {count}</Button>`. Los espacios se colapsan como en HTML. Texto suelto dentro de un contenedor se convierte en un `<Text>`.

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
- Las props son **de solo lectura** en el hijo y reactivas: si el padre cambia el valor, se actualiza todo lo que las lee. En la plantilla se usan sin `.value`. Para editarlas, cópialas en un `state` o emite un evento para que el padre las cambie.
- Un evento sin manejador en el padre no hace nada.
- En el padre, un atributo con literal (`compact`, `title="x"`) se pasa como constante; una expresión (`todo={t}`) se reevalúa cuando cambia lo que lee.

### Ciclo de vida

- Cada uso de un componente crea una instancia con su propio script y estado.
- Al desmontarse (rama `{#if}` inactiva, fila de `{#each}` eliminada, recarga), se liberan sus bindings, sus props dejan de escuchar al padre y sus hijos se desmontan también.

Por ahora los componentes no admiten contenido entre etiquetas (slots), ni `class`/`id` en la etiqueta: los estilos y el `flex` se definen en la raíz del propio componente.

## Elementos disponibles

Propiedades comunes a todos salvo `Window`: `width`, `height`, `flex`, `visible`, `enabled`, `opacity`.

| Elemento | Qt Quick | Propiedades | Eventos | `bind:` |
|---|---|---|---|---|
| `Window` | `ApplicationWindow` | `title`, `width`, `height`, `minWidth`, `minHeight`, `background` | — | — |
| `Column` | `ColumnLayout` | `gap`, `padding` | `on:click` | — |
| `Row` | `RowLayout` | `gap`, `padding` | `on:click` | — |
| `Scroll` | `ScrollView` + columna | `gap`, `padding` | — | — |
| `Text` | `Label` | `text`, `color` | — | — |
| `Button` | `Button` | `text`, `variant` (`default`, `primary`, `danger`, `ghost`), `flat` | `on:click` | — |
| `TextField` | `TextField` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:submit(texto)` | `bind:value` |
| `TextArea` | `TextArea` | `value`, `placeholder`, `readonly` | — | `bind:value` |
| `Checkbox` | `CheckBox` | `checked`, `text` | `on:change(marcado)` | `bind:checked` |
| `Spacer` | `Item` | — | — | — |

- `Column`/`Row` con `on:click` se pueden pulsar en toda su superficie (tarjetas, filas): muestran cursor de mano y un resaltado al pasar el ratón. Un botón dentro sigue funcionando por separado.
- `Scroll` es una columna con desplazamiento vertical; por defecto ocupa el espacio libre (`flex: 1`).
- `Spacer` ocupa el espacio libre y empuja a sus hermanos hacia los extremos.
- `width`/`height` fijan el tamaño preferido dentro del contenedor; `flex={1}` hace crecer el elemento en el eje del contenedor. Ver [estilos.md](estilos.md#disposición).

Un elemento, propiedad, evento o directiva desconocidos producen un error con las opciones válidas y, si hay uno parecido, «¿quisiste decir…?».

## Diagnósticos

Todos los errores siguen el formato `archivo:línea:columna: error: mensaje`, con la línea de origen, un `^` y, cuando existe, una sugerencia. Si Qt rechaza el QML generado, el error se remite al elemento `.flux` correspondiente y muestra además la línea QML implicada.

Para depurar: `flux parse src/App.flux` muestra el AST, `flux compile src/App.flux` el QML generado y `flux build` valida todos los componentes del proyecto.
