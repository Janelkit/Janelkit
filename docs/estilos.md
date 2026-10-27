# Estilos, disposición y temas

Qt Quick no es un navegador y FluxUI **no implementa CSS**. `<style>` admite una lista corta de propiedades que se traducen a propiedades de Qt Quick. Todo lo demás produce una **advertencia** con su ubicación y se ignora.

## Selectores

- De clase: `.titulo { … }` → elementos con `class="titulo"`.
- De elemento: `Button { … }` → todos los `<Button>` del componente (también `flex { … }`).
- Varios selectores separados por comas: `.a, .b { … }`.
- Compuestos: `.boton.primary`, `flex.tarjeta`.
- De descendiente: `.tarjeta .titulo` (a cualquier profundidad) y de hijo directo: `.menu > .item`. Cuentan los elementos de la plantilla, también a través de `{#if}` y `{#each}`.
- Pseudo-clases (estados): ver la tabla siguiente. `.fila:hover`, `.tarjeta:hover .acciones`, `.boton.primary:pressed`.
- Clases condicionales: `class:activa={cond}` en el elemento aplica `.activa` mientras `cond` sea verdadera.
- Clases dinámicas: `class={["tarjeta", variante, {"activa": sel}]}` (texto, listas o diccionarios `{clase: condición}`).

| Pseudo-clase | Cuándo |
|---|---|
| `:hover` | el puntero está encima (también encima de un hijo) |
| `:pressed` (o `:active`) | se está pulsando con el ratón o el dedo; en una caja con `on:click`, también con Espacio |
| `:focus` | tiene el foco del teclado |
| `:focus-visible` | tiene el foco y llegó con el teclado (las cajas solo lo toman con Tab) |
| `:focus-within` | él o algo de dentro tiene el foco |
| `:disabled` | `enabled={False}` |
| `:checked`, `:selected`, `:expanded` | el atributo es verdadero (`Checkbox`, `Switch`; en `<flex>`, `checked`, `selected`, `expanded`) |
| `:first-child`, `:last-child` | primero o último entre los hermanos visibles de su contenedor (también dentro de `{#each}`) |

Los estados los cambia la vista: pasar el ratón por encima **no llama a Python**. `transition` anima los cambios. En una caja con `on:click`, una regla `:hover` sustituye al resaltado por defecto, y una regla con `outline`, al anillo de foco por defecto.

Los estilos son **locales al componente**: afectan a los elementos escritos en su plantilla (también el contenido que pasa a los slots de sus hijos), nunca al interior de otro componente. En el contenido de un slot, un selector de descendiente puede usar las clases fijas de los antecesores de fuera, pero no sus estados ni sus clases condicionales (el compilador avisa).

**Precedencia, como en CSS:** gana la regla más específica (cuenta clases y pseudo-clases; a igualdad, elementos) y, a igualdad, la que aparece después en `<style>`. `.tarjeta:hover .acciones` gana a `.acciones` aunque esté antes. Los atributos escritos en el elemento ganan a las reglas sin estado (`gap={4}` gana a `.page { gap: 20px }`); las reglas con estado (pseudo-clases, `class:x`, `class={...}`) ganan a los atributos. Las reglas que dependen de una clase condicional o dinámica del propio elemento se aplican por encima de las demás.

## Valores

- Números: `16px` o `16`.
- Colores: `#rgb`, `#rrggbb`, `#aarrggbb`, nombres (`red`), `rgb(…)`, `rgba(…)`.
- **Tokens del tema:** `var(--primary)`, `var(--space-4)`… Se enlazan al tema activo y cambian al cambiar de tema.

## Propiedades

| CSS | Aplica a | Notas |
|---|---|---|
| `color` | Text, Button, TextField, TextArea, Checkbox; flex, Column, Row (lo heredan sus `<Text>`) | color del texto |
| `background`, `background-color` | Window, flex, Column, Row, Scroll, List, Text, Button, TextField, TextArea, Select | en `Text`, con `padding` y `border-radius`, sirve para etiquetas y contadores |
| `border` | los mismos que `background` (salvo Window) | `1px solid #ccc`, `1px solid var(--border)`, `none` |
| `border-color`, `border-width` | ídem | |
| `border-top`, `-right`, `-bottom`, `-left` (y `-width`, `-color`) | flex, Column, Row | bordes por lado (separadores). Con radio, los lados son rectos en las esquinas |
| `border-radius` | ídem | 1 valor; de 2 a 4 (radio por esquina, como en CSS) solo en flex, Column y Row |
| `overflow` | flex, Column, Row | `visible`, `hidden` (recorta, sin redondear las esquinas), `auto`/`scroll` (zona de desplazamiento) |
| `padding` | contenedores y controles con texto | 1 a 4 valores, como en CSS |
| `padding-top`, `-right`, `-bottom`, `-left` | ídem | |
| `gap` | flex, Column, Row, Scroll | separación entre hijos |
| `row-gap`, `column-gap` | flex, Column, Row | separación entre filas / entre columnas |
| `flex-direction` (o `direction`) | flex | `row` (por defecto), `column`, `row-reverse`, `column-reverse` |
| `flex-wrap` | flex, Column, Row | `nowrap`, `wrap` (salto de línea: rejillas) |
| `font-size` | Window y controles con texto | en Window se hereda en toda la ventana |
| `font-weight` | ídem | `100`–`1000`, `normal`, `bold`, `lighter`, `bolder` |
| `font-family` | ídem | `"Inter"` o un token |
| `font-style` | ídem | `italic`, `normal` |
| `letter-spacing` | controles con texto | px |
| `text-transform` | controles con texto | `uppercase`, `lowercase`, `capitalize`, `none` |
| `text-align` | Text, TextField, TextArea | `left`, `center`, `right`, `justify` |
| `line-height` | Text, flex, Column, Row | factor sin unidades (`1.4`) |
| `white-space` | Text, flex, Column, Row | `normal`, `nowrap` (una sola línea) |
| `text-overflow` | Text, flex, Column, Row | `ellipsis` (puntos suspensivos al cortar), `clip` |
| `--nombre` | flex, Column, Row | variable propia: `--acento: var(--primary)`; se lee con `var(--acento)` (ver abajo) |
| `align-items` | flex, Column, Row, Scroll | `start`, `center`, `end`, `stretch`; `baseline` en flex, Column y Row |
| `justify-content` | flex, Column, Row, Scroll | `start`, `center`, `end`, `space-between`, `space-around`, `space-evenly` |
| `align-content` | flex, Column, Row | como `justify-content` y `stretch`: reparto entre líneas con `flex-wrap` |
| `flex` | todos salvo Window | `1` (= `1 1 0`), `1 0 200px` (crecer, encoger, base), `auto`, `none` |
| `flex-grow`, `flex-shrink`, `flex-basis` | todos salvo Window | como en CSS; `flex-grow` solo deja la base en `auto` |
| `order` | todos salvo Window | entero: orden dentro del contenedor |
| `margin`, `margin-top`, `-right`, `-bottom`, `-left` | todos salvo Window | px o `auto` (empuja: `margin-left: auto`). Sin colapso de márgenes |
| `align-self` | todos salvo Window | `start`, `center`, `end`, `stretch` |
| `width`, `height` | todos | px, `%` del contenedor, `auto`; `100%` ocupa el espacio disponible |
| `min-width`, `max-width`, `min-height`, `max-height` | todos | px |
| `opacity` | todos | `0`–`1` |
| `transform` | todos salvo Window | `scale(n)`, `rotate(Ndeg)`, `translate(x, y)`, `translateX()`, `translateY()`, `none`. Desde el centro y sin afectar a la disposición, como en CSS |
| `cursor` | todos salvo Window | `default`, `pointer`, `text`, `move`, `grab`, `grabbing`, `not-allowed`, `wait`, `crosshair`, `ew-resize`, `ns-resize`… |
| `box-shadow` | flex, Column, Row | `0 2px 8px rgba(0, 0, 0, .15)` (x, y, desenfoque, extensión, color). Una sombra (si hay varias, avisa y usa la primera); sin `inset`. Con `overflow: hidden`, la caja recorta su sombra |
| `outline`, `outline-width`, `-color`, `-offset` | flex, Column, Row | anillo que no ocupa sitio (`2px solid var(--primary)`); con `outline-offset` negativo, por dentro |
| `pointer-events` | flex, Column, Row | `none`: la caja no recibe el ratón (ni `:hover`, ni clic, ni cursor); sus hijos sí |
| `visibility` | flex, Column, Row | `hidden`: ocupa su sitio sin verse (ni recibir eventos); `visible` |
| `transition` | todos salvo Window | `background 200ms, opacity .3s` o `all 150ms`: anima los cambios de `color`, `background`, `border-color`, `opacity`, `width`, `height`, `border-radius` y `transform`, y en las cajas `box-shadow` y `outline` (también los que provocan los estados y las clases condicionales o dinámicas). |

No soportado todavía (advertencia): `position: sticky`, `em`/`rem`, `display: grid`, animaciones con `@keyframes`.

## Posición

| Propiedad | Valores |
|---|---|
| `position` | `static` (por defecto), `relative`, `absolute`, `fixed` |
| `top`, `right`, `bottom`, `left` | px o `%`; `auto` |
| `inset` | de 1 a 4 valores, como `margin` (`inset: 0` ocupa todo) |
| `z-index` | entero |

- `relative`: el elemento se desplaza desde su sitio (`top: 4px`) sin mover a los demás, y sirve de referencia a los `absolute` de dentro.
- `absolute`: sale del flujo (no ocupa sitio) y se coloca respecto a la caja antecesora más cercana con `position` (dentro de su borde); si no hay ninguna, respecto a la ventana. Con `left` y `right` (o `top` y `bottom`) y sin tamaño propio, se estira entre ellos; los `%` son del tamaño de esa caja.
- `fixed`: como `absolute`, siempre respecto a la ventana; sigue a la ventana al redimensionar. Sirve para velos y diálogos.
- Una caja `absolute` o `fixed` no deja pasar el puntero a lo que hay debajo (un velo no deja pulsar los botones que tapa).
- `z-index` ordena **entre hermanos** (los de la misma caja). Para que un menú emergente quede sobre lo que viene después de su caja, sube también el `z-index` de esa caja (`.zona { position: relative; z-index: 1 }`). Un velo `fixed` conviene ponerlo al final de la raíz.
- Sin `top`/`left`/`right`/`bottom`, un `absolute` va al principio de su contenedor (en CSS iría donde le tocaría en el flujo).
- Desde Python: `style={{"left": x, "top": y}}` (números en px o textos como `"50%"`).

## Texto heredado

Como en CSS, `color`, `font-family`, `font-size`, `font-weight`, `font-style`, `letter-spacing`, `text-transform`, `text-align`, `line-height`, `white-space` y `text-overflow` puestos en una caja (`<flex>`, `Column`, `Row`) los **heredan** los `<Text>` que contiene, a cualquier profundidad, también dentro de otros componentes y en el contenido de los slots, salvo que el `<Text>` fije los suyos. Así, la fila elegida de una tabla cambia el color de todo su texto con una regla:

```css
.fila:selected { background: var(--primary); color: var(--on-primary); }
```

Hoy lo heredan los `<Text>`; el texto de los controles de Qt (`Button`, `TextField`…) sigue con su propio estilo.

## Variables propias

```css
.tarjeta { --acento: var(--primary); border-left: 3px solid var(--acento); }
.tarjeta.alerta { --acento: var(--danger); }
.tarjeta:hover { --acento: var(--success); }
.titulo { color: var(--acento); }
```

- `--nombre: valor` en una caja define una variable para ella y todo lo que contiene, también dentro de otros componentes. Puede cambiar con estados y clases.
- `var(--nombre)` busca la variable en los antecesores si **este componente** la define; si no, es un token del tema, como siempre. Para leer una variable que define quien usa el componente, ponle un valor por defecto: `var(--boton-fondo, var(--surface))`.
- Desde Python: `style={{"--acento": color}}`.

## Estilos en línea: `style`

- `style="gap: 4px; background: #222"`: las mismas propiedades que `<style>`, para un elemento.
- `style={{"background": color, "width": f"{pct}%", "--acento": acento}}`: valores calculados en Python, que se actualizan solos. Admite `background`, `color`, `border-color`, `border-width`, `border-radius`, `opacity`, `gap`, `padding`, `font-size`, `width`, `height` (px o `%`) y variables `--x`.
- Los estilos en línea ganan a las reglas y a los estados (`:hover` no los cambia). Ver las fases de [flex.md](flex.md).

## Disposición

Toda la disposición la hace el motor de [`<flex>`](flex.md), un subconjunto del flexbox de CSS. `<flex>` sigue los valores por defecto de la web (fila, `align-items: stretch`, los hijos encogen si no caben). `Column` y `Row` son atajos de `<flex>` con los valores por defecto de siempre:

- Los hijos se colocan en orden, separados por `gap`. El espacio sobrante **no** se reparte entre ellos: queda al final, salvo que `justify-content` diga otra cosa.
- `flex: 1` (o el atributo `flex={1}`) hace que un hijo ocupe el espacio libre del eje principal (alto en una `Column`, ancho en una `Row`). Si varios tienen `flex`, se lo reparten **en proporción**, sin importar su contenido (como `flex: N 1 0` en CSS): `flex: 2` y `flex: 1` reciben dos tercios y un tercio del espacio que dejan los demás.
- El reparto proporcional se aplica cuando el tamaño del contenedor en ese eje viene de fuera (llena la ventana, tiene `flex` o se estira). Si el contenedor se ajusta a su contenido, cada hijo toma su tamaño natural.
- En la etiqueta de un componente (`<Panel flex={2} />`), `flex` se aplica a su raíz si es una caja; si no, a una caja exterior que la raíz ocupa entera (ver "Estilos en la etiqueta del componente" en [lenguaje.md](lenguaje.md)).
- En una `Column`, `Text`, `TextField`, `TextArea`, `Column`, `Row` y `Scroll` ocupan todo el ancho por defecto (como bloques); botones y casillas conservan su tamaño. `align-items` en el contenedor (o `align-self` en el hijo) cambia ese comportamiento.
- En una `Row`, los hijos se centran verticalmente por defecto.
- `width`/`height` en px fijan el tamaño preferido; `100%` ocupa el espacio disponible en ese eje; otro porcentaje es del contenedor.
- En `Column` y `Row` solo encoge lo que tiene `flex` (en `<flex>`, todo, como en CSS, sin bajar del contenido mínimo: un texto que se corta puede estrecharse; un botón, no).
- La raíz de la ventana ocupa la ventana entera.

**Rejilla con `flex-wrap`** (se recoloca al cambiar el ancho, sin Python):

```html
<flex class="rejilla">{#each fichas as f}<Ficha class="celda" … />{/each}</flex>
<style>
.rejilla { flex-wrap: wrap; gap: 12px; align-items: start; }
.celda { flex: 1 1 200px; }   /* parte de 200 px, crece; las que no caben saltan de línea */
</style>
```

Un bloque `{#if}` o `{#each}` con varios elementos se agrupa en una caja que copia la dirección, la separación y la alineación de su contenedor; con `flex-wrap`, sus elementos saltan de línea dentro de esa caja, no junto con los hermanos de fuera.

```html
<Row class="app">
  <Column class="sidebar">…</Column>      <!-- ancho fijo, alto completo -->
  <Column class="main">…</Column>         <!-- ocupa el resto -->
</Row>
<style>
.sidebar { width: 260px; align-self: stretch; background: var(--surface-alt); }
.main { flex: 1; align-self: stretch; padding: 24px; }
</style>
```

## Controles base y temas

Los elementos se dibujan con un conjunto propio de controles (módulo QML interno `Flux`) que usa los tokens del tema: el mismo código se ve coherente en Windows, macOS y Linux, y cambia de aspecto al cambiar de tema.

`Button` tiene variantes: `variant="primary"`, `"danger"`, `"ghost"` (sin fondo) y `"default"`.

### Tokens

| Token | Uso |
|---|---|
| `--bg`, `--surface`, `--surface-alt` | fondos: ventana, tarjetas/campos, zonas secundarias |
| `--text`, `--text-muted` | texto principal y secundario |
| `--border` | bordes |
| `--primary`, `--on-primary` | color de acento y texto sobre él |
| `--danger`, `--on-danger`, `--success`, `--warning` | estados |
| `--hover`, `--pressed` | capas semitransparentes para interacción |
| `--radius-sm`, `--radius`, `--radius-lg` | radios (4, 8, 14) |
| `--font-family`, `--font-size-sm`, `--font-size`, `--font-size-lg`, `--font-size-xl` | tipografía (12, 14, 18, 24) |
| `--space-1` … `--space-6` | espacios (4, 8, 12, 16, 24, 32) |

Un `var(--x)` que no existe en el tema activo produce una advertencia al arrancar, con su ubicación.

### API de temas

```python
from fluxui import theme

theme.set("dark")                      # "light" (por defecto) o "dark"
theme.toggle()                         # alterna claro/oscuro
theme.extend("light", brand="#7048e8") # añade/cambia tokens (sin nombre: en todos los temas)
theme.define("sepia", base="light", bg="#f4ecd8", text="#433422")
theme.name                             # reactivo: {theme.name} en la plantilla se actualiza
```

En CSS, los nombres con guiones bajos se escriben con guiones: `brand_dark` → `var(--brand-dark)`.
