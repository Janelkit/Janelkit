# Cambios entre versiones

Cada versión lista lo nuevo y, aparte, lo que **rompe** código existente con cómo migrarlo. La política está en [api.md](api.md#política-de-versiones).

## 0.1.0 (sin publicar)

Primera versión pública prevista. Respecto a la prealfa interna (incrementos 0–7):

### Nuevo

- **Reactividad:** listas, diccionarios y conjuntos reactivos dentro de `state` (`items.value.append(x)`, `item["done"] = True`); `State.notify()`; `effect` con limpieza (la función devuelta se llama antes de repetir y al desmontar).
- **Plantilla:** manejadores en línea (`on:click={n += 1}`, `on:change={item["done"] = event}`, `on:click={borrar(item)}`).
- **Componentes:** slots (`<Slot />`, `<Slot name="x">`, `slot="x"`); `class`, `id` y `flex` en la etiqueta de un componente; `on_mount`, `on_destroy`; `ref`; `provide`/`inject`.
- **Asincronía:** manejadores `async def`, `@task` (`.loading`, `.error`, `.value`), `background()` y `spawn()`. Lo lanzado desde un componente se cancela al desmontarlo.
- **Elementos:** `Switch`, `Slider`, `Select`, `RadioGroup`, `Tabs`, `Image`, `ProgressBar`, `Shortcut`, `List` (virtualizada); `on:input` en `TextArea`; `label` (nombre accesible) en todos; `alt` en `Image`.
- **Diálogos:** `fluxui.dialogs` (abrir, guardar, carpeta, mensaje, confirmación), asíncronos.
- **Elementos propios en QML:** importar un `.qml` del proyecto como un componente.
- **Accesibilidad:** cajas con `on:click` accesibles con el teclado; foco visible; nombres accesibles.
- **Herramientas:** `fluxui.inspect` para probar aplicaciones; `fluxui.compiler.check_source`/`check_file` para editores; `FORMAT_VERSION`.
- **Disposición:** `flex` reparte el espacio en proporción, como en CSS.
- **Desplazamiento en `<List>`** (reto del chat): `follow`, `on:top`, `on:bottom`, `on:scroll`; `ref.scroll_to_end()`, `scroll_to_start()`, `scroll_to(i)`. Añadir filas ya no reinicia la lista, aunque sean muchas.
- **Texto enriquecido:** `<Text format="markdown">` (o `"html"`) y `on:link`.
- **Ventanas:** `on:activate` y `on:deactivate` en `<Window>`.
- **Notificaciones:** `fluxui.notify(título, mensaje)`, con icono en la bandeja del sistema.
- **Inspección:** `find(label=...)` y `Element.label`; `MountedApp.notifications()`; `MountedApp.windows()` para inspeccionar las ventanas abiertas con `open_window`.
- **Temporizadores** (reto del panel): `interval(ms, fn)` y `timeout(ms, fn)` (también como decoradores), ligados al componente; `Timer` con `.active`, `.start()`, `.restart()`, `.stop()`.
- **Formato en el texto:** `{cpu:.1f}`, `{n:,}`, `{x!r}`, como en un f-string.
- **Listas:** reordenar muchas filas de una `<List>` (una tabla que se ordena cada segundo) ya no la devuelve al principio.
- **Elementos propios en QML:** `flex` funciona como en los elementos de FluxUI.
- **`flux build`:** acepta los componentes con `<Window>` que solo se abren con `open_window`.
- **`<flex>`, el elemento base de las cajas (fase 1 de [flex.md](flex.md)):** flexbox de CSS en `.flux`: dirección, `flex-wrap` (rejillas que se recolocan solas), `row-gap`/`column-gap`, `justify-content` con `space-between`/`space-around`/`space-evenly`, `align-items: baseline`, `align-content`, `flex: crecer encoger base`, `flex-shrink`, `flex-basis`, `order`, `margin` (también `auto`), tamaños en `%`, bordes por lado, radio por esquina y `overflow` (`hidden`, `auto`, `scroll`). `Column` y `Row` pasan a ser atajos de `<flex>` y ganan todo lo anterior. Los elementos base se escriben en minúscula; una etiqueta en minúscula desconocida es un error. Ejemplo: `examples/flex`.
- **Estados y selectores (fase 2 de [flex.md](flex.md)):** pseudo-clases (`:hover`, `:pressed`/`:active`, `:focus`, `:focus-visible`, `:focus-within`, `:disabled`, `:checked`, `:selected`, `:expanded`, `:first-child`, `:last-child`), selectores compuestos (`.boton.primary`), de descendiente (`.tarjeta:hover .acciones`) y de hijo directo (`.menu > .item`). Nuevas propiedades: `transform`, `cursor`, `box-shadow`, `outline`; `transition` anima también `transform`, `box-shadow` y `outline`. `<flex>` admite `checked`, `selected` y `expanded`. Los estados no llaman a Python. En `fluxui.inspect`: `Element.hover()`, `unhover()`, `press()` y `release()`. Ejemplo: `Boton.flux` y `Tarjeta.flux` en `examples/flex`.
- **Eventos y accesibilidad en las cajas (fase 3 de [flex.md](flex.md)):** `on:dblclick`, `on:contextmenu`, `on:pointerdown`/`up`/`move`/`enter`/`leave`, `on:wheel`, `on:keydown`/`keyup`, `on:focus`/`blur` y `on:resize` en `<flex>`, `Column` y `Row`, con propagación como en la web, `event.prevent()` y `event.stop()`. Tipos públicos `PointerEvent`, `KeyEvent`, `WheelEvent`, `FocusEvent` y `ResizeEvent`. Atributos `as` (papel y teclado: `button`, `link`, `checkbox`, `switch`, `menuitem`…), `tabindex`, `disabled` y `title`; CSS `pointer-events` y `visibility`. Advertencia para una caja con papel de botón sin texto ni `label`. Ejemplo: `Chip.flux`, `Interruptor.flux` y `Menu.flux` en `examples/flex`.
- **Posición (fase 6 de [flex.md](flex.md)):** `position: relative | absolute | fixed`, `top`, `right`, `bottom`, `left`, `inset` y `z-index` (también en `style={{...}}`). Una caja `absolute` o `fixed` no deja pasar el puntero. `Ref.focused`. Ejemplos: insignia, menú en el puntero y `Dialogo.flux` (retiene el foco, Escape, devuelve el foco) en `examples/flex`.
- **Corrección (eventos):** un elemento creado en la dirección de memoria de otro ya destruido podía quedarse con los manejadores `on:` de aquel (p. ej. un diálogo abierto tras cerrar un menú no recibía `on:pointerdown`).
- **Componentes como elementos (fase 5 de [flex.md](flex.md)):** si la raíz de un componente es una caja, lo que su etiqueta lleva y él no declara (`class`, `style`, `label`, `title`, `disabled`, `ref`, `on:click`, `on:keydown`…) se aplica a esa raíz, sin caja exterior. Los estados de la etiqueta (`.celda:hover`) funcionan, y sus clases activan las reglas del componente (`<Boton class="primary">` activa `.boton.primary`). `inherit_attrs = False` lo desactiva.
- **Texto heredado, variables y estilos en línea (fase 4 de [flex.md](flex.md)):** `color`, la fuente, `text-align`, `line-height`, `white-space` y `text-overflow` puestos en una caja los heredan los `<Text>` de dentro, también en otros componentes y slots. Variables propias (`--acento: …`, `var(--acento)`, `var(--x, valor)`), que cambian con estados. `style="…"` y `style={{…}}` con valores de Python. Nuevas propiedades `white-space` y `text-overflow`. Ejemplo: `Tabla.flux` y `Segmentado.flux` en `examples/flex`.
- **Corrección:** una lista o diccionario de un `state` pasado entero a un control (`options={items}`, `values={serie}` en un QML propio) no se actualizaba al modificarlo en el sitio (`append`, `del`); ahora sí.

### Cambia (puede requerir ajustes)

| Antes | Ahora | Cómo migrar |
|---|---|---|
| `on:click={crear(x)}` llamaba a la función que devolvía `crear(x)`. | Una llamada en un manejador se **ejecuta** al ocurrir el evento. | Si `crear(x)` devuelve una función, escribe `on:click={lambda: crear(x)()}`, o llama directamente a lo que querías ejecutar. |
| `state([...])` guardaba la lista tal cual. | Guarda una **copia reactiva** (también de los diccionarios y listas anidados). | Modifica el objeto que devuelve `estado.value`, no el original que pasaste. Los `list`/`dict`/`set` siguen siendo instancias de esos tipos (`isinstance` funciona). |
| `flex` repartía según el tamaño del contenido. | `flex: N` reparte en proporción a N cuando el tamaño del contenedor viene de fuera. | Revisa las vistas que dependían del reparto anterior; normalmente basta con quitar anchos fijos que compensaban el reparto. |
| `Column` y `Row` eran `ColumnLayout`/`RowLayout` de Qt. | Son atajos de `<flex>`: los coloca el motor de FluxUI, con los mismos valores por defecto. Medido: crear 1000 cajas cuesta un 7 % menos. | Nada, salvo QML propio que leyera propiedades internas de `FxColumn`/`FxRow` (`align`, `stretch`, `justify` pasan a `alignItems` y `justifyContent`). Los bordes ahora ocupan sitio, como en CSS (el contenido empieza tras el borde). |
| Entre reglas, ganaba siempre la última del archivo; entre `class:x` activas, la última escrita en el elemento. | Gana la más específica, como en CSS, y a igualdad la última del archivo (también entre `class:x`). | Con selectores de una sola clase no cambia nada. Si dos `class:x` del mismo elemento fijan lo mismo, ordena sus reglas en `<style>`. |
| En una caja con `on:click`, el resaltado al pasar el ratón y el anillo de foco (el borde) eran fijos. | Una regla `:hover` sustituye al resaltado y una regla con `outline`, al anillo. | Nada. |
| `on:click` de una caja no recibía nada; entre cajas anidadas con `on:click`, el clic llegaba a las dos sin forma de evitarlo. | Recibe un `PointerEvent` (si la función lo acepta) y `event.stop()` corta la subida. Con Espacio o Intro también sube a las cajas de fuera con `on:click`. | Si una caja con `on:click` está dentro de otra con `on:click` y no quieres que reaccionen las dos, llama a `event.stop()` en la de dentro. |
| `class`, `flex`, `width`… en la etiqueta de un componente cuya raíz es una caja iban a una caja exterior. | Van a la raíz y ganan a sus estilos propios. | Si un estilo de la etiqueta pisa uno del componente que quieres conservar, quítalo de la etiqueta o usa `inherit_attrs = False`. |
| `on:click` sin declarar en la etiqueta de un componente era un error. | Si la raíz es una caja, es el clic en la raíz. | Nada. |
| `color` y la fuente no se podían poner en `Column`/`Row` (advertencia). | Se heredan a los `<Text>` de dentro. | Nada; si dependías de la advertencia, quita esas declaraciones. |
| `flex-grow: N` era lo mismo que `flex: N`. | Como en CSS: `flex-grow` solo no cambia la base (`auto`), `flex: N` parte de cero. | Usa `flex: N` para el reparto proporcional. |
| `justify-content: space-between`, márgenes o porcentajes daban una advertencia. | Funcionan. | Nada. |
| `TextArea value` se aplicaba directamente al texto. | Igual, pero `on:input` solo salta con los cambios del usuario. | Nada, salvo si dependías de que `bind:value` reaccionara a cambios programáticos. |
| Modificar estado desde otro hilo pasaba sin aviso (y podía corromperlo). | Lanza `WrongThreadError`. | Devuelve el valor desde `background()` y asígnalo tras el `await`. |
| `flux dev` intentaba recargar en el mismo proceso. | Los cambios en `.qml` propios reinician el proceso, como los `.py`. | Nada. |

### Requisitos

- Python ≥ 3.10.
- **PySide6 ≥ 6.8** (antes ≥ 6.6): con 6.6 había fallos de PySide al salir, botones sin `click()` y diálogos con tipos erróneos.
- Nueva dependencia: `qasync` ≥ 0.27 (integra `asyncio` con el bucle de Qt).
- Formato `.flux`: `FORMAT_VERSION = 1`.
