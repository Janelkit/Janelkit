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

Si la raíz no es `<Window>`, el compilador la envuelve en una ventana de 640×480. Si `<Window>` tiene varios hijos, se apilan en una `Column` implícita.

## El script

- Se ejecuta **una vez por instancia** del componente, en un espacio de nombres propio: dos instancias nunca comparten estado local.
- Es Python normal: puede importar módulos del proyecto. La carpeta del componente raíz (`src/`) se añade a `sys.path`, de modo que `from services.users import display_name` funciona.
- Los errores apuntan a la línea real del `.flux` en el traceback.
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

`{expresión}` admite **expresiones** Python (no sentencias). Se evalúan en Python, en el espacio de nombres del script.

- **Desenvolvido automático:** un nombre que apunta a un `state` o `computed` se sustituye por su valor. `{count + 1}` equivale a `count.value + 1`. Por eso, en la plantilla **no** se escribe `.value`.
- Las dependencias se registran solas: cada binding se recalcula solo cuando cambia algo de lo que leyó, y solo se notifica a QML la propiedad afectada.
- Limitación: dentro de `lambda` en la plantilla los nombres no se desenvuelven.
- `None` se muestra como texto vacío.
- Si una expresión lanza una excepción, se registra un error con archivo y línea en el logger `fluxui` y la aplicación sigue funcionando.

Las llaves pueden contener cadenas y diccionarios con llaves: `{ {"a": "}"}["a"] }`.

## Atributos

| Forma | Ejemplo | Significado |
|---|---|---|
| Literal | `title="Hola"` | Texto. En propiedades numéricas se admite `width="640"`. |
| Expresión | `width={640}`, `enabled={count > 0}` | Si es un literal Python se incrusta en el QML; si no, es un binding reactivo. |
| Booleano | `flat` | Equivale a `flat={True}`. |
| Abreviado | `{enabled}` | Equivale a `enabled={enabled}`. |
| `id` | `id="guardar"` | Se convierte en `objectName` (útil para pruebas). |
| `class` | `class="a b"` | Clases para `<style>`. Solo texto literal por ahora. |
| Evento | `on:click={increment}` | Llama a la función. Ver eventos por elemento. |
| Enlace | `bind:value={name}` | Enlace bidireccional con un `state` (nombre simple). |

Los manejadores reciben los argumentos del evento que acepten: `def enviar():` y `def enviar(texto):` son válidos para `on:submit`.

## Texto

El contenido de `<Text>`, `<Button>` y `<Checkbox>` es su texto: `<Button>Clicks: {count}</Button>`. Los espacios se colapsan como en HTML. Texto suelto dentro de un contenedor se convierte en un `<Text>`.

## Bloques

```html
{#if count >= 5}
  <Text>Cinco o más</Text>
{:else if count > 0}
  <Text>Algunos</Text>
{:else}
  <Text>Ninguno</Text>
{/if}
```

Implementación actual: cada elemento de una rama se crea siempre y se **oculta** (`visible: false`) cuando la rama no está activa. Las posiciones de `Column`/`Row` ignoran los elementos ocultos. El desmontaje real de ramas llegará con el Incremento 4.

`{#each items as item, i (item.id)}…{/each}` se **analiza** (el parser lo entiende y valida), pero el compilador aún lo rechaza con un error claro: es trabajo del Incremento 4.

## Elementos disponibles

Propiedades comunes a todos: `width`, `height`, `visible`, `enabled`, `opacity`.

| Elemento | Qt Quick | Propiedades | Eventos | `bind:` |
|---|---|---|---|---|
| `Window` | `ApplicationWindow` | `title`, `width`, `height`, `minWidth`, `minHeight`, `background` | — | — |
| `Column` | `Column` | `gap`, `padding` | — | — |
| `Row` | `Row` | `gap`, `padding` | — | — |
| `Text` | `Label` | `text`, `color` | — | — |
| `Button` | `Button` | `text`, `flat` | `on:click` | — |
| `TextField` | `TextField` | `value`, `placeholder`, `readonly` | `on:input(texto)`, `on:submit(texto)` | `bind:value` |
| `Checkbox` | `CheckBox` | `checked`, `text` | `on:change(marcado)` | `bind:checked` |

Un elemento, propiedad, evento o directiva desconocidos producen un error con la lista de opciones válidas.

## Diagnósticos

Todos los errores siguen el formato `archivo:línea:columna: error: mensaje`, con la línea de origen, un `^` y, cuando existe, una sugerencia. Si Qt rechaza el QML generado, el error se remite al elemento `.flux` correspondiente y muestra además la línea QML implicada.

Para depurar: `flux parse src/App.flux` muestra el AST y `flux compile src/App.flux` el QML generado.
