# Estilos, disposición y temas

Qt Quick no es un navegador y FluxUI **no implementa CSS**. `<style>` admite una lista corta de propiedades que se traducen a propiedades de Qt Quick. Todo lo demás produce una **advertencia** con su ubicación y se ignora.

## Selectores

- De clase: `.titulo { … }` → elementos con `class="titulo"`.
- De elemento: `Button { … }` → todos los `<Button>` del componente (también `flex { … }`).
- Varios selectores separados por comas: `.a, .b { … }`.
- Clases condicionales: `class:activa={cond}` en el elemento aplica `.activa` mientras `cond` sea verdadera.
- Clases dinámicas: `class={["tarjeta", variante, {"activa": sel}]}` (texto, listas o diccionarios `{clase: condición}`). Entre clases gana la regla que aparece después en `<style>`; las `class:x={cond}` se aplican por encima.

Sin descendientes, pseudo-clases ni combinadores. Los estilos son **locales al componente**: las clases de un componente no afectan a sus hijos.

**Precedencia:** reglas de elemento, después reglas de clase (en orden del archivo; la última gana), después los atributos escritos en el elemento (`gap={4}` gana a `.page { gap: 20px }`) y, por encima de todo, las clases condicionales activas (si varias fijan lo mismo, gana la última declarada en el elemento).

## Valores

- Números: `16px` o `16`.
- Colores: `#rgb`, `#rrggbb`, `#aarrggbb`, nombres (`red`), `rgb(…)`, `rgba(…)`.
- **Tokens del tema:** `var(--primary)`, `var(--space-4)`… Se enlazan al tema activo y cambian al cambiar de tema.

## Propiedades

| CSS | Aplica a | Notas |
|---|---|---|
| `color` | Text, Button, TextField, TextArea, Checkbox | color del texto |
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
| `line-height` | Text | factor sin unidades (`1.4`) |
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
| `transition` | todos salvo Window | `background 200ms, opacity .3s` o `all 150ms`: anima los cambios de `color`, `background`, `border-color`, `opacity`, `width`, `height` y `border-radius` (también los que provoca una clase condicional o dinámica). |

No soportado todavía (advertencia): sombras, posiciones absolutas, pseudo-clases (`:hover`…), selectores de descendientes, variables propias, `em`/`rem`, `display: grid`, animaciones. Ver las fases de [flex.md](flex.md).

## Disposición

Toda la disposición la hace el motor de [`<flex>`](flex.md), un subconjunto del flexbox de CSS. `<flex>` sigue los valores por defecto de la web (fila, `align-items: stretch`, los hijos encogen si no caben). `Column` y `Row` son atajos de `<flex>` con los valores por defecto de siempre:

- Los hijos se colocan en orden, separados por `gap`. El espacio sobrante **no** se reparte entre ellos: queda al final, salvo que `justify-content` diga otra cosa.
- `flex: 1` (o el atributo `flex={1}`) hace que un hijo ocupe el espacio libre del eje principal (alto en una `Column`, ancho en una `Row`). Si varios tienen `flex`, se lo reparten **en proporción**, sin importar su contenido (como `flex: N 1 0` en CSS): `flex: 2` y `flex: 1` reciben dos tercios y un tercio del espacio que dejan los demás.
- El reparto proporcional se aplica cuando el tamaño del contenedor en ese eje viene de fuera (llena la ventana, tiene `flex` o se estira). Si el contenedor se ajusta a su contenido, cada hijo toma su tamaño natural.
- En la etiqueta de un componente (`<Panel flex={2} />`), `flex` se aplica a una caja exterior y la raíz del componente la ocupa entera.
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
