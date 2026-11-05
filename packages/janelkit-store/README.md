# janelkit-store

[![PyPI](https://img.shields.io/pypi/v/janelkit-store)](https://pypi.org/project/janelkit-store/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit-store)](https://pypi.org/project/janelkit-store/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**Los datos compartidos de una aplicación [JanelKit](https://pypi.org/project/janelkit/), en un solo sitio:** una clase con campos reactivos, acciones que agrupan y anotan cada cambio, escritura controlada si se quiere, una instancia por aplicación (la misma en todas las ventanas y vistas) y persistencia en disco.

```bash
pip install janelkit-store
```

## En un minuto

```python
# src/stores/carrito.py
from janelkit import background, computed
from janelkit_store import field, store

@store(strict=True, persist="carrito")
class Carrito:
    items: list[dict] = []
    nota: str = field("", bind=True)        # en un store estricto, solo los marcados admiten bind:
    _cache: dict = {}                       # con _: interno (ni reactivo, ni se anota, ni se guarda)

    @computed
    def total(self) -> float:               # derivado, en caché
        return sum(i["precio"] for i in self.items)

    def agregar(self, item):                # cada método es una acción
        self.items.append(item)

    async def cargar(self):
        self.items = await background(leer)  # tras el await sigue siendo «cargar»
```

```html
<script>
from janelkit_store import use
from stores.carrito import Carrito
carrito = use(Carrito)        # la misma instancia en todas las vistas y ventanas: sin provide ni props
</script>
<text>{len(carrito.items)} productos · {carrito.total:.2f} €</text>
<textfield bind:value={carrito.nota} />
<button on:click={carrito.agregar(producto)}>Añadir</button>
```

## Cuándo usar un store

| Lo que guardas | Dónde |
|---|---|
| Lo de un solo componente (un borrador, si un panel está abierto) | `state` en su `<script>` |
| Lo que comparten varias vistas o ventanas (el usuario, los documentos, el carrito) | Un **store** |
| Un objeto con estado propio del que hay varios (una cámara, una conexión) | Una clase con `state` como atributos, o un store con `key=` |
| Una preferencia suelta que se recuerda | `persisted` |

## Campos, derivados y acciones

- **Campos:** cada anotación de la clase es un campo reactivo, con su valor por defecto (copiado para cada instancia). Se leen y escriben como atributos normales, sin `.value`, en Python y en la plantilla. Lo anidado (una tarjeta dentro de una lista) es del campo que lo contiene.
- **Derivados:** `@computed` sobre un método da un valor en caché que se lee sin `.value` y no se asigna.
- **Acciones:** cada método es una acción, salvo `setup`, `teardown` y los `__dunder__`. Agrupa sus cambios en un `batch` (lo que depende de ellos se recalcula una vez) y se anota como una `Mutation`. Una acción dentro de otra del mismo store se suma a ella. En un método `async`, lo que cambia tras un `await` sigue siendo de esa acción. Lo que crea una acción (un `effect`, un `timeout`, una tarea) es del store y vive lo que él.
- **`setup(self)`** (o `setup(self, key)`) se ejecuta al crearse la instancia, y **`teardown(self)`** al liberarse. No son acciones: lo que cambian no se anota.
- Un store no define `__init__`: los valores iniciales son los de la clase, y `setup` prepara lo demás.

## Escritura controlada: `strict=True`

En un store estricto, fuera de sus métodos solo se lee: `carrito.items.append(x)` desde una vista (también `carrito.items[0]["precio"] = 9`) da un `StoreError` que dice qué hacer, y la escritura no se hace. `bind:` solo vale con los campos `field(..., bind=True)`; un `bind:` a otro campo se registra como error.

Sin `strict` (por defecto) se puede escribir desde cualquier parte; lo que no pasa por una acción se anota como «sin acción».

## Una instancia por aplicación: `use()`

- `use(Carrito)` da la instancia de la aplicación en marcha: la misma en todas las vistas y ventanas. Se crea la primera vez que se pide y se libera al cerrar la aplicación.
- `use(Documento, key=ruta)` da una por clave. Si se pide en el script de un componente, se libera (con su `teardown`) cuando se desmonta el último componente que la pidió.
- En las pruebas con `janelkit.inspect.mount`, cada montaje empieza con instancias nuevas: una prueba no ve los datos de la anterior.
- `Carrito()` crea una instancia suelta, sin aplicación: así se prueba un store sin Qt. `Carrito(items=[...])` le da valores iniciales.
- Un store puede usar otro: `use(Sesion)` dentro de un método o de `setup`.

## Seguir los cambios

```python
from janelkit_store import subscribe, snapshot, reset

cancelar = subscribe(carrito, lambda m: print(m))   # Carrito.agregar: items
snapshot(carrito)    # {"items": [...], "nota": ""}: copia de los campos públicos
reset(carrito)       # vuelve a los valores por defecto (una acción «reset»)
```

- Cada acción que cambia algo produce una `Mutation`: `.store` (nombre de la clase), `.key`, `.action` (el método, `"bind:campo"` o `None`) y `.changes`, una `Change` por campo con `.field`, `.kind` (`"set"` si se asignó, `"mutate"` si se modificó en el sitio), `.old` y `.new`. Las copias de `.old` y `.new` solo se hacen si alguien observa (`subscribe` o `JANELKIT_STORE_LOG`); si no, son `None`.
- Con `JANELKIT_STORE_LOG=1`, cada `Mutation` se registra en el logger `janelkit_store`.

## Persistencia

- `@store(persist="carrito")` guarda los campos públicos en `<carpeta de datos>/carrito.json` y los lee al crearse la instancia. `field(..., persist=False)` deja un campo fuera.
- `persisted(clave, valor_inicial)` es un `state` suelto que se recuerda: `tema = persisted("tema", "claro")`. Se usa igual que un `state` (`.value`, `bind:`); la misma clave da el mismo objeto. `.flush()` escribe ya lo pendiente.
- Los cambios se escriben agrupados (como mucho cada 300 ms) y al cerrar la aplicación, de forma atómica. Solo valores JSON: textos, números, booleanos, `None`, listas y diccionarios con claves de texto.
- La carpeta de datos es la de la sesión: `JANELKIT_DATA_DIR`, la temporal de `janelkit.inspect.mount`, o la carpeta de datos del usuario más el nombre del proyecto (`%APPDATA%\gestor` en Windows, `~/Library/Application Support/gestor` en macOS, `~/.config/gestor` en Linux). Para probar que algo se recuerda entre dos montajes, fija `JANELKIT_DATA_DIR`.
- Es para datos pequeños y medianos: cada cambio reescribe el archivo entero.

## En pruebas

```python
from janelkit.inspect import mount
from stores.carrito import Carrito

def test_anadir():
    with mount("src/App.janel") as app:
        app.find("button", text="Añadir").click()
        assert len(app.store(Carrito).items) == 1
        assert [m.action for m in app.mutations()] == ["agregar"]
```

Al importarse, el paquete añade a `janelkit.inspect` `app.store(Clase, key=None)` (la instancia de la aplicación montada) y `app.mutations()` (sus mutaciones, de la más antigua a la más reciente).

## Referencia

| Nombre | Descripción |
|---|---|
| `store` | Decorador de clase: `@store`, `@store(strict=True, persist="clave")`. |
| `field` | `field(defecto, bind=False, persist=True)`: un campo con opciones. |
| `use` | `use(Clase, key=None)`: la instancia de la aplicación (ver arriba). Sin aplicación en marcha, `StoreError`. |
| `subscribe` | `subscribe(instancia, fn) -> cancelar`: `fn(mutation)` tras cada acción que cambie algo. |
| `snapshot` | `snapshot(instancia) -> dict`: copia de los campos públicos. |
| `reset` | `reset(instancia)`: los campos vuelven a su valor por defecto. |
| `mutations` | `mutations()`: las mutaciones de la aplicación en marcha. |
| `Mutation`, `Change` | Lo que reciben los suscriptores (ver arriba). |
| `StoreError` | Escribir fuera de una acción en un store estricto, `use()` sin aplicación, una clase mal declarada. |
| `persisted`, `Persisted` | Un `state` suelto que se recuerda entre sesiones (ver arriba). |

Ejemplos: [`apps/examples/carrito`](https://github.com/janelkit/janelkit/tree/main/apps/examples/carrito) (dos ventanas con el mismo store, modo estricto y registro de cambios) y [`apps/examples/preferencias`](https://github.com/janelkit/janelkit/tree/main/apps/examples/preferencias) (`persisted`).

## Cómo está hecho

Solo usa la API pública del núcleo: `janelkit.ext.session()` (una instancia por aplicación y su carpeta de datos), `on_write` y `own` (de qué campo es cada escritura, y el modo estricto), `Scope` (lo que crea un store es suyo), `@computed` en métodos y `bind:` a través de descriptores (`__jk_bind__`).

## Compatibilidad

| janelkit-store | janelkit | Python |
|---|---|---|
| 0.1.x | ≥ 0.2, < 0.3 | ≥ 3.10 |

Sigue la misma [política de versiones](https://github.com/janelkit/janelkit/blob/main/docs/api.md#paquetes-del-ecosistema) que el núcleo, con versión propia.

## Cambios

### 0.1.0

- Primera versión: `store`, `field`, `use`, `subscribe`, `snapshot`, `reset`, `mutations`. `persisted` venía del núcleo: cambia `from janelkit import persisted` por `from janelkit_store import persisted` (`janel migrate` lo hace).

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).
