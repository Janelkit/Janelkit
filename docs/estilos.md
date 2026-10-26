# Estilos soportados (subconjunto CSS)

Qt Quick no es un navegador y FluxUI **no implementa CSS**. `<style>` admite una lista corta de propiedades que se traducen a propiedades de Qt Quick. Todo lo demás produce una **advertencia** con su ubicación y se ignora.

## Selectores

- De clase: `.titulo { … }` → elementos con `class="titulo"`.
- De elemento: `Button { … }` → todos los `<Button>` del componente.
- Varios selectores separados por comas: `.a, .b { … }`.

Sin descendientes, pseudo-clases ni combinadores. Los estilos son **locales al componente**.

**Precedencia:** reglas de elemento, después reglas de clase (en orden del archivo; la última gana) y, por encima de todo, los atributos escritos en el elemento (`gap={4}` gana a `.page { gap: 20px }`).

## Propiedades

| CSS | Qt Quick | Aplica a | Valores |
|---|---|---|---|
| `padding` | `padding` | Column, Row, Text, Button, TextField, Checkbox | `24px` o `24` |
| `gap` | `spacing` | Column, Row | `16px` |
| `font-size` | `font.pixelSize` | Text, Button, TextField, Checkbox | `18px` |
| `font-weight` | `font.weight` | ídem | `100`–`1000`, `normal`, `bold`, `lighter`, `bolder` |
| `font-family` | `font.family` | ídem | `"Inter"` |
| `font-style` | `font.italic` | ídem | `italic`, `normal` |
| `color` | `color` | Text, TextField | `#rgb`, `#rrggbb`, `#aarrggbb`, nombres, `rgb()`, `rgba()` |
| `background` / `background-color` | `color` | Window | colores |
| `width`, `height` | `width`, `height` | todos | `px` |
| `opacity` | `opacity` | todos | `0`–`1` |

Pendiente para el Incremento 6: bordes, radios, fondos de controles, alineación, tokens de tema y temas claro/oscuro.
