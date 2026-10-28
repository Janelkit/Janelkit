# API pública

Esta página define **qué es público** en JanelKit. Lo público solo cambia siguiendo la [política de versiones](#política-de-versiones); todo lo demás es interno y puede cambiar sin aviso.

Lo público es:

1. Los nombres que se importan desde `janelkit` (listados abajo).
2. Los nombres listados de `janelkit.compiler`, `janelkit.diagnostics` y `janelkit.inspect`, pensados para herramientas y pruebas, y los de `janelkit.ext`, para paquetes que extienden JanelKit.
3. El formato `.janel`: secciones, sintaxis de plantilla, elementos con sus props y eventos, la importación de componentes `.janel` y de elementos `.qml`, y el CSS soportado ([lenguaje.md](lenguaje.md), [estilos.md](estilos.md)).
4. Los comandos `janel` y sus opciones ([desarrollo.md](desarrollo.md)), y el grupo de entry points `janelkit.commands` para añadir subcomandos ([abajo](#janelkitext-extensiones)).
5. Las variables de entorno `JANELKIT_DEV`, `JANELKIT_EXIT_AFTER_MS`, `JANELKIT_DATA_DIR` y `QT_QUICK_CONTROLS_STYLE`.
6. En los archivos `.qml` propios: el objeto `jktheme`, con los tokens del tema activo (`jktheme.primary`, `jktheme.radius`…).

**No es de JanelKit**: el contenido de los archivos `.qml` propios es interfaz de Qt; el compilador solo lee sus `property` y `signal`.

**Es interno**: cualquier otro módulo (`janelkit.runtime`, `janelkit.qt_backend`, `janelkit.reactivity.*`, los submódulos de `janelkit.compiler`…), el QML generado y el módulo QML `Janel`. Que algo se pueda importar no lo hace público.

## `janelkit`

### Aplicación

| Nombre | Descripción |
|---|---|
| `run` | `run(entry, argv=None) -> int`. Compila el componente raíz, abre la ventana y ejecuta el bucle de Qt. Devuelve el código de salida. |
| `__version__` | Versión del paquete. |

### Reactividad

| Nombre | Descripción |
|---|---|
| `state` | `state(valor)` crea un `State`. Las listas, diccionarios y conjuntos se vuelven reactivos: modificarlos en el sitio notifica. |
| `State` | Tipo de `state`. `.value`, `.set()`, `.update(fn)`, `.peek()`, `.notify()`. |
| `computed` | Decorador de valores derivados, perezosos y en caché. Si al recalcularse da el mismo valor (números, texto, tuplas… no objetos mutables), lo que depende solo de él no se vuelve a ejecutar. |
| `Computed` | Tipo de `computed`. `.value`, `.peek()`. |
| `effect` | `effect(fn)` ejecuta `fn` ahora y cada vez que cambie lo que leyó. Dentro de un componente se libera al desmontarlo. |
| `Effect` | Tipo de `effect`. `.dispose()`. |
| `batch` | `with batch():` agrupa cambios; los efectos se ejecutan una vez al final. |
| `untracked` | `with untracked():` lee estado sin registrar dependencias. |
| `persisted` | `persisted(clave, valor_inicial)` crea un `Persisted`: un `state` que se recuerda entre sesiones. Lee el valor guardado al crearse y guarda cada cambio (también en el sitio) en `<carpeta de datos>/<clave>.json`, agrupado y al cerrar. La misma clave devuelve el mismo objeto. Solo valores JSON. Ver [lenguaje.md](lenguaje.md#estado-que-se-recuerda-persisted). |
| `Persisted` | Tipo de `persisted`: lo de `State` más `.key`, `.file` y `.flush()` (escribe ya lo pendiente). |
| `History` | Deshacer y rehacer: `historial = History(limit=100)`. `with historial.step("mover tarjeta"):` anota como un paso lo que cambie dentro (cada `State` asignado y cada lista, diccionario o conjunto reactivo modificado); `historial.add(nombre, undo=, redo=)` anota algo que ya se hizo y el historial no ve. `undo()` y `redo()` devuelven el nombre del paso (o `None`); `clear()`, `mark_saved()`. Reactivos: `can_undo`, `can_redo`, `undo_label`, `redo_label`, `modified`. Ver [lenguaje.md](lenguaje.md#deshacer-y-rehacer-history). |

### Componentes

| Nombre | Descripción |
|---|---|
| `prop` | `nombre = prop(defecto)` en el script de un componente declara una prop (sin defecto: obligatoria). |
| `Prop` | Tipo de las props: `.value` de solo lectura, `.peek()`. |
| `PropError` | Error al intentar escribir una prop. |
| `event` | `nombre = event()` declara un evento que el padre escucha con `on:nombre`. |
| `Event` | Tipo de los eventos: `.emit(*args, **kwargs)`, `.connected`. |

### Ciclo de vida, contexto y referencias

Se llaman mientras se ejecuta el `<script>` de un componente; fuera de él lanzan `RuntimeError`.

| Nombre | Descripción |
|---|---|
| `on_mount` | `on_mount(fn)` (o como decorador) ejecuta `fn` cuando la vista del componente existe. Si `fn` devuelve una función, se llama al desmontar. |
| `on_destroy` | `on_destroy(fn)` ejecuta `fn` al desmontar el componente. |
| `before_leave` | `before_leave(fn)` (o como decorador): `fn()` se consulta antes de descartar la página que lo contiene o de cerrar su ventana con la X; si devuelve `False`, no se sale. Puede ser `async`. |
| `provide` | `provide(clave, valor)` pone un valor a disposición de los descendientes. |
| `inject` | `inject(clave, defecto)` lee el valor del antecesor más cercano que lo provee. Sin defecto y sin proveedor: `LookupError`. |
| `ref` | `ref()` crea una referencia para `ref={nombre}` en la plantilla. |
| `Ref` | Tipo de `ref`: `.value` (reactivo; el objeto Qt o `None`), `.exists`, `.focused` (¿tiene el foco él o algo de dentro?; no reactivo), `.focus()`, `.blur()`, `.select_all()`; en una `<List>`, `.scroll_to_start()`, `.scroll_to_end()`, `.scroll_to(índice)`. |
| `PointerEvent` | Lo que recibe `on:click`, `on:dblclick`, `on:contextmenu` y `on:pointer*` de las cajas: `.x`, `.y` (respecto al elemento), `.window_x`, `.window_y`, `.button`, `.buttons`, `.pointer` (`"mouse"`, `"touch"`, `"pen"`, `"keyboard"`), `.clicks`, `.ctrl`, `.shift`, `.alt`, `.meta`. Como todos los eventos: `.prevent()`, `.stop()`, `.type`. |
| `DragEvent` | `on:dragstart`, `on:dragover`, `on:drop`, `on:dragend` de un `<flex draggable>`: lo de `PointerEvent` más `.data` (lo que se arrastra: lo pone `on:dragstart` y llega igual al resto) y `.dropped` (en `on:dragend`: si algún `on:drop` lo recibió). |
| `KeyEvent` | `on:keydown`, `on:keyup`: `.key` (como en la web: `"a"`, `"Enter"`, `"ArrowUp"`…), `.code`, `.text`, `.repeat` y los modificadores. |
| `WheelEvent` | `on:wheel`: `.dx`, `.dy` (px; positivo hacia abajo), `.x`, `.y` y los modificadores. |
| `FocusEvent` | `on:focus`, `on:blur`: `.reason` (`"tab"`, `"click"`, `"code"`). |
| `ResizeEvent` | `on:resize`: `.width`, `.height` (también `event["width"]`). |

### Trabajo asíncrono

Las corrutinas corren en el hilo de la interfaz, sobre el bucle de Qt (con `qasync`). Lo lanzado desde un componente se cancela al desmontarlo.

| Nombre | Descripción |
|---|---|
| `spawn` | `spawn(corrutina, on_error=None)` la lanza sin esperarla. Devuelve una `asyncio.Task`. |
| `background` | `await background(fn, *args, **kwargs)` ejecuta `fn` en otro hilo y devuelve su resultado. `fn` no debe tocar estado ni interfaz. |
| `task` | Decorador: `@task async def cargar(...)` crea una `Task`. |
| `Task` | Operación con estado reactivo: `.loading`, `.error`, `.value`, `.run(*args)` (cancela la anterior), `.cancel()`. |

Un manejador `async def` (o en línea que devuelva una corrutina, como `on:click={guardar()}`) se lanza con `spawn` automáticamente.

### Temporizadores

Creados en el script de un componente (o en algo que se ejecuta dentro de él), se detienen al desmontarlo. Cada ejecución agrupa sus cambios (`batch`); si la función es `async def`, se lanza con `spawn` y los tics siguientes se saltan mientras no termine.

| Nombre | Descripción |
|---|---|
| `interval` | `interval(ms, fn)` llama a `fn` cada `ms` milisegundos. También como decorador: `@interval(250)`. Devuelve un `Timer`. |
| `timeout` | `timeout(ms, fn)` llama a `fn` una vez, pasados `ms` milisegundos. También como decorador. Devuelve un `Timer`. |
| `Timer` | Tipo de `interval` y `timeout`: `.active` (reactivo), `.ms` (se aplica al volver a arrancar), `.start()`, `.restart()` (vuelve a contar desde cero), `.stop()`; llamarlo (`muestrear()`) ejecuta la función ahora. Un error en la función se registra en el logger `janelkit` y el temporizador sigue. |

### Ventanas

| Nombre | Descripción |
|---|---|
| `open_window` | `open_window(Componente, modal=False, theme=None, **props_y_on_eventos)` abre un componente importado en otra ventana. Devuelve una ventana con `.is_open` (reactivo), `.close()`, `.focus()` e `.instance`. |

### Navegación

| Nombre | Descripción |
|---|---|
| `pages` | `nav = pages(Inicio, **props)` en el script crea una pila de páginas; `<Pages stack={nav} />` muestra la de arriba. |
| `PageStack` | Tipo de `pages`: `.push(C, **props_y_on_eventos)` (se puede esperar: `await` devuelve el valor de `.back(valor)`), `.pop()`, `.back(valor=None)`, `.replace(...)`, `.reset(...)` (los cuatro se pueden esperar: `True` si se salió, `False` si un `before_leave` lo impidió); reactivos `.current`, `.depth`, `.can_go_back`; `.page` (instancia visible). |
| `navigation` | `nav = navigation()` en el script de una página (o de un componente dentro de ella) da su pila. |
| `sections` | `secciones = sections(a=A, b=B)` crea secciones paralelas, cada una con su pila; `<Sections of={secciones} />` muestra la actual. |
| `Sections` | Tipo de `sections`: `.show(nombre)`, `[nombre]` (su pila), `.stack` (la de la visible), `.names`; reactivo `.current`. |

### Idioma de la interfaz

| Nombre | Descripción |
|---|---|
| `locale` | Idioma de la interfaz: `.language`, `.set(idioma)`, `.reset()`, `.rtl` (¿se escribe de derecha a izquierda? Entonces toda la interfaz se refleja). Reactivo; también fija el `QLocale` por defecto de Qt. `janelkit_i18n.i18n.set()` lo cambia. |

Las traducciones (`t`, `i18n`) están en [`janelkit-i18n`](../packages/janelkit-i18n/README.md), y los diálogos, el portapapeles y las notificaciones (`dialogs`, `clipboard`, `notify`), en [`janelkit-desktop`](../packages/janelkit-desktop/README.md).

### Estilos

| Nombre | Descripción |
|---|---|
| `theme` | Tema activo: `.name`, `.names`, `.tokens`, `.set()`, `.toggle()`, `.define()`, `.extend()`, `.reset()`. Reactivo. |

## `janelkit.compiler` (herramientas)

| Nombre | Descripción |
|---|---|
| `compile_file` | `compile_file(path, roots=None, as_window=True) -> CompiledComponent`. Lanza `JanelError` si hay errores. |
| `compile_source` | `compile_source(source, file="<memoria>", roots=None) -> CompiledComponent`. |
| `check_file` | `check_file(path, roots=None, as_window=True) -> list[Diagnostic]`. Errores y advertencias sin lanzar excepciones ni ejecutar el script. Para editores. |
| `check_source` | Igual que `check_file`, desde texto. |
| `CompiledComponent` | Resultado de compilar: `.qml`, `.file`, `.files`, `.warnings`, `.all_warnings`. El resto de atributos es interno. |
| `FORMAT_VERSION` | Versión del formato `.janel` que entiende el compilador (entero). |

## `janelkit.diagnostics`

| Nombre | Descripción |
|---|---|
| `JanelError` | Excepción con uno o más diagnósticos: `.diagnostics`, `.first`. |
| `Diagnostic` | `.message`, `.location`, `.hint`, `.severity` (`"error"` o `"warning"`), `.format()`. |
| `SourceLocation` | `.file`, `.line`, `.column` (desde 1). |

## `janelkit.inspect` (pruebas y herramientas)

| Nombre | Descripción |
|---|---|
| `mount` | `with mount("src/App.janel", headless=True) as app:` monta la aplicación sin ventana visible y la desmonta al salir. |
| `MountedApp` | `app.find(tag, text=, id=, placeholder=, label=)`, `app.find_all(...)`, `app.texts()`, `app.get(nombre)`, `app.namespace`, `app.wait(segundos, until=)`, `app.process()`, `app.key("Ctrl+Z")` (pulsa una combinación sobre lo que tenga el foco: atajos), `app.windows()` (las ventanas abiertas con `open_window`, cada una inspeccionable igual). Las extensiones añaden más con [`janelkit.ext.inspector`](#janelkitext-extensiones): `janelkit-desktop` añade `app.dialogs()`, `app.answer_dialog(resultado)` y `app.notifications()`. |
| `Element` | `.tag`, `.id`, `.text`, `.label`, `.value`, `.visible`, `.enabled`, `.prop(nombre)`; acciones `.click()`, `.type(texto)`, `.submit()`, `.check(bool)`, `.slide(valor)`, `.choose(opción)`, `.focus()`, `.hover()`/`.unhover()` (puntero encima: estilos `:hover`), `.press()`/`.release()` (botón del ratón: `:pressed`; soltar encima es un clic real). `.double_click()`, `.right_click()` (`on:dblclick`, `on:contextmenu`), `.key("Ctrl+D")` (le da el foco y pulsa la combinación). `.drag_to(destino, x=, y=, cancel=False)` arrastra un `<flex draggable>` y lo suelta sobre `destino` (o pulsa Escape con `cancel=True`). `.item` es el objeto Qt (no cubierto por la política de versiones). |
| `InspectError` | Elemento no encontrado, ambiguo, desactivado o que no admite la acción. Es un `AssertionError`. |

## `janelkit.ext` (extensiones)

Para paquetes que amplían JanelKit sin tocar el núcleo (`janelkit-i18n`, `janelkit-desktop`…). Una extensión usa solo la API pública: los nombres de `janelkit` y los de estos módulos. `tests/test_boundaries.py`, en la raíz del repositorio, comprueba que las de este repositorio lo cumplen y que el núcleo no las importa.

| Nombre | Descripción |
|---|---|
| `app` | `app()` devuelve la aplicación en marcha, o `None`. Son públicos `.engine` (el `QQmlEngine`), `.qt_app` (la `QGuiApplication`) y `.main_window()` (la ventana de la vista montada más reciente, o `None`). |
| `inspector` | Decorador: `@inspector("nombre")` sobre `fn(app, *args)` añade el método `MountedApp.nombre` de `janelkit.inspect`. Así `janelkit_desktop.dialogs` aporta `dialogs()` y `answer_dialog()`, y `janelkit_desktop.notifications` aporta `notifications()`. |

**Subcomandos de `janel`:** un paquete los declara como entry points del grupo `janelkit.commands`. El nombre del entry point es el del comando y apunta a `configurar(parser)`, que recibe el `ArgumentParser` del subcomando, le añade sus argumentos y fija `parser.set_defaults(func=ejecutar)`. `ejecutar(args)` devuelve el código de salida, y la primera línea de la documentación de `configurar` es la ayuda.

```toml
[project.entry-points."janelkit.commands"]
package = "janelkit_package.cli:configure"
```

Un plugin que falla al cargarse, o que intenta redefinir un comando de JanelKit, se ignora con un aviso.

## Política de versiones

Mientras JanelKit esté en la serie **0.x**:

- **Versión de parche** (0.1.0 → 0.1.1): nunca rompe lo público.
- **Versión menor** (0.1 → 0.2): puede romper lo público, pero cada cambio se anuncia en las notas de la versión con cómo migrar. Cuando sea viable, lo antiguo sigue funcionando una versión menor más con un aviso (`DeprecationWarning` o advertencia del compilador).
- **Formato `.janel`**: `FORMAT_VERSION` sube solo cuando un archivo que compilaba deja de compilar o cambia de significado. Añadir sintaxis nueva no lo cambia. Las herramientas (editores, linters) pueden usarlo para saber qué esperar.
- Desde la **1.0**, se aplica versionado semántico estricto.

### Paquetes del ecosistema

`janelkit-i18n` y `janelkit-desktop` tienen **versión propia** y siguen la misma política para su propia API. Cada uno declara en su `pyproject.toml` las versiones del núcleo con las que funciona (por ejemplo `janelkit>=0.1,<0.2`) y solo usa la API pública del núcleo, así que una versión de parche del núcleo no los rompe. Cuando el núcleo publica una versión menor, se prueban contra ella y se amplía el rango (con una versión de parche de la extensión) o se adaptan (con una versión menor). En el repositorio, la CI prueba cada extensión contra el núcleo de la misma rama, y `tests/test_packages.py` comprueba que el rango declarado incluye esa versión.

Las pruebas de `packages/janelkit/tests/test_public_api.py` fallan si cambia la lista de nombres públicos sin actualizar esta página.
