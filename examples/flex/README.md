# Catálogo de `<flex>`

Elementos construidos solo con `.flux` sobre `<flex>`, el elemento base de las cajas ([docs/flex.md](../../docs/flex.md)). Cada fase del diseño añade aquí los elementos que la validan; hoy, las fases 1 (caja y disposición), 2 (estados y selectores), 3 (eventos y accesibilidad), 4 (herencia y variables), 5 (componentes como elementos) y 6 (posición):

| Elemento | Archivo | Qué demuestra |
|---|---|---|
| Rejilla de tarjetas | `src/App.flux` (`.rejilla`, `.celda`) | `flex-wrap`, `flex: 1 1 200px`, `gap`: pasa de 4 a 2 y a 1 columna al estrechar la ventana, sin código Python |
| Tarjeta | `src/components/Tarjeta.flux` | columna, `margin-left: auto` (la etiqueta a la derecha), radio distinto por esquina; al pasar el ratón se eleva (`transform`, `box-shadow`) y muestra sus acciones (`.tarjeta:hover .acciones`, `:focus-within`) |
| Botón | `src/components/Boton.flux` | `as="button"` (Tab, Espacio, Intro, lector de pantalla); se usa como un elemento: `on:click`, `disabled` y `ref` van a la raíz sin declararlos, y las variantes son clases en la etiqueta (`<Boton class="primary">` activa `.boton.primary`); `:hover`, `:pressed` (`scale`), `:focus-visible` (`outline`), `:disabled`; el texto hereda el color |
| Chip | `src/components/Chip.flux` | se elige con un clic; su ✕ (otra caja con `on:click` dentro) lo quita con `event.stop()` para no elegirlo; `:selected`; `title` |
| Interruptor | `src/components/Interruptor.flux` | `as="switch"` con `checked` (Espacio lo cambia), `outline: none` y anillo de foco en la pista, pomo con `transform` |
| Tabla | `src/components/Tabla.flux` | la fila elegida (`:selected`) cambia fondo y `color` y todo su texto lo hereda; el color del estado es una variable (`--estado`) que fija cada fila y sustituye la elegida; cabecera con `text-transform` heredado |
| Pestañas segmentadas | `src/components/Segmentado.flux` | `as="tablist"`/`"tab"`, flechas con `on:keydown`; la pestaña elegida solo cambia `color` y `font-weight` en la caja |
| Diálogo | `src/components/Dialogo.flux` | velo `position: fixed; inset: 0` que no deja pulsar lo de debajo; `as="dialog"`; retiene el foco con `on:keydown` (Tab/Mayús+Tab), `event.prevent()` y `Ref.focused`; Escape o clic en el velo lo cierran; el foco vuelve al botón que lo abrió (`opener`) |
| Insignia | `src/App.flux` (`.insignia`) | `position: absolute; top: -6px; right: -6px` sobre el botón «Eliminar…», dentro de una caja `position: relative` |
| Menú | `src/components/Menu.flux` | `as="menu"`/`"menuitem"`, `tabindex`, flechas con `on:keydown` y `event.prevent()`, `on:pointerenter`, Escape; se abre con `on:contextmenu` (clic derecho o tecla de menú) en la zona del catálogo, y se coloca en el puntero (`class="emergente"` con `position: absolute` y `style={{"left": x, "top": y}}` en su etiqueta) |
| Barra de herramientas | `src/components/Barra.flux` | `justify-content: space-between`, grupos con `border-left` por lado, salto de línea al estrechar |

```bash
python main.py
python bench.py              # mediciones: montar y redimensionar 200 tarjetas
python bench.py --cards 500
```

Pruebas: `tests/test_example_flex.py` (el catálogo), `tests/test_flex_qt.py` (el motor) `tests/test_flex_states.py` (estados y selectores) `tests/test_flex_events.py` (eventos y accesibilidad), `tests/test_flex_inherit.py` (herencia y variables) `tests/test_flex_components.py` (componentes como elementos) y `tests/test_flex_position.py` (posición).
