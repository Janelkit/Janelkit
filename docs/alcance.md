# Alcance de JanelKit: núcleo y ecosistema

JanelKit es un **núcleo** (`janelkit`) y un **ecosistema** de paquetes que se construyen encima con su API pública. Este documento dice qué va en cada sitio, con qué criterio, y qué necesita del núcleo cada paquete. Las prioridades antes del lanzamiento están en [lanzamiento.md](lanzamiento.md).

La frontera se decidió el 28 de octubre de 2026 (decisión 23 de [estado.md](estado.md)) y está aplicada en el código. Dos pruebas la vigilan: `tests/test_boundaries.py` (el núcleo no importa el ecosistema y las extensiones no usan nada interno) y `tests/test_packages.py` (versiones y rangos compatibles).

## Criterio

Una funcionalidad es del **núcleo** si cumple **al menos una** de estas condiciones:

1. **Sin ella no se puede escribir, ejecutar o componer una aplicación `.janel`**: lenguaje, compilador, runtime, controles básicos, CLI esencial.
2. **Necesita detalles internos** que no deben ser públicos: el puente QObject, las regiones dinámicas, el IR del compilador.
3. **Define una semántica que todo lo demás asume**: cómo se propaga un cambio de estado, cuándo se monta y desmonta un componente, cuándo se agrupan cambios (`batch`).

Si algo puede construirse **solo con la API pública** y no todas las aplicaciones lo necesitan, va al **ecosistema**. El núcleo, entonces, se responsabiliza de ofrecer la API pública mínima y estable que ese paquete necesita (ver [puntos de extensión](#puntos-de-extensión)).

Dos casos que el criterio resuelve y conviene recordar:

- **La gestión de estado es del núcleo**, también la que vendrá (stores con acciones): se apoya en la semántica de `batch`, de los efectos y del ciclo de vida, y un paquete aparte acabaría duplicándola o dependiendo de detalles internos. `persisted` y `History` (deshacer/rehacer) ya están dentro.
- **El idioma de la interfaz es del núcleo; las traducciones, no.** La dirección de escritura (derecha a izquierda) y el `QLocale` cambian la disposición de todo, así que `janelkit.locale` está en el núcleo. Los catálogos, plurales y formatos son de `janelkit-i18n`, que cambia ese idioma.

## Organización del repositorio

```
packages/janelkit           núcleo
packages/janelkit-i18n      traducciones
packages/janelkit-desktop   diálogos, portapapeles, notificaciones
packages/janelkit-vscode    resaltado para VS Code
apps/examples               ejemplos pequeños, uno por tema
apps/challenges             aplicaciones grandes que ponen a prueba el framework
tests/                      frontera y coherencia entre paquetes
docs/                       documentación (docs/archivo: documentos históricos)
spikes/                     validaciones técnicas previas
```

- Cada paquete de `packages/` tiene su `pyproject.toml`, su README, sus pruebas y **versión propia**, y se prueba solo (`python -m pytest packages/janelkit-i18n`). Las extensiones declaran el rango del núcleo que admiten ([api.md](api.md#paquetes-del-ecosistema)).
- La CI tiene un trabajo por paquete: el núcleo se prueba con solo `janelkit` instalado, y cada extensión sobre el núcleo y sin las demás.
- Las aplicaciones de `apps/` usan JanelKit como lo haría un usuario. Sus dependencias están en `apps/requirements.txt`.
- Por ahora todo vive en un solo repositorio. Un paquete pasa a repositorio propio cuando tenga ritmo de publicación propio o colaboradores propios; el primer candidato es `janelkit-vscode`.

## El núcleo (`janelkit`)

| Área | Contenido | Estado |
|---|---|---|
| **Lenguaje `.janel`** | Archivo único (`<script lang="python">`, plantilla, `<style>`), interpolación, `on:`, `bind:`, `class:`, `transition:`, `{#if}`, `{#each}`, `{#key}`, `{#hidden}`, slots; `FORMAT_VERSION` | ✅ |
| **Compilador** | Parser con ubicaciones, análisis del script, IR, generación de QML, diagnósticos con sugerencias; `check_source`/`check_file` para herramientas | ✅ |
| **Reactividad y estado** | `state`, `computed`, `effect`, `batch`, colecciones reactivas, props, eventos, contexto (`provide`/`inject`), `persisted`, deshacer/rehacer (`History`) | ✅ · stores con acciones: pendientes |
| **Runtime de componentes** | Instancias, regiones dinámicas, reconciliación por clave, ciclo de vida, referencias a elementos | ✅ |
| **Asincronía** | Manejadores `async def`, `@task`, `background`, `spawn`, temporizadores; todo ligado al componente | ✅ |
| **Disposición y controles** | Motor `<flex>` y vía rápida con layouts de Qt; texto, botón, campos, casilla, select, switch, slider, radio, imagen, progreso, pestañas, lista virtualizada | ✅ |
| **Ventanas y navegación básica** | Varias ventanas, pila de vistas, secciones que se conservan, `navigation()`, `before_leave` | ✅ |
| **Estilos y temas** | Subconjunto de CSS con pseudo-clases y selectores, tokens `var(--x)`, temas intercambiables | ✅ |
| **Idioma de la interfaz** | `janelkit.locale`: idioma, dirección de escritura, `QLocale` | ✅ |
| **Interoperabilidad con Qt** | Importar un `.qml` propio como componente | ✅ |
| **Pruebas** | `janelkit.inspect`: montar sin ventana, buscar, simular eventos, leer el estado. `janelkit.testing`: fixtures de pytest | ✅ inspect · `janelkit.testing` aún interno; será un plugin de pytest delgado y público |
| **CLI** | `janel new`, `dev`, `build`, `compile`, `parse`; subcomandos de otros paquetes | ✅ |

**No es del núcleo:** traducciones, servicios del sistema (diálogos, portapapeles, notificaciones), soporte de editores, bibliotecas de componentes ricos, empaquetado en ejecutables, devtools, enrutado por direcciones y backends distintos de Qt Quick.

## El ecosistema

| Paquete | Qué hace | Usa del núcleo | Estado |
|---|---|---|---|
| [`janelkit-i18n`](../packages/janelkit-i18n/README.md) | `t`, `i18n`: catálogos JSON, plurales, formatos de número, moneda y fecha, cambio de idioma en caliente | `State`, `locale` | ✅ en el repositorio |
| [`janelkit-desktop`](../packages/janelkit-desktop/README.md) | `dialogs`, `clipboard`, `notify`, con sus métodos de inspección (`app.dialogs()`, `app.notifications()`) | `State`, `janelkit.ext` | ✅ en el repositorio |
| [`janelkit-vscode`](../packages/janelkit-vscode/README.md) | Resaltado de `.janel` | — | ✅ resaltado · diagnósticos en vivo y autocompletado (`janelkit-lsp`): pendientes |
| `janelkit-lsp` | Diagnósticos en vivo, autocompletado de elementos, props y nombres del script, ir a definición | `janelkit.compiler` (`check_source`; falta exponer la estructura: props, eventos, nombres) | Idea |
| `janelkit-kit` | Tablas con ordenación y filtrado, gráficas, selectores de fecha, árboles, paneles acoplables | Slots, `ref`, QML propio, tokens de tema | Idea |
| `janelkit-router` | Navegar a direcciones con parámetros, historial con «adelante», rutas anidadas, restaurar la ruta | Navegación básica, contexto, ciclo de vida | Idea ([abajo](#navegación-básica-y-enrutado)) |
| `janel package` | Ejecutables e instaladores con PyInstaller, Nuitka o Briefcase | Recursos del paquete en ubicación estable, `janel build`, plugins de la CLI | Receta manual en [empaquetado.md](empaquetado.md) |
| Devtools | Árbol de componentes, estado de cada instancia, bindings que se recalculan | `janelkit.inspect`; faltan ganchos de depuración en la reactividad | Idea |

Las aplicaciones de `apps/challenges` no son paquetes: son la forma de descubrir qué le falta al núcleo. Cada una tiene un `HALLAZGOS.md` con lo que encontró ([challenges_to_test.md](challenges_to_test.md)).

## Puntos de extensión

Lo que el núcleo ofrece para que el ecosistema crezca sin tocarlo:

| # | Punto | Estado |
|---|---|---|
| 1 | **API pública declarada** ([api.md](api.md)): lo que exporta `janelkit` y los módulos públicos es estable según la política de versiones; lo demás es interno | ✅ `test_public_api.py` |
| 2 | **Inspección** (`janelkit.inspect`): montar sin ventana, recorrer, disparar eventos, leer el estado; las extensiones le añaden métodos con `janelkit.ext.inspector` | ✅ |
| 3 | **Compilador para herramientas**: diagnósticos sin ejecutar el script | 🟡 diagnósticos sí; la estructura (componentes importados, props, eventos, nombres) aún no es pública |
| 4 | **Elementos propios**: un elemento nuevo respaldado por QML que el compilador valida como los integrados | 🟡 se importa un `.qml` como componente; sin declaración de props y eventos para validarlos |
| 5 | **Plugins de la CLI**: subcomandos de `janel` desde otros paquetes, con el grupo de entry points `janelkit.commands` | ✅ |
| 6 | **Versión del formato `.janel`** (`FORMAT_VERSION`) con política de cambios | ✅ |
| 7 | **Acceso a la aplicación** (`janelkit.ext.app()`): motor QML, `QApplication` y ventana principal, para servicios del sistema | ✅ |

## Navegación básica y enrutado

Casi toda aplicación necesita varias vistas y ventanas: eso es del núcleo. El enrutador es otra cosa: traduce **direcciones** a vistas.

- **Navegación básica (núcleo):** se navega a un componente, con sus props: `nav.push(Detalle, item=t)`. Incluye ventanas, la pila de vistas, volver conservando el estado, secciones paralelas que se conservan y la confirmación al salir o cerrar con cambios sin guardar.
- **Enrutado (`janelkit-router`):** se navega a un texto, `/proyectos/42/tablero?tarjeta=t5`, que el enrutador traduce a vistas y parámetros. Sirve para guardar, compartir o reconstruir «dónde estoy».

| Capacidad | Dónde |
|---|---|
| Abrir ventanas con props, eventos y modo modal | Núcleo ✅ |
| Pila de vistas: ir, volver, sustituir; volver conserva el estado; lo descartado se libera | Núcleo ✅ |
| Secciones paralelas, cada una con su pila, que se conservan al ocultarse | Núcleo ✅ `sections()`, `{#hidden}` |
| Confirmar antes de salir de una vista o cerrar una ventana | Núcleo ✅ `before_leave` |
| Obtener la pila sin pasarla, atrás con teclado y ratón, devolver un resultado | Núcleo ✅ `navigation()`, `back(valor)` |
| Rutas con nombre y parámetros, historial con adelante, enlaces profundos | Enrutador |
| Rutas anidadas declaradas como tabla, restaurar la ruta, carga diferida | Enrutador |

El reto del [gestor de proyectos](challenges_to_test.md#6-gestor-de-proyectos) se hizo solo con la navegación básica; sus [hallazgos](../apps/challenges/gestor/HALLAZGOS.md) dicen qué quedaría para el enrutador, que debe poder construirse con la API pública.

## Añadir un paquete al ecosistema

1. Crear `packages/janelkit-<nombre>/` con `pyproject.toml` (versión propia, `janelkit>=X,<Y`), `README.md` con una sección «Cambios», `src/janelkit_<nombre>/` y `tests/` con un `conftest.py` que importe las fixtures de `janelkit.testing`.
2. Usar solo la API pública del núcleo. Si falta algo, se añade al núcleo como punto de extensión, con prueba y entrada en [api.md](api.md), antes de usarlo.
3. Añadirlo a `pytest.ini`, a `requirements-dev.txt`, a la matriz `extensions` de la CI y, si tiene wheel, a `EXTENSIONS` en `tools/check_wheel.py`. `tests/test_boundaries.py` y `tests/test_packages.py` lo revisan solos; actualiza la lista esperada de `test_packages.py`.
