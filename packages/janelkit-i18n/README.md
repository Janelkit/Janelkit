# janelkit-i18n

Traducciones para aplicaciones [JanelKit](../../README.md): catálogos JSON, plurales, formatos de número, moneda y fecha según el idioma, y cambio de idioma en caliente.

```bash
pip install janelkit-i18n         # en el repositorio: pip install -e packages/janelkit-i18n
```

```python
from pathlib import Path
from janelkit_i18n import i18n, t

i18n.load(Path(__file__).parent / "locales")   # locales/es.json, en.json, ar.json…
i18n.set("es")
```

```html
<Text>{t("saludo", nombre=nombre)}</Text>
<Text>{t("archivos", n=len(archivos))}</Text>
<Text>{i18n.number(total, 2)} · {i18n.date(hoy, "long")}</Text>
```

El idioma de la interfaz es del núcleo (`janelkit.locale`): de él dependen la dirección de escritura (en `ar`, `he`, `fa`… toda la interfaz se refleja) y el `QLocale` de Qt. `i18n.set()` comprueba que haya catálogo y cambia ese idioma. Solo usa la API pública del núcleo.

## Referencia

| Nombre | Descripción |
|---|---|
| `t` | `t(clave, **parámetros)` traduce al idioma activo. Reactivo: en la plantilla se actualiza al cambiar de idioma. |
| `i18n` | Idioma y catálogos: `.load(carpeta)`, `.add(idioma, dict)`, `.set(idioma)`, `.language` y `.rtl` (los de `janelkit.locale`), `.languages`, `.default` (idioma de reserva, `"es"`), `.reset()`; formatos `.number(x, decimales)`, `.currency(x, "€")`, `.date(fecha, "short" \| "long")`. |
| `I18nError` | Catálogo no válido o idioma sin catálogo. |

- Plurales: un diccionario con `zero` (opcional), `one` y `other`, elegido con el parámetro `n`.
- Si falta una clave en el idioma activo, se usa la de `i18n.default` y, si tampoco está, la propia clave, con un aviso en el logger `janelkit`.

Ejemplo: `apps/examples/idiomas` (español, inglés y árabe).

## Cambios

### 0.0.1.dev0 (sin publicar)

- Primera versión como paquete propio. Antes era el módulo `janelkit.i18n` del núcleo: cambia `from janelkit import t, i18n` por `from janelkit_i18n import t, i18n`.
- Compatible con `janelkit` 0.0.1.dev0 (prealfa); se ampliará al publicarse la 0.1 (`janelkit>=0.0.1.dev0,<0.1`).
