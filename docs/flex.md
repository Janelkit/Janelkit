# Diseño de `<flex>`: el elemento base para construir componentes visuales

> **Estado: las 6 fases hechas** (caja y disposición; estados y selectores; eventos y accesibilidad; herencia y variables; componentes como elementos; posición; ver [Fases](#fases-de-implementación)). Lo demás es diseño aprobado, sin implementar. Este documento fija qué es `<flex>`, qué hace y qué no, cómo se escribe y cómo se comprobará que cumple. Las decisiones tomadas están al final.

## Por qué

Hoy, en FluxUI, se puede **componer** (componentes `.flux` con props, eventos y slots), pero no se puede **construir un control desde cero**. Un `Button` propio en `.flux` no puede:

- cambiar de aspecto al pasar el ratón, al pulsarlo o con el foco (no hay `:hover`, `:pressed`, `:focus`);
- reaccionar al puntero o al teclado más allá de `on:click`;
- dar color y tipo de letra a su texto desde el contenedor (no hay herencia ni selectores de descendientes);
- tener sombra, márgenes, posición absoluta o una rejilla que salte de línea.

Por eso los controles integrados están escritos en QML y quedan cerrados: solo se personalizan con tokens del tema y con una lista corta de propiedades.

En el frontend web, todo eso se hace con una caja (`<div>`), CSS y eventos. **`<flex>` es esa caja para FluxUI**: un elemento con el que cualquier persona pueda escribir en `.flux` un botón, una tarjeta, un chip, un elemento de menú o una barra de herramientas, con el aspecto y el comportamiento que espera de la web, **sin escribir JavaScript ni QML**. La lógica va en el `<script>` de Python; el aspecto, en `<style>`.

**`<flex>` no cubre todos los casos, y no lo pretende.** Es una **base**: el punto de partida para crear elementos nuevos a partir de él. Quien no es experto puede hacerse su propio botón, menú o diálogo con lo que ya sabe de la web, sin toparse con la barrera de aprender QML. El QML propio sigue disponible como vía de escape para lo que `<flex>` no alcanza (dibujo libre, gráficas).

> **Sin `.js` para el usuario.** Quien escribe la aplicación nunca escribe JavaScript: ni en la plantilla, ni en los estilos, ni en manejadores. Por dentro, FluxUI implementa `<flex>` en su módulo QML interno, como hace hoy con el resto de elementos; eso es un detalle interno y no forma parte de la API.

## Elementos base en minúscula

Regla del lenguaje: **los elementos base se escriben en minúscula** (`<flex>`, y el futuro elemento base de entrada); **los componentes, en mayúscula** (`<Boton>`, `<Tarjeta>`). Es la misma convención de la web con React o Svelte: `<div>` es primitivo, `<Boton>` es algo construido.

- De un vistazo se distingue en una plantilla qué es primitivo y qué está construido encima.
- Un componente nunca choca con un elemento base: `Flex.flux` sería un componente válido, distinto de `<flex>`.
- Las etiquetas en minúscula quedan reservadas para FluxUI. Una desconocida da error con la lista de elementos base, nunca la pista de importar un componente.
- Los controles integrados que existen hoy (`Column`, `Row`, `Text`, `Button`, `List`…) mantienen su nombre: no son elementos base, sino controles ya hechos o atajos (ver [`Column` y `Row`](#column-y-row)).

## Qué es y qué no es

`<flex>` es el **padre de los elementos visuales y de interacción**: cajas que se dibujan, se disponen, cambian de estado y responden al puntero y al teclado. No es el padre de todo:

| Familia | Elemento base | Para qué | Estado |
|---|---|---|---|
| **Cajas e interacción** | `<flex>` | Contenedores, tarjetas, botones, chips, menús, barras, rejillas, superposiciones | Este documento |
| **Entrada de datos** | Otro elemento base en minúscula (nombre por decidir: `<field>`, `<input>`) | Edición de texto, cursor y selección, método de entrada (IME), valor con `bind:value`, validación, autocompletado. Sobre él se escribirían campos, selectores, deslizadores… | Diseño aparte, después de `<flex>` |
| **Texto** | `<Text>` | Hoja: muestra texto (plano, Markdown, HTML). Hereda estilo de su `<flex>` contenedor | Existe |
| **Colecciones grandes** | `<List>` | Virtualización de miles de filas. Cada fila puede ser un `<flex>` | Existe |
| **Dibujo libre y gráficas** | Vía de escape QML / `fluxui-kit` | Gráficas, lienzos | Fuera del núcleo ([alcance.md](alcance.md)) |

Regla para decidir: si el comportamiento esencial es **editar un valor** (texto, número, fecha, selección de opciones con teclado de edición), pertenece a la familia de entrada, no a `<flex>`. Un interruptor o una casilla, que solo alternan, sí se pueden construir con `<flex>`; un campo de texto, no.

## Vistazo

```html
<!-- components/Boton.flux: un botón escrito entero en .flux -->
<script lang="python">
from fluxui import prop, event

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
- `:hover`, `:pressed`, `:focus-visible` y `:disabled` los resuelve FluxUI **sin pasar por Python**: no cuestan nada aunque haya cientos de botones.
- `as="button"` le da el papel de botón para la accesibilidad, el foco con Tab y la activación con Espacio/Intro.

## La plantilla

### Atributos

| Atributo | Valores | Qué hace |
|---|---|---|
| `class`, `class:x`, `class={expr}` | como hoy | Clases para `<style>`. |
| `style` | `style={{"background": color, "width": f"{pct}%"}}` o `style="gap: 4px"` | Estilos en línea, también calculados en Python. Ganan a las clases (como en la web). Acepta las mismas propiedades que `<style>`, no pseudo-clases. |
| `as` | `"box"` (por defecto), `"button"`, `"link"`, `"checkbox"`, `"switch"`, `"tab"`, `"menuitem"`, `"dialog"`, `"listitem"`, `"heading"`… | Papel para la accesibilidad y comportamiento de teclado asociado (ver [Accesibilidad](#accesibilidad)). No cambia el aspecto. |
| `disabled` | bool | Activa `:disabled`, deja de recibir eventos de puntero y teclado y sale del orden de Tab. |
| `checked`, `selected`, `expanded` | bool | Estados que exponen `:checked`, `:selected`, `:expanded` a los estilos y a la accesibilidad. |
| `draggable` | bool | La caja se puede arrastrar: ver [Arrastrar y soltar](#arrastrar-y-soltar). |
| `tabindex` | `0` (entra en el orden de Tab), `-1` (enfocable solo por código) | Como en HTML. Por defecto, solo los papeles interactivos (`as="button"`…) son enfocables. |
| `label` | texto | Nombre accesible (como hoy). |
| `title` | texto | Descripción emergente al dejar el ratón encima (tooltip del sistema). |
| `id`, `ref` | como hoy | `ref` da `.focus()`, `.blur()`, `.scroll_to(...)` si desborda, `.rect` (posición y tamaño). |
| `on:...` | ver [Eventos](#eventos) | |
| Disposición abreviada | `direction`, `gap`, `padding`, `wrap`, `align`, `justify`, `flex`, `width`, `height` | Atajos de las propiedades CSS equivalentes, para casos rápidos (`<flex direction="column" gap={8}>`). |

Contenido: cualquier elemento, `{#if}`, `{#each}`, slots y texto suelto (que se convierte en `<Text>`, como hoy).

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

**Rejilla**: con `flex-wrap: wrap` y `flex-basis` (o `min-width`) se hacen rejillas que se recolocan al cambiar el ancho (la carencia 13 del [reto del panel](../examples/challenges/panel/HALLAZGOS.md)). Un `display: grid` completo queda fuera de esta versión.

### Caja

| Propiedad | Valores |
|---|---|
| `padding`, `padding-*` | como hoy |
| `margin`, `margin-*` | px, `auto` (empuja, como en flexbox: `margin-left: auto`). Sin colapso de márgenes |
| `background`, `background-color` | color, token; `linear-gradient(<ángulo>, <color>, <color>…)` |
| `border`, `border-color`, `border-width`, `border-style` | como hoy; `border-style`: `solid`, `none` (`dashed` quizá más adelante) |
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
- Las cambia FluxUI directamente en la vista: pasar el ratón por encima **no llama a Python**.
- `transition` anima los cambios (incluidos `transform` y `box-shadow`, además de lo que ya anima hoy).

### Selectores

| Selector | Ejemplo | Notas |
|---|---|---|
| Clase, elemento, varios | `.a`, `flex`, `.a, .b` | como hoy |
| Compuesto | `.boton.primary`, `flex.tarjeta` | |
| Pseudo-clase | `.fila:hover` | |
| Descendiente | `.tarjeta .titulo`, `.tarjeta:hover .acciones` | **Nuevo.** Dentro del mismo componente |
| Hijo directo | `.menu > .item` | **Nuevo.** |

**Alcance (como el CSS con ámbito de Vue o Svelte):** los estilos de un componente solo afectan a los elementos escritos en **su** plantilla, incluido el contenido que él pasa a los slots de sus hijos; nunca al interior de otro componente. Para personalizar el interior de un componente se usan sus props, sus clases en la etiqueta (`class` en la etiqueta va a su raíz) o sus variables (siguiente apartado). Así un componente de una biblioteca no se rompe por una regla de quien lo usa.

**Precedencia como en CSS** (cambiado al implementar la fase 2; el diseño decía «sin especificidad»): gana la regla más específica y, a igualdad, la que aparece después. Sin especificidad, `.tarjeta:hover .acciones` perdía siempre contra un `.acciones` posterior, que es justo lo que escribe quien viene de la web. Con selectores de una sola clase todas empatan y decide el orden, como antes. Los estilos en línea (`style=`) ganarán a todas; las reglas que dependen de una clase condicional del propio elemento siguen ganando a las demás, como hoy.

### Variables propias

```css
.tarjeta { --acento: var(--primary); border-left: 3px solid var(--acento); }
.tarjeta.alerta { --acento: var(--danger); }
.titulo { color: var(--acento); }
```

- Una propiedad que empieza por `--` define una variable **en ese elemento y sus descendientes**, también dentro de componentes hijos. `var(--x)` toma la del antecesor más cercano y, si no hay, el token del tema; `var(--x, valor)` admite un valor por defecto.
- Es la forma de que un componente ofrezca puntos de personalización sin exponer su interior: `Boton.flux` usa `var(--boton-fondo, var(--surface))` y quien lo usa escribe `<Boton style="--boton-fondo: #222">`.
- Se pueden cambiar en estados (`.tarjeta:hover { --acento: … }`) y con `style={...}` desde Python.

### Unidades

`px` (o números sin unidad), `%`, `ms`/`s` en transiciones y `deg` en rotaciones. Sin `em`/`rem` en esta versión.

## Eventos

Todos se escuchan con `on:` y el manejador está en Python (función o en línea, como hoy). Solo se envían a Python los eventos que tienen manejador.

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
from fluxui import KeyEvent, PointerEvent   # tipos públicos, para anotar

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

**Propagación** como en la web: el evento empieza en el `<flex>` más profundo que está bajo el puntero o que tiene el foco y sube por sus antecesores. Esto es posible sin JavaScript porque los manejadores de Python se ejecutan en el momento, en el mismo hilo que la interfaz, y FluxUI lee `prevent()`/`stop()` al volver.

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

Todos reciben un `DragEvent`: lo de `PointerEvent` más `.data` y `.dropped`. Mientras se arrastra, una imagen de la caja sigue al puntero, el teclado no hace nada más que Escape (cancela) y no hay clic al soltar. Cerca del borde (40 px) de una zona con desplazamiento (`<List>`, `<Scroll>`, `overflow: auto`), esta avanza sola, más deprisa cuanto más cerca. Funciona dentro de una ventana; arrastrar entre ventanas o desde otras aplicaciones (archivos) no entra en esta versión. En pruebas, `Element.drag_to(destino)` (`fluxui.inspect`).

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

Para que un componente se use **como un elemento más**, se añade lo siguiente a los componentes `.flux`:

1. **Atributos que pasan a la raíz.** En un componente cuya raíz es un `<flex>`, lo que la etiqueta lleva y el componente no declara como prop pasa a esa raíz: `class` (se suma a la suya), `style` (se mezcla), `id`, `label`, `title`, `tabindex`, `disabled`, y los eventos nativos (`on:click`, `on:keydown`…). Así funciona `<Boton on:click={...}>` sin que `Boton` declare `click = event()`. Si el componente declara una prop o un evento con ese nombre, gana lo declarado. Se desactiva por componente con `inherit_attrs = False` en el script (como `inheritAttrs` de Vue); entonces el componente recibe esos atributos en `attrs` y decide dónde ponerlos.
2. **`class` en la etiqueta va a la raíz.** Hoy envuelve al componente en una caja exterior; con `<flex>` como raíz, se aplica a la raíz directamente, y la caja exterior desaparece.
3. **`ref` en la etiqueta** apunta a la raíz (`.focus()` en un `<Boton>` enfoca su `<flex>`).
4. Los **estilos de la raíz** pueden depender de los atributos recibidos: `disabled` en la etiqueta activa `:disabled` en la raíz.

Con esto, una biblioteca de componentes (la futura `fluxui-kit`) puede escribirse en `.flux` puro, como se haría en Vue o Svelte.

## Cómo se comporta por dentro

Esto no es API, pero condiciona el diseño:

- **Motor de disposición propio** (hecho en la fase 1). Los `Layout` de Qt Quick no tienen salto de línea, márgenes, `space-between`, `order` ni posición absoluta dentro del flujo. `<flex>` usa un motor flexbox propio (un subconjunto del algoritmo de CSS, `Flux/flex.js`):
  - Cada elemento avisa a su contenedor con un binding que depende de lo que afecta a su sitio (`Layout.*`, `flex`, márgenes…). El contenedor pasa a una cola.
  - La cola se vacía en la fase de *polish* de Qt Quick, justo antes de sincronizar el fotograma (`FxPolisher`, un `QQuickItem` de Python por ventana). Nunca se dibuja un fotograma a medio colocar, y muchos cambios seguidos cuestan una sola pasada.
  - Se coloca de fuera adentro: un contenedor coloca en la misma pasada los contenedores de dentro a los que cambia el tamaño. Lo leído de cada hijo se guarda hasta que el hijo avisa.
  - Un contenedor recién creado se coloca enseguida si lo crea algo que lee su tamaño al momento (una `<List>`, un layout de Qt).
  - Lecciones de rendimiento del motor JS de Qt: `Set`/`Map` buscan de forma lineal, `for…of` es varias veces más lento que un bucle con índice, y un binding que recorre todos los hijos se vuelve cuadrático al añadirlos uno a uno.
- **Vía rápida: layouts de Qt.** Ver la sección siguiente.
- **Estados sin Python.** `:hover`, `:pressed`, `:focus…` y `:disabled` se compilan a estados de la vista. Python solo interviene si hay un manejador `on:`.
- **Herencia y variables.** Se resuelven en el compilador cuando el antecesor está en la misma plantilla, y en la vista cuando cruzan un componente o un slot.
- **Selectores de descendientes.** Se resuelven en el compilador, porque los estilos tienen ámbito y la plantilla se conoce entera.
- **Sombras.** Se dibujan con el efecto de sombra de Qt Quick (disponible desde Qt 6.5; FluxUI exige 6.8).
- **Rendimiento.** Un `<flex>` sin estados, sombra ni eventos no debe costar más que el `Column` de hoy.

## Vía rápida: layouts de Qt

El motor de `<flex>` está en JS y lee y escribe propiedades de cada hijo en cada pasada. Medido con 300 tarjetas en columna (unas 1500 cajas; cada tarjeta con cabecera, un texto que se corta y dos botones), los `ColumnLayout`/`RowLayout` de Qt con los que empezaron `Column` y `Row` eran unas 6 veces más rápidos al cambiar el ancho de la ventana. Por eso el compilador elige, caja a caja:

- **Layout de Qt** (`FxColumn`, `FxRow` y `FxQtBox`, sobre un `GridLayout`): para `Column`, `Row` y `<flex direction="column">` que usan dirección (sin `-reverse`), `gap`, `padding`, bordes, `align-items`/`align-self` (sin `baseline`), márgenes fijos, tamaños en px, mínimos y máximos, y un solo hijo con `flex` (o solo `<Spacer>`).
- **Motor de `<flex>`** (`FxFlexColumn`, `FxFlexRow` y `FxFlex`) si la caja usa `wrap`, `justify-content` u `overflow: auto`, o algún hijo usa `order`, `margin: auto`, tamaños en `%`, `position`, `flex-shrink`, `flex-basis` o `:first-child`/`:last-child`; si varios hijos tienen `flex` (Qt no reparte en proporción como `flex: N 1 0`); si hay contenido de un `<Slot />` (no se conoce al compilar); para las cajas implícitas de `{#if}`/`{#each}` y las cajas exteriores de componentes; y para `<flex>` en fila (encoge como CSS, y un layout de Qt no encoge lo que no crece). En `<flex direction="column">`, cualquier hijo con `flex` también lleva al motor.

Se decide al compilar con todo lo que la caja y sus hijos pueden llegar a tener, también en estados y clases condicionales. De un componente hijo se miran las reglas de su raíz en su propio `<style>` (`compiler/layout_choice.py`). Las dos vías comparten `FxBox.qml` (aspecto, estados, eventos, accesibilidad), así que solo cambia quién coloca a los hijos. Un detalle de Qt: con espacio de sobra y ningún hijo que crezca, un layout reparte el hueco entre los hijos; en flexbox se queda al final. Por eso el layout no pasa de su tamaño máximo en el eje principal.

**Dentro de una caja con el motor, también el motor.** El motor lee al momento el tamaño de cada hijo; un layout de Qt lo calcula más tarde, en su propio *polish*. Por eso una caja que va directamente dentro de otra con el motor usa también el motor, y lo mismo la raíz de un componente que se usa ahí: la página se compila antes que sus componentes y les deja anotado dónde van. `<Scroll>` no cuenta: su contenido suele ser una columna grande, y como layout de Qt cambia de ancho antes. Cuando aun así queda un layout de Qt dentro del motor (en un `<Scroll>`, o un componente compilado aparte), flex.js lo coloca al momento con `ensurePolished()`, y también las cajas del motor que tenga dentro (las que el compilador marca con `fxDeep`), antes de leer su alto. Medido (`examples/flex/bench.py`, ventana real, rejilla de 200 tarjetas de `Tarjeta.flux`): sin nada de esto, 40 ms por fotograma con picos de casi 3 s; solo colocando al momento, 24 ms; con la raíz de la tarjeta en el motor, 17 ms, como antes de la vía rápida.

Medido sin pantalla (Windows 11, la misma interfaz de 300 tarjetas en QML; mediana de 120 cambios de ancho):

| | Crear | Cambiar el ancho, por paso |
|---|---|---|
| `ColumnLayout`/`RowLayout` de Qt (referencia) | ~60 ms | ~4 ms |
| `Column`/`Row` con el motor de `<flex>` | ~300 ms | ~32 ms |
| `Column`/`Row` con la vía rápida | ~285 ms | ~9 ms |
| Vía rápida y cajas y textos ligeros (abajo) | ~205 ms | ~6,5 ms |

- Cambiar el ancho es unas 5 veces más rápido que con el motor, y queda a algo más de una vez y media de los layouts de Qt sin más. La diferencia que queda es de `Text` y de la caja: cada `FxText` es un `Label` de Qt Quick Controls, y cada caja tiene borde, estados y eventos.
- Crear sigue costando unas 3 veces más que con los layouts de Qt sin más: el coste está en la propia caja y en el texto (abajo).
- Comprobado que las dos vías colocan igual: la misma página con las dos (`tests/test_layout_choice.py`) y todos los ejemplos de `examples/` montados de las dos formas, comparando la posición y el tamaño de cada elemento a dos anchos.

### Cajas y textos ligeros: cada pieza, solo si se usa

Una caja vacía costaba ~50 µs al crearse (un `Rectangle`, ~2 µs) y un `<Text>` ~43 µs (un `Label`, ~11 µs), aunque no usaran casi nada. Ahora cada pieza se crea solo cuando hace falta (`fx.js`, `flexDecorations` y `textDecorations`):

| Pieza | Se crea si… |
|---|---|
| `FxHover.qml` (ratón encima) | `on:click`, una regla `:hover`, `cursor` o `title` |
| `FxTap.qml` (pulsación) | `on:click` o una regla `:pressed` |
| `FxRole.qml` (lector de pantalla, Espacio/Intro) | un papel distinto de `box` (`as="..."` u `on:click`), también si cambia al ejecutar |
| `FxTranslate.qml` | `transform: translate(...)` distinto de cero |
| `FxTextBox.qml` (fondo y borde de un `<Text>`) | `background` o `border` en el texto |
| `FxTextLinks.qml` (mano sobre los enlaces) | `format="markdown"` o `"html"` |

Además: el aviso de cada hijo a su contenedor (`fxTouch`) solo se calcula si el contenedor usa el motor de `<flex>` (un layout de Qt lee los `Layout.*` por su cuenta); `padding-top`, `row-gap` y los demás por lado no cuestan un binding cada uno si no se fijan (valen `NaN` y se usa `padding` o `gap`); los colores de borde por lado los resuelve `FxSides`, que solo existe con bordes por lado; y se quitaron dos `Layout.preferred*` por elemento que ya no hacían nada. Una caja con `label` pero sin papel sigue oculta a los lectores de pantalla (el compilador le pone `Accessible.ignored`).

Medido: una caja vacía, ~32 µs; un `<Text>`, ~30 µs; las 300 tarjetas en QML, de ~285 a ~205 ms al crear y de ~9 a ~6,5 ms al cambiar el ancho; desde `.flux` (con Python), de ~425 a ~325 ms al crear. En la lista de 1000 filas de `tools/bench.py`, donde manda Python, crear baja de ~470 a ~430 ms. Lo que queda por caja son sobre todo sus ~90 propiedades y los bindings del aspecto (color, borde, foco); escribir los `Layout.*` en línea en vez de llamar a `fx.js` no ahorra nada (medido). Pruebas: `tests/test_flex_lazy.py`.

## Compatibilidad y versiones

- Todo es **sintaxis nueva**: los archivos actuales compilan igual y significan lo mismo. `FORMAT_VERSION` no cambia.
- `Column` y `Row` se reimplementan sobre `<flex>` conservando sus valores por defecto (hecho). Las pruebas de comportamiento pasaron sin cambios; tres que comprobaban nombres internos del QML generado (`align`, `justify`) se actualizaron. Diferencia visible: los bordes ocupan sitio, como en CSS.
- Los controles integrados (`Button`, `Checkbox`…) siguen existiendo. Los que no son de entrada (botón, casilla, interruptor) se reescribirán sobre `<flex>` cuando la paridad esté probada, sin cambiar su API.

## Cómo se comprobará: construir otros elementos con `<flex>`

La prueba de que `<flex>` cumple es poder escribir, **solo con `.flux`** (sin QML ni JavaScript), los elementos que una aplicación de escritorio necesita, con la calidad de la web. Vivirán en `examples/flex/` con pruebas de `fluxui.inspect` y capturas en tema claro y oscuro.

| Elemento | Qué demuestra | Criterio de aceptación |
|---|---|---|
| **Botón** (normal, primario, peligro, fantasma, solo icono, cargando) | estados, foco, papel, atributos que pasan a la raíz | Se usa como `<Boton on:click>`. Hover, pulsado, foco con teclado y deshabilitado se ven como en `Button`. Espacio/Intro lo activan. Al lector de pantalla llega como botón |
| **Tarjeta** con cabecera, cuerpo y acciones que aparecen al pasar el ratón | descendientes con estado (`.tarjeta:hover .acciones`), sombra, `overflow: hidden` | Las acciones aparecen con transición. La imagen se recorta al radio |
| **Chip / etiqueta** con botón de quitar | `margin-left: auto`, eventos anidados con `stop()` | Pulsar la ✕ no activa el chip |
| **Insignia sobre un icono** | `position: absolute` | El contador queda en la esquina sin mover el icono |
| **Interruptor** (como `Switch`) | `as="switch"`, `checked`, `transform`, transición | Se alterna con clic y Espacio; mismo aspecto que el integrado |
| **Elemento de menú y menú contextual** | `on:contextmenu`, posición absoluta, `z-index`, flechas | Abre en la posición del clic, se cierra con Escape y se navega con flechas (programadas en el componente con `on:keydown` y `ref.focus()`) |
| **Rejilla de tarjetas** | `flex-wrap`, `flex-basis`, `gap` | Pasa de 4 a 2 y a 1 columna al estrechar la ventana, sin código Python |
| **Barra de herramientas** con separadores | `border-left` por lado, `:first-child`, `justify-content: space-between` | |
| **Pestañas segmentadas** | `:selected`, variables propias (`--acento`) | El color de acento se cambia desde fuera con `style="--acento: …"` |
| **Diálogo superpuesto** | superposición absoluta, `as="dialog"`, `on:keydown`, `prevent()`, `ref.focus()` | Un componente `Dialogo.flux` sobre `<flex>`, no una función de `<flex>`: retiene el foco (Tab y Mayús+Tab con `prevent()`), se cierra con Escape y devuelve el foco al elemento que lo abrió |
| **Fila de tabla** con selección | herencia de `color` a los textos de la fila | El texto de la fila seleccionada cambia de color sin estilar cada `<Text>` |

Además:

- **Paridad:** el `Boton.flux` del ejemplo y el `Button` integrado se comparan en capturas y en el árbol de accesibilidad.
- **Rendimiento:** con 1 000 `<flex>` en pantalla, crearlos no puede tardar más que con `Column` + 10 %. Pasar el ratón no llama a Python. Una rejilla de 200 tarjetas con `wrap` se recoloca al redimensionar en menos de 4 ms por fotograma (instrumentación de Qt, como en `examples/challenges/panel/bench.py`).
- **Retos:** el Kanban (reto 3) está hecho sobre `<flex>` y trajo arrastrar y soltar ([hallazgos](../examples/challenges/kanban/HALLAZGOS.md)).

## Fases de implementación

1. **Caja y disposición:** `<flex>`, el motor flexbox (wrap, márgenes, `space-*`, `order`, `align-self`, `%`, mín./máx.), bordes por lado, radios por esquina, `overflow`. `Column`/`Row` pasan a ser atajos. Validación: rejilla y barra de herramientas. **Hecha** (`examples/flex`). Pendiente de esta fase: `aspect-ratio` y `min-width: 0` explícito, y el objetivo de rendimiento de la rejilla de 200 tarjetas, que hoy cuesta 14 ms por fotograma frente a 4 ms; con la fase 5 desaparece un tercio de las cajas. `style={...}` en línea llega en la fase 4.
2. **Estados y selectores:** pseudo-clases, selectores compuestos, de descendientes y de hijo, `transition` ampliada, `cursor`, `transform`, `box-shadow`, `outline`. Validación: tarjeta y botón (solo aspecto). **Hecha** (`examples/flex`: `Boton.flux`, `Tarjeta.flux`). Diferencias con el diseño: una sola sombra por caja, sin `inset`; la caja recorta su sombra con `overflow: hidden`; `:first-child` cuenta los hermanos visibles; `pointer-events` y `visibility` pasan a la fase 3.
3. **Eventos y accesibilidad:** eventos de puntero, teclado, rueda y foco con propagación, `prevent()`/`stop()`, `as`, `tabindex`, `title`. Validación: botón completo, chip, interruptor, menú. **Hecha** (`examples/flex`: `Boton`, `Chip`, `Interruptor`, `Menu`). Cómo funciona: un filtro de eventos en cada ventana (`qt_backend/events.py`) ve el ratón, la rueda y el teclado antes que Qt Quick, busca los elementos afectados y llama a sus manejadores de dentro afuera; con `prevent()` se queda el evento. Diferencias con el diseño: `on:click` lo sigue entregando Qt (un `<Button>` dentro de una fila se queda el clic, como antes) y entre cajas sube con el ratón y con el teclado; `prevent()` no detiene los `<Shortcut>` (Qt los resuelve antes de la ventana); sin pulsación larga para `on:contextmenu`; `:focus-visible` en una caja es tener el foco (las cajas solo lo toman con Tab o por código); `as="switch"` se anuncia como casilla; `on:resize` llega una vez por vuelta del bucle de eventos. Medido: crear 1000 filas sin eventos, 478 ms (+3 % frente a la fase 2); con `on:click`, 488 ms.
4. **Herencia y variables:** texto heredado y variables propias que atraviesan componentes, más `style={...}`. Validación: fila de tabla y pestañas segmentadas. **Hecha** (`examples/flex`: `Tabla`, `Segmentado`; el `Boton` ya no estila su texto). Cómo funciona: una caja que fija texto heredable o variables crea un contexto de estilo (`FxContext.qml`) que enlaza con el de fuera; un `<Text>` con contexto recibe lo heredado (un `FxTextInherit.qml`, que es un `Binding`, por cada propiedad que alguna caja de fuera fija y él no; el contexto solo dice qué claves hay, `keys`, y el valor se busca subiendo por la cadena), y los que no tienen no pagan nada. Diferencias con el diseño: lo heredan los `<Text>`, no el texto de los controles de Qt; `var(--x)` sin valor por defecto es un token del tema salvo que el propio componente defina `--x` (los tokens se pueden ampliar al ejecutar, así que el compilador no sabe distinguirlos); `style={{...}}` admite una lista corta de propiedades (las que tienen un solo valor) y variables. Medido: crear 1000 filas sin texto heredado no cambia (484 ms).
5. **Componentes como elementos:** atributos que pasan a la raíz (`inherit_attrs = False` para desactivarlo), `class` y `ref` en la raíz. Validación: todos los ejemplos usados como elementos. **Hecha** (`Boton` ya no declara `click`, `disabled` ni `variant`: se usa `<Boton class="primary" on:click=...>`; `tests/test_flex_components.py`). Cómo funciona: la etiqueta se convierte en un `FxRemote.qml` (el `Repeater` que crea el componente) con un `Binding` por propiedad sobre la raíz; los estados de la etiqueta se leen de la raíz; las clases llegan a la raíz en `fxInClass` para las reglas del propio componente; `flex.js` coloca la raíz donde está su `FxRemote`, también al reordenar filas. Diferencias con el diseño: con `inherit_attrs = False` no hay `attrs` para repartir a mano (los atributos van a una caja exterior, como antes); lo que la etiqueta fija gana siempre a los estilos propios del componente, sin comparar especificidad; transiciones, texto heredado y variables desde la etiqueta siguen usando una caja exterior. Medido: rejilla de 200 tarjetas del catálogo actual (cada una con dos `Boton`, unas 1100 cajas), 44 ms de mediana por paso al redimensionar (48 ms con la caja exterior); la tarjeta de la fase 1, 16 ms. **El objetivo de 4 ms no se cumple**: unos dos tercios del paso son el motor en JS (unas 1100 recolocaciones, ~27 µs cada una), y lo demás, Qt rehaciendo textos; ninguna de esas recolocaciones sobra (en la prueba los botones se encogen de verdad). Bajar de ahí pide otro enfoque (el motor en C++), fuera de lo que puede hacer un proyecto solo Python + QML.
6. **Posición:** `position`, `inset`, `z-index`. Validación: insignia y diálogo superpuesto. **Hecha** (`examples/flex`: insignia sobre el botón «Eliminar…», menú contextual abierto en el puntero, `Dialogo.flux`; `tests/test_flex_position.py`). Cómo funciona: `flex.js` saca del flujo a los hijos `absolute`/`fixed` y los coloca después de los demás, respecto a su bloque contenedor; `Fx.positionDeps` hace que se recoloquen cuando ese bloque cambia de tamaño o se mueve; un `FxBlocker.qml` (perezoso, solo en cajas `absolute`/`fixed`) impide que el puntero las atraviese. Diferencias con el diseño: también `position: fixed` (la necesitaba el diálogo); `z-index` ordena solo entre hermanos (en QML no hay contextos de apilamiento como en CSS: hay que subir también el `z-index` del contenedor); sin `top`/`left` un `absolute` va al principio del contenedor, no a su sitio en el flujo. `Ref.focused` (nuevo) permite al diálogo saber qué botón tiene el foco para retenerlo. Al validar salieron dos fallos del enrutador de eventos de la fase 3, corregidos: un elemento nuevo en la dirección de memoria de uno destruido heredaba sus manejadores, y pedir la ventana de un elemento desde Python en mitad de un evento invalidaba la ventana en `fluxui.inspect`.

Cada fase termina con sus pruebas, la documentación en [lenguaje.md](lenguaje.md) y [estilos.md](estilos.md), y una entrada en [cambios.md](cambios.md).

## Decisiones tomadas

| # | Pregunta | Decisión |
|---|---|---|
| 1 | ¿`direction` por defecto `row` o `column`? | `row`, como en la web. `Column` queda como atajo |
| 2 | Nombre y alcance del elemento base de entrada | Documento aparte tras la fase 3. Será un elemento base, en minúscula; candidatos: `<field>`, `<input>` |
| 3 | Sintaxis para desactivar el paso de atributos a la raíz | `inherit_attrs = False` en el script, como `inheritAttrs` de Vue |
| 4 | ¿`em`/`rem`? | No en esta versión |
| 5 | Navegación con flechas en grupos (`tab`, `menuitem`) | No en esta versión. El componente la programa con `on:keydown` y `ref.focus()` |
| 6 | Foco atrapado en diálogos | No es parte de `<flex>`: es un componente (`Dialogo.flux`) construido sobre él con eventos de teclado, `prevent()` y `ref.focus()`. Sirve además de prueba de que `<flex>` basta para construirlo |
| 7 | ¿`display: grid`? | No en esta versión; revisar tras la hoja de cálculo (reto 2) |
| 8 | ¿Reescribir los controles integrados sobre `<flex>`? | Sí, los que no son de entrada (botón, casilla, interruptor), cuando la paridad esté probada y sin cambiar su API |
| — | Mayúsculas y minúsculas | Los elementos base van en minúscula (`<flex>`); los componentes y controles, en mayúscula (ver [Elementos base en minúscula](#elementos-base-en-minúscula)) |
