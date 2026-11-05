# Arquitectura

Para quien trabaja en JanelKit o escribe una extensión: qué va en el núcleo, cómo está organizado, el recorrido de un `.janel` hasta la pantalla, cómo se versiona y cuánto cuesta. Para usar JanelKit no hace falta.

## Qué va en el núcleo

Una funcionalidad es del **núcleo** (`janelkit`) si cumple al menos una de estas condiciones:

1. Sin ella no se puede escribir, ejecutar o componer una aplicación `.janel`: lenguaje, compilador, runtime, controles básicos, CLI.
2. Necesita detalles internos que no deben ser públicos: el puente QObject, las regiones dinámicas, el IR del compilador.
3. Define una semántica que todo lo demás asume: cómo se propaga un cambio, cuándo se monta y desmonta un componente, cuándo se agrupan cambios (`batch`).

Si algo puede construirse **solo con la API pública** y no todas las aplicaciones lo necesitan, va en un paquete aparte. Por eso la reactividad (`state`, `computed`, `effect`) y el idioma de la interfaz (`janelkit.locale`, que cambia la dirección de toda la disposición) son del núcleo, y la navegación entre pantallas, los stores y `persisted`, las traducciones o los diálogos del sistema no: son paquetes que usan la API pública, como podría hacerlo cualquiera.

## Paquetes del repositorio

| Paquete | Qué es | Depende de |
|---|---|---|
| `packages/janelkit` | El núcleo: lenguaje, compilador, reactividad, runtime, controles, CLI, inspección | PySide6, qasync |
| `packages/janelkit-router` | Navegación: pilas de páginas, secciones, `<Pages>`, `<Sections>` | `janelkit`, solo su API pública |
| `packages/janelkit-store` | Stores: datos compartidos con acciones, modo estricto, seguimiento de cambios y persistencia; `persisted` | `janelkit`, solo su API pública |
| `packages/janelkit-i18n` | Traducciones: catálogos, plurales, formatos | `janelkit`, solo su API pública |
| `packages/janelkit-desktop` | Diálogos, portapapeles, notificaciones | `janelkit`, solo su API pública |
| `packages/janelkit-vscode` | Resaltado de `.janel` en VS Code | — |
| `apps/examples` | Ejemplos pequeños, uno por tema, con pruebas | `janelkit` y extensiones |
| `apps/challenges` | Aplicaciones grandes que ponen a prueba el núcleo, con pruebas | `janelkit` y extensiones |

Cada paquete tiene versión propia y se prueba por separado. Las extensiones declaran el rango del núcleo que admiten (`janelkit>=0.1,<0.3`). `tests/test_boundaries.py` comprueba que el núcleo no importa el ecosistema y que las extensiones no usan nada interno; `tests/test_packages.py`, que versiones y rangos son compatibles.

### Lo que el núcleo ofrece a las extensiones

| Punto | Qué es |
|---|---|
| API pública declarada | Lo que exporta `janelkit` y los módulos públicos ([api.md](api.md)); lo demás es interno. Lo vigila `test_public_api.py` |
| Inspección | `janelkit.inspect`: montar sin ventana, recorrer, disparar eventos, leer el estado. Las extensiones le añaden métodos con `janelkit.ext.inspector` |
| Acceso a la aplicación | `janelkit.ext.app()`: motor QML, `QApplication` y ventana principal |
| Plugins de la CLI | Subcomandos de `janel` desde otros paquetes (entry points `janelkit.commands`) |
| Compilador para herramientas | `check_source`/`check_file`: diagnósticos sin ejecutar el script. La estructura (props, eventos, nombres) no es pública |
| Elementos propios | Un `.qml` importado como componente; el compilador lee sus `property` y `signal` |
| Anfitriones | `janelkit.ext.Host`: un objeto del script monta componentes dentro de un elemento `.qml` (raíz `JkDeck`, propiedad `JkHost`) con `Container.mount`, con su compuerta de visibilidad y su contexto. Es lo que usa `janelkit-router` |
| Sesión | `janelkit.ext.session()`: lo que dura una aplicación (una por `run()` y por cada `inspect.mount()`), con su carpeta de datos y un aviso al terminar |
| Escrituras | `janelkit.ext.on_write(fn)` ve cada escritura de estado antes de que ocurra (y puede impedirla); `own(destino, dueño)` marca de quién son unos datos, y lo insertado lo hereda. Con un descriptor que define `__jk_bind__`, `bind:` escribe a través de él |
| Componentes en paquetes | Un paquete instalado reparte `.janel` y `.qml` en su carpeta; se importan por el nombre del paquete (`from janelkit_router import Pages`) |
| Versión del formato | `FORMAT_VERSION`, con política de cambios |

### Añadir un paquete

1. Crear `packages/janelkit-<nombre>/` con `pyproject.toml` (versión propia, `janelkit>=X,<Y`), `README.md` con una sección «Cambios», `src/janelkit_<nombre>/` y `tests/` con un `conftest.py` que importe las fixtures de `janelkit.testing`.
2. Usar solo la API pública del núcleo. Si falta algo, se añade antes al núcleo, con prueba y entrada en [api.md](api.md).
3. Añadirlo a `pytest.ini`, a `requirements-dev.txt`, a la matriz `extensions` de la CI y, si tiene wheel, a `EXTENSIONS` en `tools/check_wheel.py`; y crear su etiqueta de partida (`git tag janelkit-<nombre>-v0.1.0`). Actualizar la lista esperada de `tests/test_packages.py`.

## Capas del núcleo

Cada módulo de `janelkit` pertenece a una capa y solo importa de su capa o de las de abajo. Lo comprueba `tests/test_architecture.py`, que lee los imports de todos los módulos (también los que se hacen dentro de una función): un import hacia arriba o un ciclo entre áreas hace fallar la prueba. Las capas 0 y 1 no importan Qt.

| Capa | Módulos | Qué hace |
|---|---|---|
| **0** | `reactivity`, `diagnostics`, `events` | Estado reactivo (`State`, `Computed`, `Effect`, `batch`, `Scope`, `Gate`, colecciones, props, enganche de escrituras); errores con ubicación; los objetos de evento de `<flex>`. Python puro |
| **1** | `compiler` | `.janel` → AST → IR → QML, con el catálogo de elementos (`elements.py`) y el CSS (`css_parser.py`, `css.py`, `cascade.py`). Python puro |
| **2** | `runtime`, `lifecycle`, `windows`, `tasks`, `timers`, `session`, `locale`, `themes`, `displays` | Instancias de componentes, puente con QML, anfitriones (`runtime/hosts.py`), ciclo de vida, ventanas, asincronía, temporizadores, sesión de aplicación, idioma, temas, pantallas |
| **3** | `qt_backend`, `video` | Arranque de Qt y del bucle de eventos, carga del QML, eventos de `<flex>`, motor de disposición, vídeo |
| **4** | `cli`, `inspect`, `testing`, `ext`, `janelkit` (raíz) | La CLI `janel`, la inspección para pruebas, las fixtures de pytest, la API para extensiones y lo que exporta `janelkit` |

- Un módulo no se llama igual que un nombre público que exporta su paquete (`themes.py` exporta `theme`; `displays.py`, `screens`): el submódulo taparía al objeto.
- Cuando una capa necesita algo de una de arriba, se invierte la dependencia con una interfaz en la de abajo; y cuando un paquete necesita algo del núcleo, se le da una interfaz pública en vez de abrirle lo interno: `janelkit-router` monta sus páginas con `janelkit.ext.Host` y `Container.mount`, sin tocar el runtime.

## De un `.janel` a la pantalla

```
App.janel ──► sfc_parser ──► template_parser / script_analysis ──► AST
          ──► lowering (valida, resuelve estilos y bindings) ──► IR
          ──► qml_generator ──► QML  +  tablas del runtime (bindings, manejadores, regiones)
```

1. **Compilar** (capa 1). `sfc_parser` separa `<script>`, plantilla y `<style>` conservando las líneas. `template_parser` lee la plantilla (no es XML: admite expresiones Python entre llaves). `script_analysis` analiza el script sin ejecutarlo. `lowering` valida elementos, atributos y nombres contra el catálogo, resuelve la cascada de estilos (los estilos tienen ámbito y la plantilla se conoce entera) y produce el IR. `layout_choice` decide, caja por caja, quién la dispone (abajo). `qml_generator` escribe el QML y un mapa de origen (línea QML → línea del `.janel`) para los errores.
2. **Montar** (capa 2). `runtime/component.py` crea una instancia por componente: ejecuta el script en un módulo propio (registrado en `sys.modules` mientras vive), crea un puente QObject (`runtime/qt_bridge.py`) con una propiedad por binding, y un `Effect` por binding que recalcula su valor y lo escribe en el puente. Las regiones dinámicas (`{#if}`, `{#each}`, `{#key}`, `{#hidden}`) son modelos Qt (`runtime/list_model.py`) con un puente por fila.
3. **Dibujar** (capa 3). `qt_backend/application.py` arranca Qt y el bucle de asyncio (qasync) y carga el QML generado sobre los controles de `qml/Janel/`. QML no ejecuta lógica del usuario: lee propiedades del puente y le devuelve eventos. Los estados (`:hover`, `:pressed`…) se compilan a estados de la vista, así que no pasan por Python; los eventos de `<flex>` los ve un filtro por ventana (`qt_backend/events.py`) antes que Qt Quick, y los entrega de dentro afuera.

### Reactividad y ámbitos

- Lo que lee un `Effect` o un `Computed` queda registrado; al cambiar, el efecto se vuelve a ejecutar al terminar el `batch` en curso. Si solo lo avisaron `Computed`, primero se recalculan y solo se ejecuta si alguno cambió de valor.
- Cada instancia de componente tiene un `Scope`: lo que se crea mientras su script, un manejador o un tic se ejecutan (efectos, `computed`, temporizadores, tareas) queda en él y se libera al desmontar. El ámbito activo es una variable de contexto (`contextvars`), así que una corrutina lo conserva tras cada `await`.
- Una `Gate` (compuerta de visibilidad) aplaza los efectos de la plantilla de lo que no se ve (`{#hidden}`, otra sección, la página de debajo, una fila de `<list>` fuera de la vista). Lo del script sigue funcionando; `is_visible()` expone la compuerta como `computed`.
- El estado reactivo solo se modifica desde el hilo de la interfaz. `background()` ejecuta en otro hilo y devuelve el valor por `await`.

### Disposición: motor de `<flex>` y layouts de Qt

Los `Layout` de Qt Quick no tienen salto de línea, márgenes, `space-between`, `order` ni posición absoluta en el flujo, así que `<flex>` tiene un motor propio (`qml/Janel/flex.js`, un subconjunto del algoritmo de CSS):

- Cada hijo avisa a su contenedor con un binding que depende de lo que afecta a su sitio; el contenedor pasa a una cola que se vacía en la fase de *polish* de Qt Quick, justo antes de dibujar (`JkPolisher`, `qt_backend/polish.py`). Nunca se dibuja un fotograma a medio colocar, y muchos cambios seguidos cuestan una pasada.
- Se coloca de fuera adentro, y lo leído de cada hijo se guarda hasta que el hijo avisa.
- En el motor de JS de Qt, `Set`/`Map` buscan de forma lineal, `for…of` es varias veces más lento que un bucle con índice, y un binding que recorre todos los hijos se vuelve cuadrático al añadirlos uno a uno.

El motor es unas 5 veces más lento que un layout de Qt al cambiar el ancho. Por eso `compiler/layout_choice.py` elige, caja por caja:

- **Layout de Qt** (`JkColumn`, `JkRow`, `JkQtBox`) para `column`, `row` y `<flex direction="column">` que solo usan dirección, `gap`, `padding`, bordes, `align-items`/`align-self` (sin `baseline`), márgenes fijos, tamaños en px, mínimos y máximos, y un solo hijo con `flex`.
- **Motor** (`JkFlex`, `JkFlexColumn`, `JkFlexRow`) en todo lo demás: `wrap`, `justify-content`, `overflow: auto`, `order`, `margin: auto`, `%`, `position`, `flex-shrink`/`flex-basis`, `:first-child`/`:last-child`, varios hijos con `flex`, contenido de un `<slot />`, cajas implícitas de `{#if}`/`{#each}`, cajas exteriores de componentes y `<flex>` en fila. También dentro de una caja con el motor (el motor lee al momento el tamaño de cada hijo; un layout de Qt lo calcula más tarde). Si aun así queda un layout dentro del motor, `flex.js` lo coloca al momento con `ensurePolished()`.

Se decide al compilar con todo lo que la caja y sus hijos pueden llegar a tener, también en estados y clases condicionales. Las dos vías comparten `JkBox.qml` (aspecto, estados, eventos, accesibilidad) y colocan igual: lo comprueba `packages/janelkit/tests/test_layout_choice.py`, que monta las mismas páginas de las dos formas.

Cada pieza de una caja o de un `<text>` se crea solo si se usa (`jk.js`, `flexDecorations` y `textDecorations`; prueba: `test_flex_lazy.py`):

| Pieza | Se crea si… |
|---|---|
| `JkHover.qml` | `on:click`, una regla `:hover`, `cursor` o `title` |
| `JkTap.qml` | `on:click` o una regla `:pressed` |
| `JkRole.qml` (lector de pantalla, Espacio/Intro) | un papel distinto de `box` |
| `JkTranslate.qml` | `transform: translate(...)` distinto de cero |
| `JkTextBox.qml` | `background` o `border` en un `<text>` |
| `JkTextLinks.qml` | `format="markdown"` o `"html"` |

## Versiones y publicación

La versión no se escribe a mano: la calcula `.github/workflows/version.yml` (con `tools/versioning.py`) cuando la CI pasa en `main`, a partir del **prefijo** de cada commit. El prefijo dice qué nota quien usa JanelKit, no cuánto costó el cambio:

| Prefijo | Sube | Cuándo |
|---|---|---|
| `mayor:` | 0.**#**.0 | API pública nueva, algo que se rompe o se retira, un cambio de comportamiento |
| `menor:` | 0.0.**#** | Corrige o mejora sin añadir ni quitar API: errores, rendimiento, mensajes |
| `interno:` | — | Reorganización, pruebas, CI, herramientas: el usuario no lo nota |
| `docs:` | — | Solo documentación |
| `version:` | — | Reservado al commit que hace el workflow |

- Cada paquete de `packages/` sube por separado: un commit cuenta para los paquetes cuyos archivos toca. Se miran los commits desde la última etiqueta del paquete (`janelkit-v0.2.0`, `janelkit-desktop-v0.1.1`), y `mayor:` gana a `menor:`.
- El workflow escribe la versión (`pyproject.toml` y `__version__`) y el registro de cambios. Si ya hay una sección con esa versión escrita a mano (`## 0.2.0 (sin publicar)`), solo le pone la fecha; si no, la crea con los asuntos de los commits. Después hace el commit `version: …` y las etiquetas, y lanza `release.yml`, que publica en PyPI.
- Si el núcleo va a salir del rango que declara una extensión (`janelkit>=0.1,<0.2` y el núcleo pasa a 0.2.0), el cálculo se detiene con un error: primero se amplía el rango con un commit `menor:` de la extensión. La CI prueba cada extensión contra el núcleo de la misma rama.
- La **1.0.0** nunca se calcula: se decide a mano.
- La CI rechaza commits sin prefijo válido; en local lo comprueba el hook (`git config core.hooksPath .githooks`, una vez por clon). `python tools/versioning.py plan` dice qué versión tocaría ahora y por qué.

El trabajo de una versión se acumula en una rama; al integrarla en `main`, la CI (`.github/workflows/ci.yml`) prueba cada paquete por separado y, si pasa, se publica. Qué promete cada versión a quien usa JanelKit está en [api.md](api.md#política-de-versiones).

## Rendimiento

Tiempos indicativos (Windows 11, `offscreen` salvo que se diga), para saber qué esperar y detectar regresiones.

**Listas** (`python tools/bench.py`; filas con casilla, texto y botón):

| Operación | `<scroll>`, 1000 filas | `<list>`, 1000 filas | `<list>`, 10 000 filas |
|---|---|---|---|
| Crear | 430 ms | 9 ms | 39 ms |
| Insertar una fila en medio (`insert`) | 5 ms | 2 ms | 16 ms |
| Editar una fila en el sitio | <1 ms | <1 ms | <1 ms |
| Invertir el orden | 93 ms | 11 ms | 25 ms |
| Vaciar | 39 ms | 1 ms | 3 ms |

**Arranque** (`python tools/bench_app.py`): 260–290 ms en frío para cualquier ejemplo de `apps/examples`. Casi todo es importar PySide6; compilar cuesta menos de 10 ms, así que no hay caché de compilación.

**Disposición** (`python apps/examples/flex/bench.py`, ventana real): rejilla de 200 tarjetas, 17 ms por fotograma; 300 tarjetas en un `<scroll>`, 8,7 ms por paso al cambiar el ancho. Una caja vacía cuesta ~32 µs al crearse y un `<text>`, ~30 µs.

**Vídeo** (`python apps/examples/video/bench.py --ventana`; un hilo empuja fotogramas a 60 fps):

| Resolución | Entregados | `push` | De `push` a la entrega (p50 / p95) | CPU del hilo de la interfaz |
|---|---|---|---|---|
| 640 × 480 | 59,6 fps | 0,37 ms | 0,57 / 0,69 ms | 3,1 % |
| 1280 × 720 | 60,1 fps | 0,62 ms | 0,94 / 1,29 ms | 2,6 % |
| 1920 × 1080 | 59,6 fps | 1,07 ms | 1,54 / 1,84 ms | 6,2 % |

`push` copia y convierte la imagen en el hilo que lo llama, así que el de la interfaz solo entrega un `QVideoFrame` ya listo.

## Herramientas

| Herramienta | Para qué |
|---|---|
| `tools/versioning.py` | `plan` (qué versión toca a cada paquete), `apply`, `check` (prefijos) |
| `tools/check_wheel.py` | Construye los wheels, los instala en un entorno limpio y prueba `janel new` + `python main.py` fuera del repositorio |
| `tools/bench.py`, `tools/bench_app.py` | Los tiempos de [Rendimiento](#rendimiento) |
