# Pendientes antes del lanzamiento

Prioriza lo que falta en **el framework** antes de su primera versión pública (0.1 en PyPI). Los proyectos paralelos (editor, pruebas, stores, empaquetado…) quedan fuera; ver [alcance.md](alcance.md).

Situación de partida: incrementos 0–7 completos; detalle en [estado.md](estado.md).

## Avance

| # | Pendiente | Prioridad | Estado | Evidencia |
|---|---|---|---|---|
| 1 | Colecciones reactivas | P0 | ✅ | `tests/test_collections.py`, `tools/bench.py` |
| 2 | Modificar estado desde la plantilla | P0 | ✅ | manejadores en línea; `tests/test_runtime_qt.py::test_inline_handlers_*` |
| 3 | Slots | P0 | ✅ | `tests/test_slots_qt.py` |
| 4 | Ciclo de vida y referencias | P0 | ✅ | `tests/test_lifecycle_qt.py` |
| 5 | Asincronía y segundo plano | P0 | ✅ | `tests/test_async_qt.py`, `examples/books` |
| 6 | Contexto | P0 | ✅ | `tests/test_lifecycle_qt.py::test_provide_*` |
| 7 | Superficie pública y versionado | P0 | ✅ | [api.md](api.md), `tests/test_public_api.py` |
| 8 | Interoperabilidad con Qt | P0 | ✅ | `.qml` propios; `tests/test_qml_elements_qt.py`, `examples/counter` |
| 9 | Controles que faltan | P1 | ✅ | `tests/test_controls_qt.py` (Switch, Slider, Select, RadioGroup, Tabs, Image, ProgressBar, Shortcut, diálogos, `on:input` en TextArea) |
| 10 | Lista virtualizada | P1 | ✅ | `<List>`; `tests/test_list_qt.py`; 10 000 filas en ~40 ms (`tools/bench.py`) |
| 12 | Aplicaciones de validación | P1 | ✅ | `examples/files`, `examples/books`; hallazgos en [estado.md](estado.md#validación-con-aplicaciones-reales) |
| 13 | Rendimiento de una aplicación mediana | P1 | ✅ | `tools/bench_app.py`; arranque < 300 ms, interacciones < 70 ms |
| 15 | API de inspección pública | P1 | ✅ | `fluxui.inspect`; `tests/test_inspect.py` |
| 14 | Accesibilidad básica | P1 | ✅ | `tests/test_accessibility_qt.py`: orden de Tab, Espacio/Intro en cajas pulsables, foco visible, nombres accesibles (`label`, `alt`) |
| 11 | Linux, macOS y CI | P1 | 🟡 | CI con matriz preparada (`.github/workflows/ci.yml`); versiones mínimas (Python 3.10 + PySide6 6.8) verificadas en Windows. **Falta:** ejecutarla en GitHub (necesita un remoto) para probar Linux y macOS. |
| 16 | Documentación de lanzamiento | P1 | ✅ | [tutorial.md](tutorial.md) (con `examples/compra` probado), [api.md](api.md), [cambios.md](cambios.md), [empaquetado.md](empaquetado.md) (receta verificada con PyInstaller) |
| 17 | Nombre, licencia y publicación | P1 | 🟡 | Nombre decidido: **JanelKit** (`janelkit`, comando `janel`, archivos `.janel`; [estado.md](estado.md#decisiones-provisionales-tomadas-al-implementar), decisión 23). **Falta:** aplicar el renombrado, elegir licencia y publicar en TestPyPI. |
| 18 | Tipos en props | P2 | ✅ | `edad: int = prop(0)`; literales al compilar, valores dinámicos al ejecutar (`tests/test_components_qt.py`) |
| 20 | Transiciones y animaciones | P2 | ✅ | `transition:`/`in:`/`out:`, `transition` en CSS, `<List animate>` (`tests/test_transitions_qt.py`) |
| 23 | `class={expr}` dinámico | P2 | ✅ | `tests/test_runtime_qt.py::test_dynamic_class_expression` |
| 19 | Varias ventanas y tema por ventana | P2 | ✅ | `open_window`; `tests/test_windows_qt.py` |
| 24 | Navegación entre pantallas | P2 | ✅ | `pages()` y `<Pages>`; `tests/test_pages_qt.py` |
| 21 | Internacionalización | P2 | ✅ | `t`, `i18n`; formatos con QLocale; RTL; `examples/idiomas`; `tests/test_i18n_qt.py` |
| 22 | `flux dev` conservando el estado (HMR) | P2 | ✅ | `tests/test_dev.py::test_reload_keeps_state_unless_the_script_changed` |
| 25 | Secciones que conservan sus vistas | P0 | ✅ | `sections()`/`<Sections>` y `{#hidden}`; `tests/test_navigation.py`. Cambiar de sección con 500 filas: ~13 ms (crearla, ~80 ms) |
| 26 | Salir de una vista o cerrar una ventana con cambios sin guardar | P1 | ✅ | `before_leave` (también `async`); `tests/test_navigation.py` |
| 27 | Experiencia de navegación | P1 | ✅ | `navigation()`, `await push` / `back(valor)`, Alt+← y botón «atrás» del ratón; `tests/test_navigation.py`. `<Pages transition:slide>`. Pendiente opcional: `open_window(..., single=True)` |

## Cómo se prioriza

| Prioridad | Significado |
|---|---|
| **P0** | Cambia la API o la semántica. Si se publica sin resolverlo, arreglarlo después rompe aplicaciones de terceros. **Bloquea el lanzamiento.** |
| **P1** | Sin ello una aplicación real típica no se puede hacer o el proyecto no se puede evaluar en serio. **Bloquea el lanzamiento.** |
| **P2** | Mejora que técnicamente podría añadirse después sin romper nada, pero que forma parte de lo que se quiere ofrecer en la primera versión. **Bloquea el lanzamiento.** |

Las tres prioridades son necesarias para publicar; la prioridad indica el **orden** en que se abordan, no si se hacen.

Tamaño estimado: **S** (días), **M** (1–2 semanas), **L** (más de 2 semanas).

## P0 — Decisiones de API y semántica

### 1. Colecciones reactivas · M
- **Problema:** `todos.value.append(x)` o `item["done"] = True` no actualizan la interfaz y no avisan. Es el error más probable de quien viene de Python.
- **Propuesta:** que `state([...])` y `state({...})` devuelvan listas y diccionarios reactivos que notifican mutaciones in situ; las filas de `{#each}` se actualizan de forma granular.
- **Hecho cuando:** `append`, `remove`, `insert`, asignación por índice/clave y mutación de un diccionario dentro de una lista actualizan la interfaz; la reasignación sigue funcionando; hay pruebas y medición de rendimiento.

### 2. Modificar estado desde la plantilla · S
- **Problema:** `on:click={lambda: count.set(count + 1)}` falla porque en la plantilla el `state` llega desenvuelto; obliga a crear funciones para cambios triviales.
- **Propuesta:** decidir y documentar una forma directa. Opciones: no desenvolver dentro de manejadores, o una sintaxis de asignación (`on:click={count += 1}`).
- **Hecho cuando:** existe una forma de una línea para modificar estado desde un evento, documentada y con diagnóstico claro si se usa mal.

### 3. Slots · M
- **Problema:** `<Card>contenido</Card>` no es posible; sin eso no hay componentes contenedores (tarjeta, diálogo, panel, layout).
- **Propuesta:** slot por defecto y slots con nombre; el contenido se evalúa en el ámbito del padre. Incluir `class` en la etiqueta del componente.
- **Hecho cuando:** un componente puede envolver contenido arbitrario, incluidos `{#each}` y otros componentes, con estado del padre reactivo dentro.

### 4. Ciclo de vida y referencias · M
- **Problema:** no hay forma pública de ejecutar código al montar o desmontar, ni de llegar a un elemento para darle el foco o desplazar la vista.
- **Propuesta:** `on_mount(fn)`, `on_destroy(fn)`, efectos con limpieza ligados al componente, y `ref` (`<TextField ref={campo} />` → `campo.focus()`), con un conjunto pequeño de métodos soportados.
- **Hecho cuando:** los recursos registrados en un componente se liberan siempre al desmontar (probado con `{#if}`, `{#each}` y recarga de `flux dev`).

### 5. Asincronía y trabajo en segundo plano · L
- **Problema:** todo ocurre en el hilo de Qt; una petición de red o una lectura grande congela la ventana.
- **Propuesta:** manejadores `async def` integrados con el bucle de Qt; una función para ejecutar trabajo en otro hilo y aplicar el resultado al estado en el hilo de la interfaz; cancelación al desmontar el componente.
- **Hecho cuando:** existe un ejemplo que consulta una API sin bloquear la ventana, muestra «cargando» y «error», y no actualiza componentes ya desmontados.

### 6. Contexto (compartir estado entre componentes) · S
- **Problema:** hoy se comparte estado importando un módulo de `services/`, que es global al proceso; no hay forma de compartir algo solo con un subárbol, y el tema es global.
- **Propuesta:** `provide(clave, valor)` / `inject(clave)` como primitivas. Los stores avanzados quedan para `fluxui-store`.
- **Hecho cuando:** dos subárboles pueden recibir valores distintos para la misma clave, y está documentado cuándo usar contexto y cuándo un módulo.

### 7. Superficie pública y versionado · S
- **Problema:** no está definido qué es público; cualquier refactor interno podría romper a los usuarios.
- **Propuesta:** listar la API pública (`fluxui`, `fluxui.inspect`, API del compilador para herramientas); marcar el resto como interno; definir versión del formato `.flux` y política de cambios para la serie 0.x.
- **Hecho cuando:** existe `docs/api.md` (o equivalente) y una prueba que falla si cambia la superficie pública sin intención.

### 8. Interoperabilidad con Qt · M
- **Problema:** si a un usuario le falta un control, no tiene salida y debe abandonar el framework.
- **Propuesta:** registrar elementos propios respaldados por un archivo QML del proyecto o por un tipo Qt, declarando sus props y eventos para que el compilador los valide.
- **Hecho cuando:** un ejemplo usa un control QML propio con props, eventos y `bind:`, sin modificar FluxUI.

## P1 — Necesario para una primera versión utilizable

### 9. Controles que faltan · M
`Select`, `Switch`, `Slider`, `Radio`/`RadioGroup`, `Image`, `ProgressBar`, `Tabs`; diálogos nativos de abrir/guardar archivo y de mensaje; atajos de teclado; `on:input` en `TextArea`. Cada uno con estilos por tokens y pruebas.

### 10. Lista virtualizada · M
Un `{#each}` (o elemento `List`) basado en `ListView` que solo crea las filas visibles. Objetivo: 10 000 filas con creación por debajo de 100 ms y desplazamiento fluido.

### 11. Linux, macOS y CI · M
Probar en las tres plataformas (fuentes, escalado, estilo *Basic*); CI con matriz de sistemas y de versiones Python (3.10–3.13) y PySide6 (mínima declarada y actual), incluido `tools/check_wheel.py`.

### 12. Aplicaciones de validación · M
Construir dos aplicaciones medianas con FluxUI antes de publicar, por ejemplo un cliente de una API (asincronía, listas, formularios) y un gestor de archivos (diálogos, lista grande, atajos). Todo lo que falte o cueste se convierte en pendiente. Sirven también como ejemplos.

### 13. Rendimiento de una aplicación mediana · S
Medir arranque, tiempo de compilación y respuesta de las aplicaciones de validación; cachear lo compilado si el arranque lo justifica. Publicar las cifras en `estado.md`.

### 14. Accesibilidad básica · S
Navegación completa con teclado, orden del foco, foco visible y nombres accesibles en los controles básicos.

### 15. API de inspección pública · S
Pasar de `tests/conftest.py` a una API pública: montar sin ventana visible, buscar elementos, disparar eventos y leer el estado. Es la base de `fluxui-testing` y de las pruebas de los propios usuarios.

### 16. Documentación de lanzamiento · M
Tutorial de inicio de principio a fin; referencia de la API pública; guía de migración entre versiones 0.x; receta documentada para empaquetar con PyInstaller (sin comando propio).

### 17. Nombre, licencia y publicación · S
Verificar disponibilidad de `fluxui`/`flux` en PyPI (y conflictos con el comando `flux` de otras herramientas); elegir licencia; publicar primero en TestPyPI y repetir `check_wheel.py` contra lo publicado.

## P2 — Completar la primera versión

### 18. Tipos en props · M
- **Problema:** las props no declaran tipo; un valor equivocado solo falla al ejecutarse, lejos de donde se pasó.
- **Propuesta:** `prop[int](0)` o anotaciones (`edad: int = prop(0)`); el compilador comprueba los literales y el runtime valida los valores dinámicos en modo desarrollo.
- **Hecho cuando:** pasar un tipo incorrecto produce un diagnóstico con archivo y línea del uso; las props sin tipo siguen funcionando.

### 19. Varias ventanas y tema por ventana · M
- **Problema:** una aplicación solo tiene una ventana raíz y el tema es global al proceso.
- **Propuesta:** abrir ventanas secundarias y diálogos propios desde el script (`open_window(Componente, props)`), con ciclo de vida ligado a quien las abre; el tema se resuelve por contexto, con el global como valor por defecto.
- **Hecho cuando:** un ejemplo abre y cierra una ventana secundaria que comparte estado con la principal, y cada ventana puede usar un tema distinto.

### 20. Transiciones y animaciones · M
- **Problema:** los elementos aparecen y desaparecen de golpe; en escritorio se nota.
- **Propuesta:** directivas al estilo de `transition:fade` / `transition:slide` para `{#if}` y `{#each}`, y animación de propiedades de estilo (`transition` en `<style>`), sobre las animaciones de Qt Quick.
- **Hecho cuando:** montar, desmontar y reordenar filas puede animarse sin que el desmontaje real se adelante ni se pierdan suscripciones.

### 21. Internacionalización · M
- **Problema:** los textos están escritos en la plantilla; no hay forma de traducirlos ni de soportar idiomas de derecha a izquierda.
- **Propuesta:** función de traducción reactiva (`t("clave")`) con catálogos por idioma, cambio de idioma en caliente, formatos de número y fecha según la configuración regional, y disposición RTL.
- **Hecho cuando:** un ejemplo cambia de idioma en ejecución, incluido uno RTL, sin reiniciar.

### 22. `flux dev` conservando el estado (HMR) · L
- **Problema:** cada recarga devuelve la interfaz a su estado inicial; en formularios largos o flujos de varios pasos hace perder tiempo.
- **Propuesta:** al recargar un `.flux`, conservar los `state` de las instancias cuyo componente no cambió de forma incompatible (mismos nombres y tipos); remontar el resto. Depende del ciclo de vida (4).
- **Hecho cuando:** editar el estilo o la plantilla de un componente conserva lo escrito en sus campos; cambiar su script lo reinicia de forma predecible y lo indica en la consola.

### 23. `class={expr}` dinámico · S
- **Problema:** solo hay clases condicionales (`class:x={cond}`); no se puede elegir la clase con una expresión.
- **Propuesta:** aceptar una cadena, lista o diccionario (`class={["card", variante]}`); el compilador genera los estilos de todas las clases conocidas y el runtime decide cuáles aplica.
- **Hecho cuando:** cambiar la expresión cambia los estilos aplicados, y una clase inexistente produce una advertencia.

### 24. Navegación entre pantallas · S
- **Problema:** pasar de una pantalla a otra exige escribir a mano `{#if}` con un estado de página.
- **Propuesta:** un elemento de pila de páginas en el núcleo (`<Pages>` con `push`/`pop`/`replace`), con ciclo de vida por página. El enrutado avanzado sigue siendo un proyecto paralelo.
- **Hecho cuando:** un ejemplo navega entre tres pantallas, vuelve atrás conservando el estado de la anterior y libera las que se descartan.

### 25. Secciones que conservan sus vistas · M
- **Problema:** una aplicación con barra lateral o pestañas (Proyectos, Personas, Mi trabajo) necesita una pila por sección. Hoy se monta a mano: una `pages()` por sección y `{#if}` para elegir cuál se ve. `{#if}` destruye la sección que se oculta, así que al volver se pierden la búsqueda, el desplazamiento y lo que se estaba escribiendo.
- **Propuesta:** una forma de que el contenido oculto se conserve en vez de destruirse. Puede ser general (para cualquier `{#if}` o `<Tabs>`) o propia de la navegación (secciones, cada una con su pila). La elección afecta al lenguaje, por eso es P0.
- **Decisión:** las dos. `sections()` y `<Sections>` para la navegación, y la directiva `{#hidden cond}` para cualquier contenido.
- **Hecho cuando:** un ejemplo con tres secciones, cada una con su pila, cambia de sección y vuelve encontrando cada una como la dejó. Ocultar una sección no cuesta más que no mostrarla, y descartarla la libera.

### 26. Salir de una vista o cerrar una ventana con cambios sin guardar · S
- **Problema:** no hay forma de que una página impida `pop`, `replace` o `reset`, ni de que una ventana impida cerrarse. Hay que comprobarlo en cada botón, y cerrar la ventana con la X no se puede interceptar.
- **Propuesta:** la página o la ventana registra en su script una función que decide si se puede salir. Puede ser `async` para preguntar con `dialogs.confirm`. Si responde que no, la navegación o el cierre se cancelan.
- **Hecho cuando:** con un formulario modificado, volver atrás, cambiar de sección, cerrar la ventana con la X y cerrar la aplicación preguntan antes. Sin cambios, no preguntan.

### 27. Experiencia de navegación · S
- **Problema:** para que una página navegue tiene que recibir la pila a mano (prop o `provide`). `nav.current` es un texto con el nombre del componente. Atrás no responde a Alt+← ni al botón lateral del ratón. Una página que elige algo y vuelve devuelve el resultado con un evento.
- **Propuesta:** que una página obtenga su pila sin pasarla. Que `<Pages>` responda a Alt+← y al botón «atrás» del ratón. Que una página pueda devolver un resultado a quien la abrió. Opcional: transición al cambiar de página.
- **Hecho cuando:** la aplicación de ejemplo del 25 navega sin pasar la pila entre páginas, vuelve con Alt+← y con el ratón, y una página de selección devuelve su resultado con `await`.

## Orden sugerido

1. **Primero lo que define la API:** 1, 2, 7. Son pequeños o medianos y condicionan todo lo demás.
2. **Composición:** 3, 4, 6. Comparten el mismo trabajo sobre el runtime de componentes.
3. **Asincronía e interoperabilidad:** 5 y 8.
4. **Validación con aplicaciones reales** (12) en paralelo a los controles (9) y la lista virtualizada (10): las aplicaciones dirán qué controles hacen falta de verdad.
5. **Completar el lenguaje:** 18, 23 y 20 (tipos en props, clases dinámicas, transiciones).
6. **Aplicaciones de varias pantallas:** 19, 24 y 21 (ventanas, navegación, idiomas). Conviene incorporarlas a las aplicaciones de validación. Después, 25, 26 y 27 (navegación básica completa).
7. **Experiencia de desarrollo:** 22 (HMR), cuando el ciclo de vida esté estable.
8. **Preparar la publicación:** 11, 13, 14, 15, 16 y 17. La documentación (16) y las mediciones (13) se cierran al final para cubrir todo lo anterior.

## Criterio de lanzamiento

Se publica la 0.1 cuando:

- [ ] Todos los P0, P1 y P2 están hechos o descartados de forma explícita y documentada.
- [ ] Las aplicaciones de validación funcionan sin modificar el framework a mano.
- [ ] La CI pasa en Windows, Linux y macOS.
- [ ] `pip install` → `flux new` → `python main.py` funciona desde TestPyPI en un entorno limpio.
- [ ] La API pública está documentada y protegida por pruebas.
- [ ] Hay licencia, nombre verificado y tutorial de inicio.
