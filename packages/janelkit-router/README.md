# janelkit-router

[![PyPI](https://img.shields.io/pypi/v/janelkit-router)](https://pypi.org/project/janelkit-router/)
[![Python](https://img.shields.io/pypi/pyversions/janelkit-router)](https://pypi.org/project/janelkit-router/)
[![CI](https://github.com/janelkit/janelkit/actions/workflows/ci.yml/badge.svg)](https://github.com/janelkit/janelkit/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](https://github.com/janelkit/janelkit/blob/main/LICENSE)

**Navegación entre pantallas para aplicaciones [JanelKit](https://pypi.org/project/janelkit/):** pilas de páginas que conservan su estado, secciones paralelas (barra lateral, pestañas), resultados con `await`, preguntar antes de salir y transiciones.

```bash
pip install janelkit-router
```

## En un minuto

```python
from janelkit_router import pages, Pages
from pages.Inicio import Inicio
from pages.Detalle import Detalle

nav = pages(Inicio)

def abrir(item):
    nav.push(Detalle, item=item, on_borrado=borrar)
```

```html
<row class="barra">
  <button on:click={nav.pop()} enabled={nav.can_go_back}>← Volver</button>
  <text>{nav.current}</text>
</row>
<Pages stack={nav} />
```

`Pages` y `Sections` son elementos de este paquete: se importan en el script, como un componente, y se usan con mayúscula.

## Pilas de páginas

- `<Pages stack={nav} />` muestra la página de arriba de la pila y ocupa el espacio libre (`flex: 1`).
- `push` muestra una página nueva encima; la de debajo **sigue viva** y, al volver con `pop()`, conserva su estado. Mientras está debajo, lo que muestra espera, como en `{#hidden}`: se pone al día al volver a verse. `replace` sustituye la actual; `reset` vacía la pila y empieza de nuevo. Las páginas descartadas se liberan (sus `on_destroy` se ejecutan).
- Cada página ocupa todo su `<Pages>` (y cada sección, su `<Sections>`) y se estrecha con la ventana hasta el mínimo de su contenido; lo que deba desplazarse, con `overflow: auto`. La raíz de la página puede cambiarlo con CSS, como un bloque en una columna:

  ```css
  .pagina { max-width: 720px; margin: 0 auto; }   /* una columna centrada */
  .pagina { width: 400px; height: 300px; }         /* tamaño fijo, arriba a la izquierda */
  .pagina { align-self: center; }                  /* su ancho natural, centrada */
  .pagina { margin: 24px; }                        /* llena, con margen alrededor */
  ```
- Las palabras clave son props y eventos (`on_...`) de la página, como en `open_window`. Las páginas heredan el contexto (`inject`) del componente que declara la pila.
- `nav.current` (nombre de la página visible), `nav.depth` y `nav.can_go_back` son reactivos; `nav.page` da la instancia visible.
- **Transiciones:** `<Pages stack={nav} transition:slide />` anima la página que entra: al avanzar llega desde la derecha y al volver desde la izquierda. También `fade` y `scale`, y la duración: `transition:fade={150}`. En `<Sections>`, la transición se aplica al cambiar de sección y a las páginas de cada una.
- **Atrás con el teclado y el ratón:** Alt+← y el botón «atrás» del ratón vuelven a la página anterior, en la pila visible más interna. Alt+← actúa cuando el foco está dentro de la pila (si está, por ejemplo, en un botón de la barra lateral, no hace nada); el ratón, al pulsar sobre ella. Si un elemento de la página ya usa Alt+← (por ejemplo, para mover una tarjeta), gana el elemento.

### Navegar desde una página

Dentro de una página (o de cualquier componente que contenga), `navigation()` da su pila, sin pasarla como prop:

```python
from janelkit_router import navigation
from pages.Detalle import Detalle

nav = navigation()

def abrir(item):
    nav.push(Detalle, item=item)
```

### Devolver un resultado

`push` se puede esperar: `await` devuelve el valor con el que la página vuelve con `nav.back(valor)` (o `None` si se descarta de otra forma, con `pop`, `replace` o `reset`).

```python
async def elegir_responsable():                  # en la página que pregunta
    persona = await nav.push(ElegirPersona)
    if persona is not None:
        tarjeta["responsable"] = persona["id"]
```

```html
<!-- en ElegirPersona.janel -->
<button on:click={nav.back(p)}>{p["nombre"]}</button>
```

## Secciones

Una aplicación con barra lateral o pestañas tiene varias secciones, y cada una necesita su pila. `sections()` las crea; `<Sections of={...} />` muestra la actual:

```python
from janelkit_router import sections, Sections
from pages.Proyectos import Proyectos
from pages.Personas import Personas

secciones = sections(proyectos=Proyectos, personas=Personas)
```

```html
<flex>
  <flex direction="column" class="barra">
    <button on:click={secciones.show("proyectos")} class:activa={secciones.current == "proyectos"}>Proyectos</button>
    <button on:click={secciones.show("personas")} class:activa={secciones.current == "personas"}>Personas</button>
  </flex>
  <Sections of={secciones} />
</flex>
```

- Cada sección es una pila (`secciones["personas"]`, o `secciones.stack` para la visible) y empieza en el componente indicado. Dentro, `navigation()` da la pila de su sección.
- Una sección se crea la primera vez que se muestra. Al cambiar a otra **se conserva entera**, con todas sus páginas y su estado; volver a ella cuesta lo mismo que mostrarla. Mientras no se ve, lo que muestra espera (como en `{#hidden}`): un cambio de datos en otra sección no la recalcula.
- `secciones.current` (el nombre de la visible) es reactivo; `secciones.names` lista los nombres.

## Preguntar antes de salir

`before_leave(fn)` (del núcleo) en el script de un componente registra una pregunta: si `fn()` devuelve `False`, no se sale. Puede ser `async`, para preguntar con un diálogo:

```python
from janelkit import before_leave
from janelkit_desktop import dialogs

@before_leave
async def salir():
    return not cambios.value or await dialogs.confirm("Hay cambios sin guardar. ¿Salir igualmente?")
```

- Se consulta al descartar la página que contiene el componente (`pop`, `back`, `replace`, `reset`, Alt+←) y al cerrar con la X la ventana que lo muestra.
- Cambiar de sección no pregunta: la sección se conserva y no se pierde nada.
- Para encadenar navegaciones, espera la salida: `pop`, `back`, `replace` y `reset` devuelven `True` si se salió y `False` si un `before_leave` lo impidió (la respuesta puede llegar después de un diálogo):

  ```python
  async def ir_a_tarjeta(pid, tid):
      if await nav.reset(Proyectos):      # un detalle con cambios puede pedir quedarse
          nav.push(Proyecto, ident=pid, enfocar=tid)
  ```

## Referencia

| Nombre | Descripción |
|---|---|
| `pages` | `nav = pages(Inicio, **props)` crea una pila de páginas que empieza en `Inicio` (un componente importado). |
| `PageStack` | Tipo de `pages`: `.push(C, **props_y_on_eventos)` (se puede esperar: `await` devuelve el valor de `.back(valor)`), `.pop()`, `.back(valor=None)`, `.replace(...)`, `.reset(...)` (los cuatro se pueden esperar: `True` si se salió, `False` si un `before_leave` lo impidió); reactivos `.current`, `.depth`, `.can_go_back`; `.page` (instancia visible). |
| `navigation` | `nav = navigation()` en el script de una página (o de un componente dentro de ella) da su pila. |
| `sections` | `secciones = sections(a=A, b=B)` crea secciones paralelas, cada una con su pila. |
| `SectionSet` | Tipo de `sections`: `.show(nombre)`, `[nombre]` (su pila), `.stack` (la de la visible), `.names`; reactivo `.current`. |
| `<Pages stack={nav} />` | Muestra la página de arriba. Admite `transition:` y las propiedades comunes (`flex`, `width`, `class`…). |
| `<Sections of={secciones} />` | Muestra la sección visible. Igual que `<Pages>`. |

## En pruebas

Con `janelkit.inspect`, las páginas se buscan por el nombre de su componente (`app.find("Detalle")`) y la pila se maneja desde el script (`app.get("nav").push(...)`). La página de debajo y las secciones ocultas no salen en `find`.

Ejemplo: [`apps/challenges/gestor`](https://github.com/janelkit/janelkit/tree/main/apps/challenges/gestor) (secciones, páginas, resultados con `await` y preguntas antes de salir).

## Cómo está hecho

Solo usa la API pública del núcleo, como cualquier paquete externo: `Pages.qml` y `Sections.qml` son elementos cuya raíz es `JkDeck` y que declaran una propiedad `JkHost`; `PageStack` y `SectionSet` son anfitriones (`janelkit.ext.Host`) que montan las páginas con `Container.mount`. Ver [arquitectura.md](https://github.com/janelkit/janelkit/blob/main/docs/arquitectura.md).

## Compatibilidad

| janelkit-router | janelkit | Python |
|---|---|---|
| 0.2.x.x | 0.2.x.x | ≥ 3.10 |

Comparte la serie con el núcleo: janelkit-router 0.2.x.x va con janelkit 0.2.x.x. Los dos últimos números son suyos ([política de versiones](https://github.com/janelkit/janelkit/blob/main/docs/api.md#paquetes-del-ecosistema)).

## Cambios

### 0.2.0.0 (sin publicar)

- Primera versión, en la serie 0.2. Antes era la navegación del núcleo (`janelkit.pages`): cambia `from janelkit import pages, navigation, sections` por `from janelkit_router import pages, navigation, sections` e importa los elementos que uses (`from janelkit_router import Pages, Sections`). El tipo de `sections()` pasa a llamarse `SectionSet`. `janel migrate` hace el cambio.

## Licencia

[MIT](https://github.com/janelkit/janelkit/blob/main/LICENSE).
