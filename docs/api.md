# API pública

Esta página define **qué es público** en FluxUI. Lo público solo cambia siguiendo la [política de versiones](#política-de-versiones); todo lo demás es interno y puede cambiar sin aviso.

Lo público es:

1. Los nombres que se importan desde `fluxui` (listados abajo).
2. Los nombres listados de `fluxui.compiler`, `fluxui.diagnostics` y `fluxui.inspect`, pensados para herramientas y pruebas.
3. El formato `.flux`: secciones, sintaxis de plantilla, elementos con sus props y eventos, la importación de componentes `.flux` y de elementos `.qml`, y el CSS soportado ([lenguaje.md](lenguaje.md), [estilos.md](estilos.md)).
4. Los comandos `flux` y sus opciones ([desarrollo.md](desarrollo.md)).
5. Las variables de entorno `FLUXUI_DEV`, `FLUXUI_EXIT_AFTER_MS` y `QT_QUICK_CONTROLS_STYLE`.
6. En los archivos `.qml` propios: el objeto `fxtheme`, con los tokens del tema activo (`fxtheme.primary`, `fxtheme.radius`…).

**No es de FluxUI**: el contenido de los archivos `.qml` propios es interfaz de Qt; el compilador solo lee sus `property` y `signal`.

**Es interno**: cualquier otro módulo (`fluxui.runtime`, `fluxui.qt_backend`, `fluxui.reactivity.*`, los submódulos de `fluxui.compiler`…), el QML generado y el módulo QML `Flux`. Que algo se pueda importar no lo hace público.

## `fluxui`

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
| `computed` | Decorador de valores derivados, perezosos y en caché. |
| `Computed` | Tipo de `computed`. `.value`, `.peek()`. |
| `effect` | `effect(fn)` ejecuta `fn` ahora y cada vez que cambie lo que leyó. Dentro de un componente se libera al desmontarlo. |
| `Effect` | Tipo de `effect`. `.dispose()`. |
| `batch` | `with batch():` agrupa cambios; los efectos se ejecutan una vez al final. |
| `untracked` | `with untracked():` lee estado sin registrar dependencias. |

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
| `provide` | `provide(clave, valor)` pone un valor a disposición de los descendientes. |
| `inject` | `inject(clave, defecto)` lee el valor del antecesor más cercano que lo provee. Sin defecto y sin proveedor: `LookupError`. |
| `ref` | `ref()` crea una referencia para `ref={nombre}` en la plantilla. |
| `Ref` | Tipo de `ref`: `.value` (reactivo; el objeto Qt o `None`), `.exists`, `.focus()`, `.blur()`, `.select_all()`; en una `<List>`, `.scroll_to_start()`, `.scroll_to_end()`, `.scroll_to(índice)`. |

### Trabajo asíncrono

Las corrutinas corren en el hilo de la interfaz, sobre el bucle de Qt (con `qasync`). Lo lanzado desde un componente se cancela al desmontarlo.

| Nombre | Descripción |
|---|---|
| `spawn` | `spawn(corrutina, on_error=None)` la lanza sin esperarla. Devuelve una `asyncio.Task`. |
| `background` | `await background(fn, *args, **kwargs)` ejecuta `fn` en otro hilo y devuelve su resultado. `fn` no debe tocar estado ni interfaz. |
| `task` | Decorador: `@task async def cargar(...)` crea una `Task`. |
| `Task` | Operación con estado reactivo: `.loading`, `.error`, `.value`, `.run(*args)` (cancela la anterior), `.cancel()`. |

Un manejador `async def` (o en línea que devuelva una corrutina, como `on:click={guardar()}`) se lanza con `spawn` automáticamente.

### Ventanas

| Nombre | Descripción |
|---|---|
| `open_window` | `open_window(Componente, modal=False, theme=None, **props_y_on_eventos)` abre un componente importado en otra ventana. Devuelve una ventana con `.is_open` (reactivo), `.close()`, `.focus()` e `.instance`. |

### Navegación

| Nombre | Descripción |
|---|---|
| `pages` | `nav = pages(Inicio, **props)` en el script crea una pila de páginas; `<Pages stack={nav} />` muestra la de arriba. |
| `PageStack` | Tipo de `pages`: `.push(C, **props_y_on_eventos)`, `.pop()`, `.replace(...)`, `.reset(...)`; reactivos `.current`, `.depth`, `.can_go_back`; `.page` (instancia visible). |

### Diálogos

| Nombre | Descripción |
|---|---|
| `dialogs` | Módulo de diálogos del sistema, todos asíncronos (`await`): `open_file`, `open_files`, `save_file`, `choose_folder` (devuelven `Path`, lista o `None` si se cancela), `message` y `confirm` (devuelve `bool`). `pending()` lista los abiertos (para pruebas). |

### Notificaciones

| Nombre | Descripción |
|---|---|
| `notify` | `notify(título, mensaje="", on_click=None)` muestra una notificación del sistema (con el icono de la aplicación en la bandeja). Pulsarla trae la ventana al frente y llama a `on_click`. Donde no hay bandeja no se ve, pero queda registrada (`MountedApp.notifications()`). |

### Idiomas

| Nombre | Descripción |
|---|---|
| `t` | `t(clave, **parámetros)` traduce al idioma activo. Reactivo. |
| `i18n` | Idioma y catálogos: `.load(carpeta)`, `.add(idioma, dict)`, `.set(idioma)`, `.language`, `.languages`, `.rtl`, `.default`; formatos `.number()`, `.currency()`, `.date()`. |

### Estilos

| Nombre | Descripción |
|---|---|
| `theme` | Tema activo: `.name`, `.names`, `.tokens`, `.set()`, `.toggle()`, `.define()`, `.extend()`, `.reset()`. Reactivo. |

## `fluxui.compiler` (herramientas)

| Nombre | Descripción |
|---|---|
| `compile_file` | `compile_file(path, roots=None, as_window=True) -> CompiledComponent`. Lanza `FluxError` si hay errores. |
| `compile_source` | `compile_source(source, file="<memoria>", roots=None) -> CompiledComponent`. |
| `check_file` | `check_file(path, roots=None, as_window=True) -> list[Diagnostic]`. Errores y advertencias sin lanzar excepciones ni ejecutar el script. Para editores. |
| `check_source` | Igual que `check_file`, desde texto. |
| `CompiledComponent` | Resultado de compilar: `.qml`, `.file`, `.files`, `.warnings`, `.all_warnings`. El resto de atributos es interno. |
| `FORMAT_VERSION` | Versión del formato `.flux` que entiende el compilador (entero). |

## `fluxui.diagnostics`

| Nombre | Descripción |
|---|---|
| `FluxError` | Excepción con uno o más diagnósticos: `.diagnostics`, `.first`. |
| `Diagnostic` | `.message`, `.location`, `.hint`, `.severity` (`"error"` o `"warning"`), `.format()`. |
| `SourceLocation` | `.file`, `.line`, `.column` (desde 1). |

## `fluxui.inspect` (pruebas y herramientas)

| Nombre | Descripción |
|---|---|
| `mount` | `with mount("src/App.flux", headless=True) as app:` monta la aplicación sin ventana visible y la desmonta al salir. |
| `MountedApp` | `app.find(tag, text=, id=, placeholder=, label=)`, `app.find_all(...)`, `app.texts()`, `app.get(nombre)`, `app.namespace`, `app.wait(segundos, until=)`, `app.process()`, `app.dialogs()`, `app.answer_dialog(resultado)`, `app.notifications()`. |
| `Element` | `.tag`, `.id`, `.text`, `.label`, `.value`, `.visible`, `.enabled`, `.prop(nombre)`; acciones `.click()`, `.type(texto)`, `.submit()`, `.check(bool)`, `.slide(valor)`, `.choose(opción)`, `.focus()`. `.item` es el objeto Qt (no cubierto por la política de versiones). |
| `InspectError` | Elemento no encontrado, ambiguo, desactivado o que no admite la acción. Es un `AssertionError`. |

## Política de versiones

Mientras FluxUI esté en la serie **0.x**:

- **Versión de parche** (0.1.0 → 0.1.1): nunca rompe lo público.
- **Versión menor** (0.1 → 0.2): puede romper lo público, pero cada cambio se anuncia en las notas de la versión con cómo migrar. Cuando sea viable, lo antiguo sigue funcionando una versión menor más con un aviso (`DeprecationWarning` o advertencia del compilador).
- **Formato `.flux`**: `FORMAT_VERSION` sube solo cuando un archivo que compilaba deja de compilar o cambia de significado. Añadir sintaxis nueva no lo cambia. Las herramientas (editores, linters) pueden usarlo para saber qué esperar.
- Desde la **1.0**, se aplica versionado semántico estricto.

Las pruebas de `tests/test_public_api.py` fallan si cambia la lista de nombres públicos sin actualizar esta página.
