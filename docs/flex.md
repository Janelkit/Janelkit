# `<flex>`: el elemento base para construir componentes visuales

## Por qué

Componer (componentes `.janel` con props, eventos y slots) no basta para construir un control desde cero: un botón propio necesita cambiar de aspecto al pasar el ratón, al pulsarlo o con el foco; reaccionar al puntero y al teclado; dar color y letra a su texto desde el contenedor; tener sombra, márgenes, posición absoluta o una rejilla que salte de línea.

En el frontend web, todo eso se hace con una caja (`<div>`), CSS y eventos. **`<flex>` es esa caja para JanelKit**: un elemento con el que cualquier persona pueda escribir en `.janel` un botón, una tarjeta, un chip, un elemento de menú o una barra de herramientas, con el aspecto y el comportamiento que espera de la web, **sin escribir JavaScript ni QML**. La lógica va en el `<script>` de Python; el aspecto, en `<style>`.

**`<flex>` no cubre todos los casos, y no lo pretende.** Es una **base**: el punto de partida para crear elementos nuevos a partir de él. Quien no es experto puede hacerse su propio botón, menú o diálogo con lo que ya sabe de la web, sin toparse con la barrera de aprender QML. El QML propio sigue disponible como vía de escape para lo que `<flex>` no alcanza (dibujo libre, gráficas).

> **Sin `.js` para el usuario.** Quien escribe la aplicación nunca escribe JavaScript: ni en la plantilla, ni en los estilos, ni en manejadores. Por dentro, JanelKit implementa `<flex>` en su módulo QML interno, como hace hoy con el resto de elementos; eso es un detalle interno y no forma parte de la API.

## Elementos base en minúscula

Regla del lenguaje: **los elementos base se escriben en minúscula** (`<flex>`); **los componentes, en mayúscula** (`<Boton>`, `<Tarjeta>`). Es la misma convención de la web con React o Svelte: `<div>` es primitivo, `<Boton>` es algo construido.

- De un vistazo se distingue en una plantilla qué es primitivo y qué está construido encima.
- Un componente nunca choca con un elemento base: `Flex.janel` sería un componente válido, distinto de `<flex>`.
- Las etiquetas en minúscula quedan reservadas para JanelKit. Una desconocida da error con la lista de elementos base, nunca la pista de importar un componente.
- Los controles integrados (`Column`, `Row`, `Text`, `Button`, `List`…) mantienen su nombre: no son elementos base, sino controles ya hechos o atajos (ver [`Column` y `Row`](#column-y-row)).

## Qué es y qué no es

`<flex>` es el **padre de los elementos visuales y de interacción**: cajas que se dibujan, se disponen, cambian de estado y responden al puntero y al teclado. No es el padre de todo:

| Familia | Elemento base | Para qué | Estado |
|---|---|---|---|
| **Cajas e interacción** | `<flex>` | Contenedores, tarjetas, botones, chips, menús, barras, rejillas, superposiciones | Este documento |
| **Entrada de datos** | Controles integrados (`TextField`, `TextArea`, `Select`, `Slider`…) | Edición de texto, cursor y selección, método de entrada (IME), valor con `bind:value` | Existen; no se construyen con `<flex>` |
| **Texto** | `<Text>` | Hoja: muestra texto (plano, Markdown, HTML). Hereda estilo de su `<flex>` contenedor | Existe |
| **Colecciones grandes** | `<List>` | Virtualización de miles de filas. Cada fila puede ser un `<flex>` | Existe |
| **Dibujo libre y gráficas** | Un `.qml` propio importado como componente | Gráficas, lienzos | Fuera del núcleo ([lenguaje.md](lenguaje.md)) |

Regla para decidir: si el comportamiento esencial es **editar un valor** (texto, número, fecha, selección de opciones con teclado de edición), pertenece a la familia de entrada, no a `<flex>`. Un interruptor o una casilla, que solo alternan, sí se pueden construir con `<flex>`; un campo de texto, no.

## Vistazo

```html
<!-- components/Boton.janel: un botón escrito entero en .janel -->
<script lang="python">
from janelkit import prop, event

variant = prop("default")   # "default" | "primary" | "danger"
disabled = prop(False)
press = event()
</script>

<flex as="button" class={["boton", variant]} disabled={disabled}
      on:click={press.emit()}>
  <Slot />
</flex>

<style>
.boton {
  direction: row; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: var(--radius);
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text); font-weight: 500; cursor: pointer;
  transition: background 120ms, box-shadow 120ms, transform 80ms;
}
.boton:hover   { background: var(--surface-alt); }
.boton:pressed { transform: scale(0.97); }
.boton:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.boton:disabled { opacity: 0.5; cursor: default; }

.primary { background: var(--primary); color: var(--on-primary); border-color: transparent; }
.primary:hover { background: var(--primary-hover); }
.danger  { background: var(--danger);  color: var(--on-danger);  border-color: transparent; }
</style>
```

```html
<!-- Uso: como cualquier elemento, con clases, eventos y contenido -->
<Boton variant="primary" class="ancho" on:press={guardar}>Guardar</Boton>
```

- El texto del slot es un `<Text>` que **hereda** `color` y `font-weight` del `<flex>`: no hace falta estilarlo aparte.
- `:hover`, `:pressed`, `:focus-visible` y `:disabled` los resuelve JanelKit **sin pasar por Python**: no cuestan nada aunque haya cientos de botones.
- `as="button"` le da el papel de botón para la accesibilidad, el foco con Tab y la activación con Espacio/Intro.

## La plantilla

### Atributos

| Atributo | Valores | Qué hace |
|---|---|---|
| `class`, `class:x`, `class={expr}` | como en los demás elementos | Clases para `<style>`. |
| `style` | `style={{"background": color, "width": f"{pct}%"}}` o `style="gap: 4px"` | Estilos en línea, también calculados en Python. Ganan a las clases (como en la web). Acepta las mismas propiedades que `<style>`, no pseudo-clases. |
| `as` | `"box"` (por defecto), `"button"`, `"link"`, `"checkbox"`, `"switch"`, `"tab"`, `"menuitem"`, `"dialog"`, `"listitem"`, `"heading"`… | Papel para la accesibilidad y comportamiento de teclado asociado (ver [Accesibilidad](#accesibilidad)). No cambia el aspecto. |
| `disabled` | bool | Activa `:disabled`, deja de recibir eventos de puntero y teclado y sale del orden de Tab. |
| `checked`, `selected`, `expanded` | bool | Estados que exponen `:checked`, `:selected`, `:expanded` a los estilos y a la accesibilidad. |
| `draggable` | bool | La caja se puede arrastrar: ver [Arrastrar y soltar](#arrastrar-y-soltar). |
| `tabindex` | `0` (entra en el orden de Tab), `-1` (enfocable solo por código) | Como en HTML. Por defecto, solo los papeles interactivos (`as="button"`…) son enfocables. |
| `label` | texto | Nombre accesible . |
| `title` | texto | Descripción emergente al dejar el ratón encima (tooltip del sistema). |
| `id`, `ref` | como en los demás elementos | `ref` da `.focus()`, `.blur()`, `.scroll_to(...)` si desborda, `.rect` (posición y tamaño). |
| `on:...` | ver [Eventos](#eventos) | |
| Disposición abreviada | `direction`, `gap`, `padding`, `wrap`, `align`, `justify`, `flex`, `width`, `height` | Atajos de las propiedades CSS equivalentes, para casos rápidos (`<flex direction="column" gap={8}>`). |

Contenido: cualquier elemento, `{#if}`, `{#each}`, slots y texto suelto (que se convierte en `<Text>`).

### `Column` y `Row`

Pasan a ser **atajos** de `<flex direction="column">` y `<flex direction="row">`, con sus valores por defecto actuales (en una columna, los bloques ocupan el ancho; en una fila, los hijos se centran en vertical). El código existente no cambia de significado.

Por dentro, el compilador los dispone con un layout de Qt (en C++, como los `ColumnLayout`/`RowLayout` de antes) siempre que la caja y sus hijos usen solo lo que ese layout hace igual que el motor de `<flex>`; si no, usa el motor. El resultado en pantalla es el mismo; cambia la velocidad. Ver [Vía rápida](#vía-rápida-layouts-de-qt).

## Los estilos

`<flex>` amplía el subconjunto de CSS de [estilos.md](estilos.md). Lo que no aparece aquí sigue sin estar soportado (advertencia del compilador).

### Disposición: flexbox

| Propiedad | Valores |
|---|---|
| `direction` (alias `flex-direction`) | `row` (por defecto, como en CSS), `column`, `row-reverse`, `column-reverse` |
| `flex-wrap` (alias `wrap`) | `nowrap` (por defecto), `wrap` |
| `gap`, `row-gap`, `column-gap` | px |
| `justify-content` | `start`, `center`, `end`, `space-between`, `space-around`, `space-evenly` |
| `align-items` | `start`, `center`, `end`, `stretch` (por defecto, como en CSS), `baseline` |
| `align-content` | igual que `justify-content` y `stretch` (filas de un contenedor con `wrap`) |
| En los hijos: `flex`, `flex-grow`, `flex-shrink`, `flex-basis`, `align-self`, `order` | como en CSS (`flex: 1` = `1 1 0`) |
| `width`, `height`, `min-*`, `max-*` | px, `%` (del contenedor), `auto`, `fit-content` |
| `aspect-ratio` | `16 / 9`, `1` |

Diferencias deliberadas con CSS, documentadas:

- `direction` en `<flex>` vale `row` por defecto, como en la web; `Column` sigue existiendo para la columna.
- No hay `display`: todo `<flex>` es un contenedor flex. Para ocultar, `visible={False}` o `{#if}`.
- No hay flujo de texto en línea (`inline`): el texto vive en `<Text>`, que es un bloque.

**Rejilla**: con `flex-wrap: wrap` y `flex-basis` (o `min-width`) se hacen rejillas que se recolocan al cambiar el ancho. No hay `display: grid`.

### Caja

| Propiedad | Valores |
|---|---|
| `padding`, `padding-*` | como en los demás elementos |
| `margin`, `margin-*` | px, `auto` (empuja, como en flexbox: `margin-left: auto`). Sin colapso de márgenes |
| `background`, `background-color` | color, token; `linear-gradient(<ángulo>, <color>, <color>…)` |
| `border`, `border-color`, `border-width`, `border-style` | como en los demás elementos; `border-style`: `solid`, `none` |
| `border-top`, `-right`, `-bottom`, `-left` | bordes por lado (separadores, pestañas) |
| `border-radius` | 1 a 4 valores (radio por esquina) |
| `box-shadow` | `0 2px 8px rgba(0,0,0,.15)`; varias sombras separadas por comas; `inset` no |
| `outline`, `outline-offset` | anillo de foco que no ocupa espacio |
| `opacity`, `visibility` | `visibility: hidden` ocupa sitio sin verse |
| `overflow` | `visible` (por defecto), `hidden` (recorta), `auto`/`scroll` (desplazamiento: el `<flex>` se convierte en zona de scroll) |
| `cursor` | `default`, `pointer`, `text`, `move`, `grab`, `grabbing`, `not-allowed`, `ew-resize`, `ns-resize`… |
| `transform` | `scale()`, `rotate()`, `translate()`; no afecta a la disposición, como en CSS |
| `pointer-events` | `none` (deja pasar el ratón a lo de debajo), `auto` |

### Posición

| Propiedad | Valores |
|---|---|
| `position` | `static` (por defecto), `relative`, `absolute`, `fixed` |
| `top`, `right`, `bottom`, `left`, `inset` | px, `%` |
| `z-index` | entero |

Un hijo con `position: absolute` sale del flujo y se coloca respecto al `<flex>` antecesor más cercano con `position: relative` o `absolute` (como en la web). Sirve para insignias sobre un icono, botones de cerrar en una esquina, superposiciones y menús emergentes. `position: fixed` (respecto a la ventana) se valora con los menús.

### Texto heredado

Igual que en CSS, estas propiedades puestas en un `<flex>` las **heredan** los `<Text>` (y el texto de los controles) que contiene, a cualquier profundidad, hasta que alguien las cambie:

`color`, `font-family`, `font-size`, `font-weight`, `font-style`, `line-height`, `letter-spacing`, `text-align`, `text-transform`, `white-space` (`normal`, `nowrap`), `text-overflow` (`ellipsis`).

La herencia **atraviesa los componentes y los slots**: el texto que el padre pasa a `<Boton>` toma el color del botón. Resuelve la carencia 16 del reto del panel (la fila seleccionada no podía cambiar el color de su texto).

### Estados (pseudo-clases)

| Pseudo-clase | Cuándo |
|---|---|
| `:hover` | el puntero está encima (también si está encima de un hijo) |
| `:pressed` (alias `:active`) | se está pulsando con el ratón, el dedo o Espacio/Intro |
| `:focus` | tiene el foco del teclado |
| `:focus-visible` | tiene el foco y llegó con el teclado (para el anillo de foco, sin mostrarlo al hacer clic) |
| `:focus-within` | él o un descendiente tiene el foco |
| `:disabled` | `disabled={True}` |
| `:checked`, `:selected`, `:expanded` | el atributo correspondiente es verdadero |
| `:dragging` | la caja se está arrastrando |
| `:drag-over` | se arrastra algo encima de esta caja, que tiene `on:drop` |
| `:first-child`, `:last-child` | primero o último entre sus hermanos (también dentro de `{#each}`) |

- Se combinan con clases: `.boton.primary:hover`.
- Las cambia JanelKit directamente en la vista: pasar el ratón por encima **no llama a Python**.
- `transition` anima los cambios (también `transform` y `box-shadow`).

### Selectores

| Selector | Ejemplo | Notas |
|---|---|---|
| Clase, elemento, varios | `.a`, `flex`, `.a, .b` | como en los demás elementos |
| Compuesto | `.boton.primary`, `flex.tarjeta` | |
| Pseudo-clase | `.fila:hover` | |
| Descendiente | `.tarjeta .titulo`, `.tarjeta:hover .acciones` | **Nuevo.** Dentro del mismo componente |
| Hijo directo | `.menu > .item` | **Nuevo.** |

**Alcance (como el CSS con ámbito de Vue o Svelte):** los estilos de un componente solo afectan a los elementos escritos en **su** plantilla, incluido el contenido que él pasa a los slots de sus hijos; nunca al interior de otro componente. Para personalizar el interior de un componente se usan sus props, sus clases en la etiqueta (`class` en la etiqueta va a su raíz) o sus variables (siguiente apartado). Así un componente de una biblioteca no se rompe por una regla de quien lo usa.

**Precedencia como en CSS:** gana la regla más específica y, a igualdad, la que aparece después. Sin especificidad, `.tarjeta:hover .acciones` perdía siempre contra un `.acciones` posterior, que es justo lo que escribe quien viene de la web. Con selectores de una sola clase todas empatan y decide el orden, como antes. Los estilos en línea (`style=`) ganarán a todas; las reglas que dependen de una clase condicional del propio elemento siguen ganando a las demás, como hoy.

### Variables propias

```css
.tarjeta { --acento: var(--primary); border-left: 3px solid var(--acento); }
.tarjeta.alerta { --acento: var(--danger); }
.titulo { color: var(--acento); }
```

- Una propiedad que empieza por `--` define una variable **en ese elemento y sus descendientes**, también dentro de componentes hijos. `var(--x)` toma la del antecesor más cercano y, si no hay, el token del tema; `var(--x, valor)` admite un valor por defecto.
- Es la forma de que un componente ofrezca puntos de personalización sin exponer su interior: `Boton.janel` usa `var(--boton-fondo, var(--surface))` y quien lo usa escribe `<Boton style="--boton-fondo: #222">`.
- Se pueden cambiar en estados (`.tarjeta:hover { --acento: … }`) y con `style={...}` desde Python.

### Unidades

`px` (o números sin unidad), `%`, `ms`/`s` en transiciones y `deg` en rotaciones. Sin `em`/`rem` en esta versión.

## Eventos

Todos se escuchan con `on:` y el manejador está en Python (función o en línea). Solo se envían a Python los eventos que tienen manejador.

| Evento | Cuándo | `event` |
|---|---|---|
| `on:click` | clic principal, o Espacio/Intro en un `<flex>` con papel interactivo | `PointerEvent` |
| `on:dblclick` | doble clic | `PointerEvent` |
| `on:contextmenu` | clic derecho, tecla de menú o pulsación larga | `PointerEvent` |
| `on:pointerdown`, `on:pointerup` | se pulsa o se suelta cualquier botón | `PointerEvent` |
| `on:pointerenter`, `on:pointerleave` | el puntero entra o sale (sin propagación, como en la web) | `PointerEvent` |
| `on:pointermove` | el puntero se mueve encima (solo con manejador: es frecuente) | `PointerEvent` |
| `on:wheel` | rueda o gesto de desplazamiento | `WheelEvent` |
| `on:keydown`, `on:keyup` | tecla, con el foco en el `<flex>` o en un descendiente | `KeyEvent` |
| `on:focus`, `on:blur` | gana o pierde el foco (`focusin`/`focusout` para descendientes) | `FocusEvent` |
| `on:resize` | cambia su tamaño | `{"width", "height"}` |
| `on:dragstart`, `on:dragover`, `on:drop`, `on:dragend` | arrastrar y soltar: ver [Arrastrar y soltar](#arrastrar-y-soltar) | `DragEvent` |

```python
from janelkit import KeyEvent, PointerEvent   # tipos públicos, para anotar

def al_pulsar_tecla(event: KeyEvent):
    if event.key == "Delete" and not event.repeat:
        borrar(seleccion.value)
        event.prevent()          # nadie más la procesa (p. ej. la ventana)

def menu(event: PointerEvent):
    abrir_menu(en=(event.window_x, event.window_y))
```

| Tipo | Atributos |
|---|---|
| `PointerEvent` | `x`, `y` (respecto al elemento), `window_x`, `window_y`, `button` (`"left"`, `"right"`, `"middle"`), `buttons`, `ctrl`, `shift`, `alt`, `meta`, `pointer` (`"mouse"`, `"touch"`, `"pen"`), `clicks` |
| `KeyEvent` | `key` (nombres como en la web: `"a"`, `"Enter"`, `"Escape"`, `"ArrowUp"`, `"Delete"`…), `code` (tecla física), `text`, `repeat`, `ctrl`, `shift`, `alt`, `meta` |
| `WheelEvent` | `dx`, `dy` (píxeles), y los modificadores |
| `FocusEvent` | `reason` (`"tab"`, `"click"`, `"code"`) |

Todos tienen:

- **`event.prevent()`**: cancela el comportamiento por defecto. Por ejemplo, que Espacio active un botón, que la rueda desplace una zona con `overflow: auto` o que una tecla llegue a un `<Shortcut>`.
- **`event.stop()`**: el evento no sigue hacia los `<flex>` antecesores.

**Propagación** como en la web: el evento empieza en el `<flex>` más profundo que está bajo el puntero o que tiene el foco y sube por sus antecesores. Esto es posible sin JavaScript porque los manejadores de Python se ejecutan en el momento, en el mismo hilo que la interfaz, y JanelKit lee `prevent()`/`stop()` al volver.

Un manejador `async def` también se puede usar, pero `prevent()` y `stop()` solo tienen efecto antes de su primer `await`.

### Arrastrar y soltar

Una caja con `draggable` se arrastra al pulsarla y mover el puntero más que la distancia de arrastre del sistema (una pulsación corta sigue siendo un clic). Lo que se arrastra es un valor de Python, no texto:

```html
<flex class="tarjeta" draggable on:dragstart={event.data = tarjeta["id"]}>…</flex>

<flex class="columna" on:drop={mover(event.data, columna)}>…</flex>

<style>
.tarjeta:dragging { opacity: 0.4; }      /* la original, mientras su copia sigue al puntero */
.columna:drag-over { background: var(--surface-alt); }
</style>
```

| Evento | Dónde | Cuándo |
|---|---|---|
| `on:dragstart` | la caja `draggable` y sus antecesores | Empieza el arrastre. Pon `event.data`; `event.prevent()` lo cancela. |
| `on:dragover` | las cajas bajo el puntero (propagación) | El puntero se mueve durante el arrastre. `event.x`/`event.y` sirven para decidir en qué posición se soltaría. |
| `on:drop` | la caja con `on:drop` más profunda bajo el puntero (y las de fuera si no hace `stop()`) | Se suelta. Solo las cajas con `on:drop` son destino y se marcan con `:drag-over`. |
| `on:dragend` | la caja `draggable` y sus antecesores | Termina, con `event.dropped` (`False` si se soltó fuera o se pulsó Escape). Si `on:drop` quitó la caja (la movió a otra lista), no llega. |

Todos reciben un `DragEvent`: lo de `PointerEvent` más `.data` y `.dropped`. Mientras se arrastra, una imagen de la caja sigue al puntero, el teclado no hace nada más que Escape (cancela) y no hay clic al soltar. Cerca del borde (40 px) de una zona con desplazamiento (`<List>`, `<Scroll>`, `overflow: auto`), esta avanza sola, más deprisa cuanto más cerca. Funciona dentro de una ventana; arrastrar entre ventanas o desde otras aplicaciones (archivos) no entra en esta versión. En pruebas, `Element.drag_to(destino)` (`janelkit.inspect`).

## Accesibilidad

`as` da el papel accesible y el teclado que la gente espera, sin código:

| `as` | Enfocable con Tab | Teclado incluido | Estados que expone |
|---|---|---|---|
| `box` (por defecto) | no | — | — |
| `button` | sí | Espacio/Intro → `on:click` | `:pressed`, `:disabled` |
| `link` | sí | Intro → `on:click` | — |
| `checkbox`, `switch` | sí | Espacio → `on:click` | `checked` |
| `tab`, `menuitem`, `option`, `listitem` | según el contenedor | las flechas no se gestionan solas en esta versión: el componente las programa con `on:keydown` | `selected` |
| `dialog`, `heading`, `region` | no | — | — |

- El anillo de foco no es automático: se dibuja con `:focus-visible` (en los ejemplos, con `outline`). El tema base ofrece una clase y un token (`--focus-ring`) para no repetirlo.
- `label` y `title` como se describió. Un `<flex as="button">` sin texto ni `label` produce una **advertencia del compilador**, porque el lector de pantalla no tendría qué leer.

## Componentes construidos sobre `<flex>`

Un componente cuya raíz es un `<flex>` se usa **como un elemento más**:

1. **Atributos que pasan a la raíz.** En un componente cuya raíz es un `<flex>`, lo que la etiqueta lleva y el componente no declara como prop pasa a esa raíz: `class` (se suma a la suya), `style` (se mezcla), `id`, `label`, `title`, `tabindex`, `disabled`, y los eventos nativos (`on:click`, `on:keydown`…). Así funciona `<Boton on:click={...}>` sin que `Boton` declare `click = event()`. Si el componente declara una prop o un evento con ese nombre, gana lo declarado. Se desactiva por componente con `inherit_attrs = False` en el script (como `inheritAttrs` de Vue); entonces el componente recibe esos atributos en `attrs` y decide dónde ponerlos.
2. **`class` en la etiqueta va a la raíz**, sin caja exterior.
3. **`ref` en la etiqueta** apunta a la raíz (`.focus()` en un `<Boton>` enfoca su `<flex>`).
4. Los **estilos de la raíz** pueden depender de los atributos recibidos: `disabled` en la etiqueta activa `:disabled` en la raíz.

Con esto, una biblioteca de componentes puede escribirse en `.janel` puro, como se haría en Vue o Svelte.

## Cómo se comporta por dentro

Esto no es API, pero condiciona el diseño:

- **Motor de disposición propio.** Los `Layout` de Qt Quick no tienen salto de línea, márgenes, `space-between`, `order` ni posición absoluta dentro del flujo. `<flex>` usa un motor flexbox propio (un subconjunto del algoritmo de CSS, `Janel/flex.js`):
  - Cada elemento avisa a su contenedor con un binding que depende de lo que afecta a su sitio (`Layout.*`, `flex`, márgenes…). El contenedor pasa a una cola.
  - La cola se vacía en la fase de *polish* de Qt Quick, justo antes de sincronizar el fotograma (`JkPolisher`, un `QQuickItem` de Python por ventana). Nunca se dibuja un fotograma a medio colocar, y muchos cambios seguidos cuestan una sola pasada.
  - Se coloca de fuera adentro: un contenedor coloca en la misma pasada los contenedores de dentro a los que cambia el tamaño. Lo leído de cada hijo se guarda hasta que el hijo avisa.
  - Un contenedor recién creado se coloca enseguida si lo crea algo que lee su tamaño al momento (una `<List>`, un layout de Qt).
  - Lecciones de rendimiento del motor JS de Qt: `Set`/`Map` buscan de forma lineal, `for…of` es varias veces más lento que un bucle con índice, y un binding que recorre todos los hijos se vuelve cuadrático al añadirlos uno a uno.
- **Vía rápida: layouts de Qt.** Ver la sección siguiente.
- **Estados sin Python.** `:hover`, `:pressed`, `:focus…` y `:disabled` se compilan a estados de la vista. Python solo interviene si hay un manejador `on:`.
- **Herencia y variables.** Se resuelven en el compilador cuando el antecesor está en la misma plantilla, y en la vista cuando cruzan un componente o un slot.
- **Selectores de descendientes.** Se resuelven en el compilador, porque los estilos tienen ámbito y la plantilla se conoce entera.
- **Sombras.** Se dibujan con el efecto de sombra de Qt Quick (disponible desde Qt 6.5; JanelKit exige 6.8).
- **Rendimiento.** Un `<flex>` sin estados, sombra ni eventos cuesta lo mismo que un `Column`.

## Vía rápida: layouts de Qt

El motor de `<flex>` está en JS y lee y escribe propiedades de cada hijo en cada pasada. Medido con 300 tarjetas en columna (unas 1500 cajas; cada tarjeta con cabecera, un texto que se corta y dos botones), los `ColumnLayout`/`RowLayout` de Qt con los que empezaron `Column` y `Row` eran unas 6 veces más rápidos al cambiar el ancho de la ventana. Por eso el compilador elige, caja a caja:

- **Layout de Qt** (`JkColumn`, `JkRow` y `JkQtBox`, sobre un `GridLayout`): para `Column`, `Row` y `<flex direction="column">` que usan dirección (sin `-reverse`), `gap`, `padding`, bordes, `align-items`/`align-self` (sin `baseline`), márgenes fijos, tamaños en px, mínimos y máximos, y un solo hijo con `flex` (o solo `<Spacer>`).
- **Motor de `<flex>`** (`JkFlexColumn`, `JkFlexRow` y `JkFlex`) si la caja usa `wrap`, `justify-content` u `overflow: auto`, o algún hijo usa `order`, `margin: auto`, tamaños en `%`, `position`, `flex-shrink`, `flex-basis` o `:first-child`/`:last-child`; si varios hijos tienen `flex` (Qt no reparte en proporción como `flex: N 1 0`); si hay contenido de un `<Slot />` (no se conoce al compilar); para las cajas implícitas de `{#if}`/`{#each}` y las cajas exteriores de componentes; y para `<flex>` en fila (encoge como CSS, y un layout de Qt no encoge lo que no crece). En `<flex direction="column">`, cualquier hijo con `flex` también lleva al motor.

Se decide al compilar con todo lo que la caja y sus hijos pueden llegar a tener, también en estados y clases condicionales. De un componente hijo se miran las reglas de su raíz en su propio `<style>` (`compiler/layout_choice.py`). Las dos vías comparten `JkBox.qml` (aspecto, estados, eventos, accesibilidad), así que solo cambia quién coloca a los hijos. Un detalle de Qt: con espacio de sobra y ningún hijo que crezca, un layout reparte el hueco entre los hijos; en flexbox se queda al final. Por eso el layout no pasa de su tamaño máximo en el eje principal.

**Dentro de una caja con el motor, también el motor.** El motor lee al momento el tamaño de cada hijo; un layout de Qt lo calcula más tarde, en su propio *polish*. Por eso una caja que va directamente dentro de otra con el motor usa también el motor, y lo mismo la raíz de un componente que se usa ahí: la página se compila antes que sus componentes y les deja anotado dónde van. `<Scroll>` no cuenta: su contenido suele ser una columna grande, y como layout de Qt cambia de ancho antes. Cuando aun así queda un layout de Qt dentro del motor (en un `<Scroll>`, o un componente compilado aparte), flex.js lo coloca al momento con `ensurePolished()`, y también las cajas del motor que tenga dentro (las que el compilador marca con `jkDeep`), antes de leer su alto. Medido (`apps/examples/flex/bench.py`, ventana real, rejilla de 200 tarjetas de `Tarjeta.janel`): sin nada de esto, 40 ms por fotograma con picos de casi 3 s; solo colocando al momento, 24 ms; con la raíz de la tarjeta en el motor, 17 ms, como antes de la vía rápida.

Medido sin pantalla (Windows 11, la misma interfaz de 300 tarjetas en QML; mediana de 120 cambios de ancho):

| | Crear | Cambiar el ancho, por paso |
|---|---|---|
| `ColumnLayout`/`RowLayout` de Qt (referencia) | ~60 ms | ~4 ms |
| `Column`/`Row` con el motor de `<flex>` | ~300 ms | ~32 ms |
| `Column`/`Row` con la vía rápida | ~285 ms | ~9 ms |
| Vía rápida y cajas y textos ligeros (abajo) | ~205 ms | ~6,5 ms |

- Cambiar el ancho es unas 5 veces más rápido que con el motor, y queda a algo más de una vez y media de los layouts de Qt sin más. La diferencia que queda es de `Text` y de la caja: cada `JkText` es un `Label` de Qt Quick Controls, y cada caja tiene borde, estados y eventos.
- Crear sigue costando unas 3 veces más que con los layouts de Qt sin más: el coste está en la propia caja y en el texto (abajo).
- Comprobado que las dos vías colocan igual: la misma página con las dos (`packages/janelkit/tests/test_layout_choice.py`) y todos los ejemplos de `apps/examples/` montados de las dos formas, comparando la posición y el tamaño de cada elemento a dos anchos.

### Cajas y textos ligeros: cada pieza, solo si se usa

Una caja vacía costaba ~50 µs al crearse (un `Rectangle`, ~2 µs) y un `<Text>` ~43 µs (un `Label`, ~11 µs), aunque no usaran casi nada. Ahora cada pieza se crea solo cuando hace falta (`jk.js`, `flexDecorations` y `textDecorations`):

| Pieza | Se crea si… |
|---|---|
| `JkHover.qml` (ratón encima) | `on:click`, una regla `:hover`, `cursor` o `title` |
| `JkTap.qml` (pulsación) | `on:click` o una regla `:pressed` |
| `JkRole.qml` (lector de pantalla, Espacio/Intro) | un papel distinto de `box` (`as="..."` u `on:click`), también si cambia al ejecutar |
| `JkTranslate.qml` | `transform: translate(...)` distinto de cero |
| `JkTextBox.qml` (fondo y borde de un `<Text>`) | `background` o `border` en el texto |
| `JkTextLinks.qml` (mano sobre los enlaces) | `format="markdown"` o `"html"` |

Además: el aviso de cada hijo a su contenedor (`jkTouch`) solo se calcula si el contenedor usa el motor de `<flex>` (un layout de Qt lee los `Layout.*` por su cuenta); `padding-top`, `row-gap` y los demás por lado no cuestan un binding cada uno si no se fijan (valen `NaN` y se usa `padding` o `gap`); los colores de borde por lado los resuelve `JkSides`, que solo existe con bordes por lado; y se quitaron dos `Layout.preferred*` por elemento que ya no hacían nada. Una caja con `label` pero sin papel sigue oculta a los lectores de pantalla (el compilador le pone `Accessible.ignored`).

Medido: una caja vacía, ~32 µs; un `<Text>`, ~30 µs; las 300 tarjetas en QML, de ~285 a ~205 ms al crear y de ~9 a ~6,5 ms al cambiar el ancho; desde `.janel` (con Python), de ~425 a ~325 ms al crear. En la lista de 1000 filas de `tools/bench.py`, donde manda Python, crear baja de ~470 a ~430 ms. Lo que queda por caja son sobre todo sus ~90 propiedades y los bindings del aspecto (color, borde, foco); escribir los `Layout.*` en línea en vez de llamar a `jk.js` no ahorra nada (medido). Pruebas: `packages/janelkit/tests/test_flex_lazy.py`.

## Límites y diferencias con CSS

- `direction` es `row` por defecto, como en la web; `Column` es un atajo. `Column` y `Row` están hechos sobre `<flex>`, y sus bordes ocupan sitio, como en CSS.
- Sin `em`/`rem`, sin `display: grid` y sin `aspect-ratio`.
- Una sola sombra por caja, sin `inset`; con `overflow: hidden`, la caja recorta su sombra.
- `:first-child` cuenta los hermanos visibles. `:focus-visible` en una caja es tener el foco (las cajas solo lo toman con Tab o por código).
- `z-index` ordena solo entre hermanos: en QML no hay contextos de apilamiento como en CSS, así que hay que subir también el del contenedor. Un `absolute` sin `top`/`left` va al principio del contenedor, no a su sitio en el flujo.
- `on:click` lo entrega Qt: un `<Button>` dentro de una fila se queda el clic. `prevent()` no detiene los `<Shortcut>` (Qt los resuelve antes que la ventana). Sin pulsación larga para `on:contextmenu`. `on:resize` llega una vez por vuelta del bucle de eventos.
- `as="switch"` se anuncia como casilla. La navegación con flechas en grupos (`tab`, `menuitem`) la programa el componente, con `on:keydown` y `ref.focus()`.
- El texto heredado llega a los `<Text>`, no al texto de los controles de Qt. `var(--x)` sin valor por defecto es un token del tema, salvo que el propio componente defina `--x`. `style={{...}}` admite las propiedades de un solo valor y variables.
- Con `inherit_attrs = False`, los atributos de la etiqueta van a una caja exterior. Lo que la etiqueta fija gana siempre a los estilos propios del componente, sin comparar especificidad.
- El motor de disposición está en JavaScript (~27 µs por recolocación). Los tiempos medidos están en [rendimiento.md](rendimiento.md#flex-y-rejillas).
