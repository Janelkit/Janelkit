# Alcance de FluxUI y proyectos paralelos

Este documento delimita qué es **el framework FluxUI** (este repositorio) y qué queda fuera, como **proyectos paralelos** que pueden construirse encima. Por ahora el trabajo se centra solo en el framework; los proyectos paralelos se describen para que el núcleo deje preparados los puntos de extensión que necesitarán, no para desarrollarlos ya.

Prioridades antes del lanzamiento: [lanzamiento.md](lanzamiento.md).

## Criterio para decidir qué pertenece al núcleo

Una funcionalidad pertenece al framework si cumple **al menos una** de estas condiciones:

1. **Sin ella no se puede escribir, ejecutar o componer una aplicación `.flux`** (lenguaje, compilador, runtime, controles básicos, CLI esencial).
2. **Necesita acceder a detalles internos** que no deben ser públicos (el puente QObject, las regiones dinámicas, el IR del compilador).
3. **Define una semántica que todo lo demás asume** (cómo se propaga un cambio de estado, cuándo se monta y desmonta un componente).

Si algo puede construirse **solo con la API pública** y no todas las aplicaciones lo necesitan, es un proyecto paralelo. El núcleo, en ese caso, se responsabiliza de ofrecer la **API pública mínima y estable** que ese proyecto necesita.

## El framework (núcleo)

### Qué incluye

| Área | Contenido | Estado actual |
|---|---|---|
| **Lenguaje `.flux`** | Formato de archivo único (`<script lang="python">`, plantilla, `<style>`), interpolación, `on:`, `bind:`, `class:`, `{#if}`, `{#each}`, `{#key}`, slots | ✅ (también `transition:`, `class={expr}`, manejadores en línea) |
| **Compilador** | Parser con ubicaciones, análisis del script, IR, generación de QML, diagnósticos con sugerencias | ✅ |
| **Reactividad** | `state`, `computed`, efectos, props, eventos, **colecciones reactivas**, **contexto** (provide/inject) | ✅ |
| **Runtime de componentes** | Instancias, regiones dinámicas, reconciliación por clave, **ciclo de vida** (`on_mount`, `on_destroy`), **referencias a elementos** | ✅ |
| **Asincronía** | Manejadores `async def` y trabajo en segundo plano con retorno seguro al hilo de la interfaz | ✅ (`qasync`, `@task`, `background`) |
| **Backend Qt** | Módulo QML interno `Flux`, controles básicos, disposición flex, ventanas | ✅ (varias ventanas, navegación, idiomas y derecha a izquierda) |
| **Controles básicos** | Los necesarios para formularios y navegación sencilla: texto, botón, campos, casilla, select, switch, slider, radio, imagen, progreso, pestañas, diálogos nativos, lista virtualizada | ✅ |
| **Estilos y temas** | Subconjunto de CSS, tokens `var(--x)`, temas intercambiables | ✅ |
| **Interoperabilidad con Qt** | Usar un componente QML propio o un objeto Qt existente desde un `.flux` cuando FluxUI no alcanza | ✅ (importar `.qml`) |
| **CLI esencial** | `flux new`, `flux dev`, `flux build`, `flux compile`, `flux parse` | ✅ |
| **API de inspección** | Montar un componente sin ventana visible, buscar elementos, simular eventos, leer el estado. Base para cualquier herramienta de pruebas | ✅ `fluxui.inspect` |
| **API del compilador para herramientas** | Obtener diagnósticos y la estructura de un `.flux` sin ejecutarlo. Base para editores | ✅ `check_source`/`check_file` |
| **Documentación** | Referencia del lenguaje, estilos, flujo de desarrollo, tutorial de inicio | ✅ |

### Qué no incluye

- Extensiones de editor, servidor de lenguaje (LSP) o autocompletado.
- Un framework de pruebas (plugin de pytest, snapshots, fixtures).
- Gestión de estado avanzada: stores con persistencia, deshacer/rehacer, sincronización.
- Bibliotecas de componentes ricos: tablas de datos, gráficas, selectores de fecha, editores de texto enriquecido.
- Empaquetado de aplicaciones en ejecutables (`.exe`, `.app`, instaladores).
- Herramientas de inspección visual en tiempo de ejecución (devtools).
- Enrutado complejo con historial, parámetros o carga diferida.
- Backends distintos de Qt Quick (web, widgets nativos, móvil).

## Proyectos paralelos

Cada proyecto se apoya en una **API del núcleo** concreta. Esa API es la que el framework debe estabilizar; el proyecto en sí puede esperar.

| Proyecto | Qué haría | Depende de (API del núcleo) | Notas |
|---|---|---|---|
| **Soporte de editor** (`fluxui-vscode`, `fluxui-lsp`) | Resaltado, diagnósticos en vivo, autocompletado de elementos, props y nombres del script, ir a definición | API del compilador para herramientas | El resaltado de `editors/vscode/` es su semilla; debería salir de este repositorio cuando tenga entidad propia |
| **Pruebas** (`fluxui-testing`) | Plugin de pytest, fixtures, consultas tipo Testing Library (por texto, por rol), capturas visuales comparables | API de inspección | El núcleo ofrece montar, buscar y disparar eventos; la ergonomía de pruebas va aparte |
| **Gestión de estado** (`fluxui-store`) | Stores con acciones, persistencia en disco, deshacer/rehacer, estado derivado entre ventanas | `state`, `computed`, efectos, colecciones reactivas, contexto | El núcleo da las primitivas; los patrones de arquitectura van aparte |
| **Biblioteca de componentes** (`fluxui-kit`) | Tablas con ordenación y filtrado, gráficas, selectores de fecha, árboles, paneles acoplables | Slots, `ref`, interoperabilidad con Qt, tokens de tema | Se escribe en `.flux` (y QML propio cuando haga falta), como lo haría un usuario |
| **Empaquetado** (`flux package`) | Generar ejecutables e instaladores con PyInstaller, Nuitka o Briefcase | Ubicación estable de recursos del paquete (módulo QML, plantillas); `flux build` | Puede ser un plugin de la CLI. El núcleo debe garantizar que las apps sean empaquetables y documentar una receta |
| **Devtools** | Ventana que muestra el árbol de componentes, el estado de cada instancia y qué bindings se recalculan | API de inspección; ganchos de depuración en la reactividad | Útil cuando haya aplicaciones medianas |
| **Enrutado** (`fluxui-router`) | Navegación entre pantallas con historial y parámetros | Slots, contexto, ciclo de vida | Para casos sencillos bastan `{#if}` y una pila de páginas en el núcleo. El reto 6 ([gestor de proyectos](challenges_to_test.md#6-gestor-de-proyectos)) lo necesita y lista qué pediría |
| **Plantillas y ejemplos** | Galería de aplicaciones de referencia y plantillas para `flux new` | API pública completa | Sirven además para validar el framework con uso real |

## Puntos de extensión que el núcleo debe ofrecer

Para que los proyectos paralelos sean posibles sin tocar el núcleo:

1. **API pública declarada:** lo que se importa desde `fluxui` (y submódulos marcados como públicos) es estable; lo demás es interno y puede cambiar.
2. **API de inspección** (`fluxui.inspect` o similar): montar sin ventana, recorrer elementos, disparar eventos, leer el estado de una instancia.
3. **API del compilador para herramientas:** analizar un `.flux` y obtener diagnósticos, componentes importados, props, eventos y nombres definidos, sin ejecutar el script.
4. **Registro de elementos propios:** declarar un elemento nuevo respaldado por QML o por un tipo Qt, con sus props y eventos, para que el compilador lo valide igual que los integrados.
5. **Plugins de la CLI:** que un paquete instalado pueda añadir subcomandos (`flux package`, `flux test`) mediante *entry points*.
6. **Versión del formato `.flux`:** el lenguaje tiene número de versión propio y política de cambios, para que editores y herramientas sepan qué esperar.

## Organización del repositorio

Mientras el núcleo no se estabilice, todo puede vivir aquí. Al publicar:

- `src/fluxui/` es el framework.
- `editors/vscode/` se mueve a su propio repositorio (o se marca como experimental).
- Las utilidades de pruebas de `tests/conftest.py` que sean de uso general pasan a la API de inspección; la ergonomía de pruebas queda para `fluxui-testing`.
