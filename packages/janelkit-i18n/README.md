# janelkit-i18n

[![PyPI](https://img.shields.io/pypi/v/janelkit-i18n)](https://pypi.org/project/janelkit-i18n/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit-i18n)](https://pypi.org/project/janelkit-i18n/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**Traducciones para aplicaciones [JanelKit](https://pypi.org/project/janelkit/):** catálogos JSON, plurales, formatos de número, moneda y fecha según el idioma, y cambio de idioma en caliente, también a idiomas que se escriben de derecha a izquierda.

```bash
pip install janelkit-i18n
```

## En un minuto

Un catálogo JSON por idioma:

```json
{
  "hello": "Hello, {name}",
  "files": {"zero": "No files", "one": "{n} file", "other": "{n} files"}
}
```

Se cargan en el script del componente:

```python
from pathlib import Path
from janelkit_i18n import i18n, t

i18n.load(Path(__file__).parent / "locales")   # locales/es.json, en.json, ar.json…
i18n.set("es")
```

Y se usan en la plantilla:

```html
<Text>{t("hello", name=name)}</Text>
<Text>{t("files", n=len(files))}</Text>
<Text>{i18n.number(total, 2)} · {i18n.currency(price, "€")} · {i18n.date(today, "long")}</Text>
<Button on:click={i18n.set("ar")}>العربية</Button>
```

Al llamar a `i18n.set()`, todos los textos se actualizan sin reiniciar la aplicación. En árabe, hebreo o persa, la interfaz entera se refleja.

## Características

- **Reactivo.** `t()` en la plantilla se actualiza solo al cambiar de idioma, como cualquier `state`.
- **Plurales.** Un diccionario con `zero` (opcional), `one` y `other`, que se elige con el parámetro `n`.
- **Formatos con las reglas del idioma.** Números, moneda y fechas mediante `QLocale` de Qt.
- **Derecha a izquierda.** El idioma de la interfaz es del núcleo (`janelkit.locale`): de él dependen la dirección de escritura y el `QLocale`. `i18n.set()` comprueba que haya catálogo y cambia ese idioma.
- **Sin sorpresas.** Si falta una clave en el idioma activo, se usa la de `i18n.default` y, si tampoco está, la propia clave, con un aviso en el logger `janelkit`.
- **Solo API pública.** No depende de nada interno del núcleo; una prueba del repositorio lo comprueba.

## Referencia

| Nombre | Descripción |
|---|---|
| `t` | `t(clave, **parámetros)` traduce al idioma activo. Es reactivo: en la plantilla se actualiza al cambiar de idioma. |
| `i18n` | Idioma y catálogos: `.load(carpeta)`, `.add(idioma, dict)`, `.set(idioma)`, `.language` y `.rtl` (los de `janelkit.locale`), `.languages`, `.default` (idioma de reserva, `"es"`), `.reset()`; formatos `.number(x, decimales)`, `.currency(x, "€")`, `.date(fecha, "short" \| "long")`. |
| `I18nError` | Catálogo no válido o idioma sin catálogo. |

Ejemplo completo, con español, inglés y árabe: [`apps/examples/idiomas`](https://github.com/janelkit/janelkit/tree/main/apps/examples/idiomas).

## Compatibilidad

| janelkit-i18n | janelkit | Python |
|---|---|---|
| 0.1.x | ≥ 0.1, < 0.2 | ≥ 3.10 |

Sigue la misma [política de versiones](https://github.com/janelkit/janelkit/blob/main/docs/api.md#paquetes-del-ecosistema) que el núcleo, con versión propia.

## Cambios

### 0.1.0

- Primera versión publicada. Antes era el módulo `janelkit.i18n` del núcleo: cambia `from janelkit import t, i18n` por `from janelkit_i18n import t, i18n`.
- Compatible con `janelkit` 0.1 (`janelkit>=0.1,<0.2`).

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).
