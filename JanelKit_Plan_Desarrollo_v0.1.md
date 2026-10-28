# JanelKit — Plan incremental de desarrollo

> **Documento de diseño y ejecución | Versión 0.1 | 26 de octubre de 2026**  
> **Estado:** propuesta inicial, sujeta a validación técnica y adopción por la comunidad.  
> **Nombre y extensión provisionales:** `JanelKit` y `.janel`. No se consideran decisiones de marca definitivas.

## 1. Propósito

Construir un framework de aplicaciones de escritorio con **Python** que ofrezca una experiencia de autoría cercana a la de los frameworks frontend modernos. Su unidad de desarrollo será el **componente de archivo único** (*Single File Component*, SFC): un archivo que declara estructura, comportamiento y estilos de una porción de la interfaz.

El framework no pretende sustituir a Qt como motor gráfico. Su objetivo es proporcionar un lenguaje declarativo y un conjunto de herramientas que permitan aprovechar Qt sin exigir al autor de cada pantalla que escriba QML ni conecte manualmente señales y propiedades.

**Propuesta de valor:** escribir componentes reactivos de escritorio con una sintaxis familiar para desarrolladores frontend, utilizar Python para la lógica y renderizar mediante Qt.

**Decisión vigente de plataforma:** desarrollar y validar JanelKit sobre **Qt 6 / Qt Quick + PySide6**, sin implementar integraciones alternativas. La prioridad es publicar un MVP y comprobar si desarrolladores externos adoptan el modelo SFC. Una eventual implementación de partes internas en **C++** se evaluará únicamente después de esa validación y ante necesidades técnicas demostradas; no es una etapa comprometida del desarrollo.

### Usuario principal

- Desarrollador Python que necesita crear aplicaciones de escritorio con interfaces cuidadas.
- Desarrollador frontend que quiere trabajar con componentes, estado reactivo y estilos sin introducir un navegador en la aplicación.
- Equipo que necesita reutilizar componentes visuales y lógica Python en proyectos de escritorio.

### Principios de diseño

1. **Declarativo por defecto.** El archivo describe qué debe aparecer, no cómo construir y actualizar manualmente cada elemento Qt.
2. **Compilación antes que interpretación permanente.** El compilador transforma la plantilla en una representación ejecutable para Qt; los cambios de estado no deben obligar a recorrer y reconstruir todo el árbol.
3. **Python como lenguaje de comportamiento.** El usuario no necesita JavaScript para programar sus componentes.
4. **Un componente, una responsabilidad.** La composición es el mecanismo principal de reutilización.
5. **Qt permanece accesible.** Las funciones avanzadas se incorporarán mediante adaptadores o mecanismos explícitos de interoperabilidad, sin intentar reproducir de inmediato todo Qt.
6. **Errores comprensibles.** Los diagnósticos deben indicar archivo, línea y causa probable.
7. **Evolución incremental.** Cada etapa entrega una aplicación ejecutable y pruebas que impiden regresiones.
8. **Validar antes de optimizar.** PySide6 será el único binding del producto en su etapa actual. El trabajo se concentrará en la experiencia de desarrollo y en su aceptación por la comunidad; no se invertirá en C++ sin evidencia posterior de adopción y de una limitación técnica concreta.
9. **Distribución pública desde el inicio.** JanelKit se desarrolla como biblioteca Python instalable, no como código que deba copiarse dentro de cada aplicación. Su distribución principal será PyPI mediante `pip`, después de validar nombre, licencia y paquetes.
10. **Una entrada Python por proyecto.** Cada proyecto generado tendrá un `main.py` en su raíz que inicia JanelKit. El componente raíz de interfaz será `src/App.janel`; los usuarios podrán ejecutar la aplicación con `python main.py`, independientemente de los comandos auxiliares del CLI.

## 2. Alcance del producto

### Experiencia de desarrollo objetivo

Una vez publicada la biblioteca en PyPI, el recorrido previsto para una persona nueva será:

```bash
python -m pip install janelkit
janel new mi-app
cd mi-app
python main.py
```

Para desarrollar con recompilación al guardar se ofrecerá, además, `janel dev`. Los nombres `janelkit` (distribución) y `janel` (ejecutable) son **provisionales** y deberán verificarse antes del registro público. **Estos comandos describen la API objetivo; no implican que el paquete ya esté disponible en PyPI.**

Estructura que deberá producir `janel new mi-app`:

```text
mi-app/
├── main.py                 # Punto de entrada ejecutable de la aplicación
├── src/
│   ├── App.janel            # Componente raíz de la interfaz
│   ├── components/
│   │   └── Counter.janel
│   ├── pages/
│   └── services/
│       └── users.py
├── assets/
├── pyproject.toml          # Metadatos y dependencias del proyecto creado
├── README.md
└── .gitignore
```

`main.py` **siempre estará en la raíz del proyecto generado**. No sustituye a `App.janel`: el archivo Python inicia el runtime, y el archivo `.janel` define el árbol principal de la interfaz. `janel dev` y `janel build` serán herramientas complementarias, no requisitos para entender cómo arranca la aplicación.

Contenido objetivo del `main.py` generado:

```python
from pathlib import Path
from janelkit import run

if __name__ == "__main__":
    run(Path(__file__).parent / "src" / "App.janel")
```

`run()` es una **API pública propuesta**, pendiente de implementación; tendrá que crear o administrar una sola instancia de `QGuiApplication`, inicializar el runtime y cargar el componente raíz. La ruta se resuelve respecto a `main.py`, para que `python main.py` no dependa del directorio de trabajo.

### Ejemplo del lenguaje que se pretende construir

```html
<script lang="python">
from janelkit import state, computed

count = state(0)
name = state("")

@computed
def greeting():
    return f"Hola, {name.value or 'invitado'}"

def increment():
    count.value += 1
</script>

<Window title="Mi aplicación" width={640} height={400}>
  <Column class="page">
    <Text class="heading">{greeting}</Text>
    <TextField bind:value={name} placeholder="Tu nombre" />
    <Button on:click={increment}>Clicks: {count}</Button>

    {#if count >= 5}
      <Text>Has llegado a cinco clicks.</Text>
    {/if}
  </Column>
</Window>

<style>
.page { padding: 24px; gap: 16px; }
.heading { font-size: 24px; font-weight: 600; }
</style>
```

**Importante:** este ejemplo define una intención de diseño, no una gramática cerrada ni un programa que ya funcione. Los detalles de `state`, las referencias a variables y la sintaxis de eventos deberán consolidarse mediante pruebas de uso.

### Capacidades objetivo

| Capacidad | Ejemplo propuesto | Prioridad |
|---|---|---|
| Interpolación reactiva | `{count}`, `{greeting}` | P0 |
| Estado local | `state(0)` | P0 |
| Eventos | `on:click={increment}` | P0 |
| Propiedades dinámicas | `enabled={count > 0}` | P0 |
| Binding bidireccional | `bind:value={name}` | P0 |
| Condicionales | `{#if condition} ... {/if}` | P0 |
| Iteración con clave | `{#each items as item (item.id)}` | P0 |
| Componentes y propiedades | `<UserCard user={user} />` | P0 |
| Estilos de alcance local | `<style>...</style>` | P0 básico / P1 avanzado |
| Valores derivados | `@computed` | P0 |
| Emisión de eventos | evento propio del componente | P1 |
| Slots / contenido proyectado | contenido hijo | P1 |
| Recarga durante desarrollo | `janel dev` | P1 |
| `watch`, transiciones, animaciones | APIs reactivas adicionales | P1/P2 |
| Tablas complejas y controles especializados | adaptadores Qt | P2 |
| Acceso a capacidades avanzadas de Qt | extensiones controladas mediante Qt Quick / PySide6 | P2 |

**P0** significa imprescindible para el primer MVP utilizable; **P1**, posterior al MVP; **P2**, expansión.

### Fuera del alcance inicial

- Reimplementar CSS completo o un navegador web.
- Crear un motor gráfico propio o un Virtual DOM genérico.
- Compatibilidad de sintaxis completa con Vue o Svelte.
- Implementar todos los widgets, módulos y plataformas de Qt desde la primera versión.
- Disponer de una plataforma visual de diseño, un marketplace o un ecosistema de plugins.
- Ofrecer garantía de ejecución segura para componentes Python de terceros no confiables.
- Incorporar o mantener bindings alternativos de Python para Qt. No forman parte de la hoja de ruta vigente.
- Desarrollar un runtime o backend propio en C++ antes de confirmar la adopción y las limitaciones reales del enfoque inicial.

## 3. Decisiones técnicas iniciales

| Área | Decisión provisional | Motivo o criterio de validación |
|---|---|---|
| Lenguaje de componentes | Sintaxis SFC propia, cercana a HTML/Svelte | Permite bloques de Python, markup y estilos con extensiones propias. |
| Extensión | `.janel` | Identificador provisional; revisar colisiones antes del lanzamiento. |
| Lenguaje de lógica | Python | Reutilizar librerías, modelos de datos y servicios existentes. |
| Motor gráfico | Qt Quick / QML | Conserva controles, modelos, composición visual y aceleración de Qt. |
| Binding Python único | PySide6 | Es el binding oficial de Qt para Python. Será la única integración soportada por el proyecto; no se planifica una capa de compatibilidad con otros bindings. |
| Implementación nativa futura | C++ es una hipótesis posterior, no parte del roadmap | Solo se investigará después de observar adopción externa y detectar una limitación medible que no se resuelva razonablemente con PySide6 y Qt Quick. |
| Compilación | SFC → AST → representación intermedia → QML + runtime Python | Facilita diagnósticos y separa sintaxis de backend. |
| Reactividad | `state`/`computed` + notificaciones Qt | Reducir a actualizaciones de propiedades afectadas. |
| Listas | Adaptador basado en modelos Qt cuando corresponda | Integración con `ListView`, `Repeater` y delegados. |
| Estilos | Subconjunto documentado de sintaxis CSS traducido a Qt Quick | Qt Quick no es un navegador y no implementa CSS general. |
| Distribución del framework | Paquete Python estándar, wheel y sdist publicados en PyPI | Permite `python -m pip install janelkit` sin clonar el repositorio ni copiar su código fuente. Nombre público provisional. |
| CLI | Ejecutable `janel` definido en `[project.scripts]` | Incluido al instalar la biblioteca; comienza con `janel new`, y se amplía con `janel dev` y `janel build`. |
| Entrada de las aplicaciones | `main.py` en la raíz + `src/App.janel` como componente raíz | Separa el arranque Python de la definición visual; `python main.py` es la ejecución canónica. |

### Restricciones que afectan al lenguaje

- El archivo **no será XML estricto**. Las directivas `{#if}`, las expresiones `{...}` y los bloques Python requieren un parser de SFC con reglas propias.
- El lenguaje debe especificar qué expresiones Python son válidas en templates. La primera versión aceptará un subconjunto definido y comunicará cuando una operación no se pueda enlazar.
- El código Python de los componentes se ejecutará como código del proyecto. No se anunciará aislamiento o seguridad de ejecución que no exista.
- Las actualizaciones visuales deberán respetar el hilo de interfaz de Qt. El trabajo asíncrono y los procesos largos necesitan una integración explícita.
- Un binding bidireccional no debe provocar bucles entre señal Qt y cambio de estado Python.
- La instancia de cada componente debe mantener su propio estado; compartir definiciones no debe implicar compartir el estado local.

## 4. Arquitectura propuesta

```text
                         ARCHIVO .janel
                ┌─────────────────────────┐
                │ <script>                │
                │ template                │
                │ <style>                 │
                └────────────┬────────────┘
                             │
                     COMPILADOR SFC
                             │
                ┌────────────▼────────────┐
                │ Parser + AST + errores  │
                └────────────┬────────────┘
                             │
                 REPRESENTACIÓN INTERMEDIA
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
          Generador QML             Runtime Python
         vista y componentes      estado, eventos, deps.
                 │                       │
                 └───────────┬───────────┘
                             ▼
                     PUENTE QObject/Qt
                             │
                             ▼
                        QT QUICK
```

### Módulos previstos

```text
janelkit/
├── compiler/
│   ├── sfc_parser.py          # Extrae script, plantilla y estilos
│   ├── template_parser.py     # Analiza elementos y directivas
│   ├── ast_nodes.py           # Nodos con información de origen
│   ├── validator.py           # Valida expresiones y estructuras
│   ├── ir.py                  # Representación intermedia
│   └── qml_generator.py       # Traduce componentes a QML
├── reactivity/
│   ├── state.py               # Estado observable
│   ├── computed.py            # Valores derivados
│   └── effects.py             # Dependencias y suscripciones
├── runtime/
│   ├── component.py           # Ciclo de vida de instancias
│   ├── qt_bridge.py           # Props, señales y eventos
│   ├── bindings.py            # Enlaces unidireccionales/bidireccionales
│   └── list_model.py          # Adaptador de colecciones a modelos Qt
├── styling/
│   ├── parser.py
│   └── compiler.py
├── cli/
│   ├── main.py              # Entry point del comando `janel`
│   └── scaffolding.py       # Generación de proyectos
├── templates/
│   └── starter/             # Archivos de plantilla incluidos en el wheel
└── qt_backend/
    ├── application.py
    └── controls.py
```

**Distinguir nombres:** `janelkit/cli/main.py` es código interno de la biblioteca para el comando `janel`; `mi-app/main.py` es el archivo que se genera en cada aplicación. No deben confundirse. Las plantillas deben distribuirse como recursos instalables del paquete (no depender de archivos sueltos del repositorio).

La estructura es orientativa. Los módulos se incorporarán cuando exista una necesidad comprobada, no todos en el primer commit.

### Contratos mínimos entre capas

- **Parser:** recibe texto y ubicación del archivo; devuelve AST tipado con rango de origen o diagnósticos.
- **Validador:** identifica directivas, propiedades, componentes y expresiones no soportadas antes de generar QML.
- **IR:** representa nodos, eventos, bindings y control de flujo sin mezclar los detalles de PySide6 con la gramática del lenguaje. Esta separación permite mantener el compilador comprensible; no implica comprometerse con otros bindings.
- **Generador:** produce QML y un mapa de origen que permite asociar fallos a líneas `.janel`.
- **Runtime:** crea una instancia Python por instancia visual, administra estado, comunica cambios y libera suscripciones al desmontar.
- **Backend Qt:** registra tipos, carga el resultado compilado y gestiona recursos y ciclo de vida de la aplicación.

## 5. Hoja de ruta incremental

> Regla de ejecución: ninguna etapa se considera terminada solo porque las clases estén implementadas. Debe existir una demostración ejecutable, pruebas y un criterio de aceptación observable.

### Incremento 0 — Validación técnica del enfoque

**Objetivo:** demostrar que Python puede actualizar una vista Qt Quick y recibir eventos sin escribir código QML dentro del componente de usuario.

**Trabajo:**

- [ ] Crear un proyecto de prueba con Python, PySide6 y Qt Quick, arrancado desde un `main.py` en su raíz.
- [ ] Exponer un objeto Python a QML mediante propiedades y notificaciones Qt.
- [ ] Implementar un contador con actualización de texto y clic de botón.
- [ ] Probar entrada de texto bidireccional sin bucles de actualización.
- [ ] Registrar restricciones observadas: tipos, señales, ciclo de vida y errores.

**Entregable:** `spikes/qt_bridge_counter/` con un contador real y una nota técnica de viabilidad.

**Criterio de salida:** el contador cambia visualmente al cambiar el estado Python; un clic modifica ese estado; escribir en un campo sincroniza el valor. No se requieren todavía archivos `.janel`.

### Incremento 1 — Formato SFC y compilador mínimo

**Objetivo:** leer un archivo `.janel` y obtener una estructura que represente fielmente su contenido.

**Trabajo:**

- [ ] Especificar las secciones permitidas y las reglas de apertura/cierre.
- [ ] Implementar extracción de `<script lang="python">`, plantilla y `<style>`.
- [ ] Construir un AST para elementos, texto, atributos y expresiones.
- [ ] Mantener línea y columna de cada nodo y atributo.
- [ ] Detectar componentes mal cerrados y expresiones inválidas.
- [ ] Crear pruebas unitarias del parser con casos correctos e incorrectos.

**Entregable:** comando interno `janel parse src/App.janel` que muestra un AST o errores útiles.

**Criterio de salida:** el parser interpreta una interfaz estática con elementos anidados; informa correctamente la ubicación de al menos los errores principales. No se pretende aún ejecutar Python ni mostrar ventanas.

### Incremento 2 — Primera interfaz compilada

**Objetivo:** transformar una plantilla estática en una ventana real de Qt Quick.

**Trabajo:**

- [ ] Definir IR básico y generador de QML.
- [ ] Mapear `Window`, `Column`, `Row`, `Text`, `Button` y `TextField`.
- [ ] Soportar propiedades literales, tamaños y contenido textual.
- [ ] Arrancar Qt Quick y cargar el resultado compilado desde una función pública `run()` invocada por `main.py`.
- [ ] Incorporar mensajes de error si Qt rechaza el QML generado.

**Entregable:** primera aplicación `.janel` que crea una ventana y muestra controles.

**Criterio de salida:** editar textos, jerarquía o tamaños en `App.janel` y recompilar produce cambios visibles, sin editar QML manualmente. Existe una primera versión de `janel new` que genera el proyecto con `main.py` y permite abrir la ventana mediante `python main.py`.

### Incremento 3 — Estado, interpolación y eventos

**Objetivo:** conseguir la primera interacción reactiva completa desde un SFC.

**Trabajo:**

- [ ] Crear `state(initial)` y definir la semántica de `.value` en Python.
- [ ] Definir cómo se desenvuelven estados y valores `computed` en plantillas.
- [ ] Conectar dependencias con propiedades notificables del puente Qt.
- [ ] Implementar interpolación `{expression}` sobre expresiones admitidas.
- [ ] Enlazar `on:click={handler}` con funciones Python del componente.
- [ ] Aplicar cambios solo a bindings afectados, sin recrear la ventana.
- [ ] Verificar liberación de listeners al destruir componentes.

**Entregable:** `examples/counter/App.janel`, sin QML escrito por el usuario.

**Criterio de salida:** cada clic modifica el número visible, los valores derivados se actualizan y dos instancias del contador mantienen estados independientes.

### Incremento 4 — Entrada de datos y control de flujo

**Objetivo:** desarrollar formularios y colecciones reactivas.

**Trabajo:**

- [ ] Implementar `bind:value` y control contra ciclos de escritura.
- [ ] Implementar `{#if}`, `{:else}` y `{/if}`.
- [ ] Implementar `{#each items as item (key)}` con clave estable.
- [ ] Diseñar reconciliación de elementos de lista o adaptación a modelos Qt.
- [ ] Implementar `@computed` con invalidación de dependencias.
- [ ] Probar inserción, edición, eliminación y reordenamiento de filas.

**Entregable:** `examples/todo/App.janel`, con lista editable, filtro y estado vacío.

**Criterio de salida:** escribir actualiza el estado, agregar/eliminar elementos actualiza la lista, los condicionales reaccionan y las claves mantienen correctamente la identidad de cada fila.

### Incremento 5 — Composición de componentes

**Objetivo:** dejar de construir aplicaciones como una sola pantalla monolítica.

**Trabajo:**

- [ ] Resolver imports de componentes `.janel`.
- [ ] Implementar paso de propiedades desde padre a hijo.
- [ ] Distinguir estado local de propiedades recibidas.
- [ ] Implementar eventos del hijo hacia el padre.
- [ ] Definir montaje, desmontaje y limpieza de recursos.
- [ ] Documentar nombres públicos y reglas de alcance de variables.

**Entregable:** aplicación de ejemplo con `App.janel`, `TodoList.janel` y `TodoItem.janel`.

**Criterio de salida:** reutilizar un componente en varios puntos sin mezclar estados; una acción del hijo puede comunicar un resultado al padre y el desmontaje no deja actualizaciones activas.

### Incremento 6 — Estilos y apariencia moderna (**cierre del MVP**)

**Objetivo:** permitir pantallas visualmente consistentes sin pedir al autor que escriba QML.

**Trabajo:**

- [ ] Definir las propiedades CSS-like soportadas y su equivalencia Qt.
- [ ] Implementar clases, estilos locales y reglas de precedencia sencillas.
- [ ] Soportar como mínimo colores, tipografía, espaciado, alineación, bordes y radios.
- [ ] Incorporar tokens de tema y dos temas de demostración (claro y oscuro).
- [ ] Construir un conjunto pequeño de controles base coherentes.
- [ ] Emitir errores o advertencias para propiedades no soportadas.

**Entregable:** una interfaz de notas o tareas con barra lateral, formulario y tarjetas, hecha únicamente con `.janel` y Python del proyecto.

**Criterio de salida:** el autor puede ajustar tipografía, espaciados, colores y estructura desde su SFC; la aplicación se representa correctamente en Qt Quick. El MVP no promete CSS completo.

### Incremento 7 — Experiencia de desarrollo

**Objetivo:** que trabajar en el framework sea cómodo durante cambios frecuentes. La **versión mínima de `janel new` y el arranque con `main.py` se implementan antes**, durante la creación del primer SFC ejecutable; aquí se perfeccionan y documentan.

**Trabajo:**

- [ ] Estabilizar `janel new`, `janel dev` y `janel build` como comandos públicos con ayuda `--help`, mensajes de error y pruebas de instalación.
- [ ] Mejorar la plantilla inicial: `main.py` en la raíz, `src/App.janel`, recursos, README, `.gitignore` y `pyproject.toml`.
- [ ] Añadir observación de archivos y recompilación automática.
- [ ] Implementar recarga completa de la vista en desarrollo como primera solución.
- [ ] Presentar diagnósticos con archivo, línea y columna.
- [ ] Diseñar soporte básico para resaltado de `.janel` en el editor.
- [ ] Evaluar posteriormente HMR con conservación selectiva del estado.

**Entregable:** proyecto generado desde CLI con ciclo editar → guardar → observar cambios; mantiene también la ejecución independiente mediante `python main.py`.

**Criterio de salida:** una modificación de texto o estilo se refleja sin reiniciar manualmente el comando de desarrollo; si el archivo contiene un error, el mensaje remite al código fuente `.janel`. Un proyecto generado puede arrancarse mediante `python main.py` sin depender de `janel dev`.

### Incremento 8 — Estabilidad, distribución y versión pública inicial

**Objetivo:** convertir el prototipo en un framework instalable y mantenible que terceros puedan probar.

**Trabajo:**

- [ ] Automatizar pruebas unitarias del parser, runtime y compilador.
- [ ] Añadir pruebas de integración con Qt y pruebas visuales representativas.
- [ ] Ejecutar una matriz de compatibilidad con versiones de Python/Qt fijadas.
- [ ] Validar Windows, Linux y macOS progresivamente según disponibilidad.
- [ ] Publicar paquetes Python `wheel` y `sdist` en TestPyPI y después en PyPI, sin publicar nombres hasta confirmar disponibilidad.
- [ ] Verificar `pip install` en un entorno virtual limpio y el comando `janel` expuesto mediante `project.scripts`.
- [ ] Verificar que los archivos de plantilla viajan dentro del wheel y `janel new` funciona fuera del repositorio.
- [ ] Definir por separado construcción de instaladores para aplicaciones de usuarios, recursos Qt y despliegue multiplataforma; instalar JanelKit con `pip` no produce por sí mismo un `.exe` o `.app`.
- [ ] Medir consumo, tiempos de inicio y actualizaciones de listas extensas.
- [ ] Documentar guía de inicio, componentes, directivas y limitaciones.
- [ ] Revisar licencias, distribución de Qt, dependencias y marca.
- [ ] Publicar al menos una aplicación demostrativa y un tutorial de inicio que puedan seguir personas ajenas al proyecto.
- [ ] Recoger problemas de instalación, comprensión de sintaxis y uso de componentes reportados por evaluadores externos.
- [ ] Comprobar el recorrido público completo: `pip install` → `janel new` → `python main.py` (y opcionalmente `janel dev`).

**Entregable:** primera versión preliminar instalable, ejemplos completos y registro de cambios.

**Criterio de salida:** en un entorno virtual limpio, se instala la biblioteca desde un artefacto publicado, `janel new ejemplo` crea una estructura válida con `main.py` en la raíz y `python main.py` abre la primera ventana. Las pruebas principales pasan; los problemas conocidos están registrados; y el MVP está disponible para evaluaciones externas.

### Incremento 9 — Validación comunitaria del producto

**Objetivo:** comprobar si el framework resuelve problemas reales de desarrolladores Python y frontend antes de ampliar su alcance técnico.

**Trabajo:**

- [ ] Publicar el repositorio, ejemplos reproducibles y una guía clara de las limitaciones actuales.
- [ ] Invitar a desarrolladores externos a construir una interfaz real, no solo ejecutar el ejemplo oficial.
- [ ] Observar dónde abandonan el tutorial, qué conceptos resultan confusos y qué API Qt necesitan exponer.
- [ ] Recoger incidencias, propuestas y aplicaciones desarrolladas sin intervención del equipo central.
- [ ] Medir, de forma consistente, la instalación completada, el tiempo hasta la primera ventana funcional, la finalización de una aplicación pequeña y la intención de seguir usándolo.
- [ ] Priorizar cambios a partir de problemas repetidos y reproducibles, no exclusivamente del número de estrellas o descargas.
- [ ] Redactar una revisión pública o interna con evidencias y una decisión de producto: continuar, cambiar la dirección o detener nuevas inversiones.

**Entregable:** informe breve de validación, lista priorizada de fricciones y decisión documentada sobre la siguiente versión.

**Criterio de salida:** varias personas ajenas al desarrollo han intentado crear aplicaciones con el framework; sus experiencias están registradas y las principales decisiones siguientes están justificadas por resultados observables. Si no hay suficientes participantes, se declara la evidencia insuficiente en vez de asumir que el producto está validado. **Completar este incremento no autoriza automáticamente una migración a C++**: esa decisión requiere un análisis técnico independiente.

## 6. Hitos de producto

| Hito | Incrementos | Evidencia verificable |
|---|---|---|
| H0 — Viabilidad | 0 | Contador nativo con puente Python ↔ Qt. |
| H1 — Primer SFC | 1–2 | Una ventana se genera desde `.janel` y arranca por `main.py`; existe un generador `janel new` mínimo. |
| H2 — Primera app reactiva | 3 | Contador SFC con eventos e interpolación. |
| H3 — Formularios y listas | 4 | App de tareas reactiva. |
| H4 — Componentes reutilizables | 5 | App dividida en componentes con propiedades y eventos. |
| **H5 — MVP de interfaz moderna** | **6** | **App demostrativa con temas y estilos locales.** |
| H6 — Flujo frontend | 7 | CLI pública estabilizada, plantilla completa y recarga al guardar. |
| H7 — Prelanzamiento | 8 | Wheel/sdist publicados y probados con `pip install` → `janel new` → `python main.py`; documentación, tests y evaluadores externos. |
| H8 — Validación comunitaria | 9 | Uso externo documentado y decisión fundamentada de continuar, ajustar o detener. |

Los hitos **no tienen fechas inventadas**. El siguiente incremento comienza cuando el anterior cumple sus criterios de salida y sus problemas críticos están resueltos. La validación comunitaria no se define por una cifra arbitraria de popularidad: requiere observar uso independiente y utilidad reiterada.

## 7. Especificación mínima del MVP

El MVP debe permitir, mediante archivos `.janel`, construir una aplicación de tareas con:

1. Ventana, layouts, textos, botones y campos de entrada.
2. Estado local, interpolaciones, eventos y valores derivados.
3. Binding bidireccional para entradas de texto.
4. Condiciones y listas identificadas por claves.
5. Componentes anidados con propiedades y eventos.
6. Estilos locales, tema claro/oscuro y espaciado configurable.
7. Integración con módulos Python externos para lógica no visual.
8. Mensajes de error que apunten al archivo de origen.

### Pruebas de aceptación de extremo a extremo

- [ ] Al pulsar «Agregar», aparece un elemento sin reconstruir toda la ventana.
- [ ] Al modificar la consulta, la lista filtrada se actualiza.
- [ ] Al borrar una tarea, no se intercambia el estado local de otras filas.
- [ ] Al desmontar una tarjeta, deja de recibir notificaciones reactivas.
- [ ] Al cambiar un tema, los colores y tipografías definidos por tokens cambian.
- [ ] Al introducir una directiva mal formada, se indica el archivo y la línea.
- [ ] La aplicación inicia sin que el proyecto usuario contenga archivos QML escritos a mano.

## 8. Estrategia de implementación y pruebas

### Orden de trabajo dentro de cada incremento

1. Escribir un ejemplo de uso que el desarrollador querría conseguir.
2. Definir el contrato observable y los casos que deben fallar.
3. Implementar el camino completo más pequeño, del SFC a la interfaz.
4. Añadir pruebas de parser, compilación e integración pertinentes.
5. Ejecutar la aplicación de ejemplo y registrar limitaciones.
6. Actualizar la documentación antes de cerrar el incremento.

### Tipos de pruebas

| Prueba | Qué valida |
|---|---|
| Parser (unitaria) | Estructura de secciones, expresiones y ubicación de errores. |
| Compilador (snapshot/estructura) | IR y QML esperado para componentes pequeños. |
| Reactividad (unitaria) | Dependencias, invalidación, independencia y limpieza. |
| Integración Qt | Propiedades, eventos, modelos y ciclo de vida. |
| Funcional de aplicación | Flujos completos de contador, formulario y lista. |
| Visual | Regresiones perceptibles de controles y estilos. |
| Rendimiento | Cambios incrementales y comportamiento con listas grandes. |

Las pruebas visuales deben considerar diferencias de plataforma, tipografías y escalado; no se usarán capturas idénticas como único criterio de corrección.

## 9. Riesgos principales y mitigaciones

| Riesgo | Consecuencia | Mitigación inicial |
|---|---|---|
| Traducir arbitrariamente expresiones Python a QML | Semántica inconsistente y errores difíciles de explicar | Evaluar expresiones admitidas en el runtime Python; publicar un subconjunto definido y dependencias explícitas. |
| Sincronización Python ↔ QML | Actualizaciones perdidas o ciclos de eventos | Prototipo del puente antes del compilador; pruebas de ida/vuelta y notificaciones. |
| Listas dinámicas | Pérdida de identidad visual o mal rendimiento | Claves obligatorias en listas mutables y adaptación progresiva a modelos Qt. |
| Estilos CSS-like | Expectativas incompatibles con Qt Quick | Tabla pública de propiedades soportadas; errores claros para lo demás. |
| Dependencia operativa de PySide6 | Cambios de versión, límites de interoperabilidad o de empaquetado | Fijar versiones compatibles, encapsular el puente Qt y probar actualizaciones antes de adoptarlas; no mantener un segundo binding. |
| Recarga del script Python | Estado duplicado, objetos vivos o memoria retenida | Comenzar con recarga completa; HMR selectivo solo tras pruebas de ciclo de vida. |
| Distribución multiplataforma | Paquetes que funcionan solo en el equipo de desarrollo | Probar recursos y empaquetado desde ejemplos pequeños, no al final. |
| Publicar un wheel incompleto | El CLI se instala, pero `janel new` no encuentra las plantillas | Incluir recursos en el paquete y probar la instalación desde un wheel fuera del árbol fuente. |
| Confundir instalación del framework con empaquetado de aplicaciones | Usuarios esperan un ejecutable de escritorio al instalar la biblioteca | Distinguir `pip install janelkit`, `python main.py` y una futura herramienta para crear instaladores. |
| Colisión de nombre en PyPI o comando `janel` | Imposibilidad de publicar con el nombre inicialmente previsto | Verificar disponibilidad y conflictos antes de registrar el paquete; mantener los nombres como provisionales. |
| Ambición de cubrir todo Qt | Retrasa indefinidamente un producto utilizable | Priorizar componentes frecuentes y habilitar extensiones específicas. |
| Migración prematura a C++ | Aumenta complejidad del build, depuración y mantenimiento sin demostrar un beneficio real | Posponer C++ hasta disponer de perfiles de rendimiento, casos de uso repetidos y adopción suficiente. |
| Confundir interés inicial con adopción | Orientar el roadmap por opiniones en lugar de uso real | Seguir aplicaciones creadas, tareas completadas y problemas de usuarios externos; documentar también los intentos fallidos. |
| Código no confiable | Ejecución arbitraria al importar/ejecutar scripts | Tratar componentes y dependencias como código confiable; no prometer sandbox. |

## 10. Registro de decisiones pendientes

Estas preguntas **no bloquean el Incremento 0**, pero deben cerrarse antes de declarar estable el lenguaje:

- [ ] **Nombre y extensión definitivos:** revisar conflictos técnicos y legales.
- [ ] **Gramática formal:** establecer si el markup admite una única raíz o fragmentos.
- [ ] **Semántica de reactividad:** seguimiento automático de lecturas, declaración estática de dependencias o combinación controlada.
- [ ] **Expresiones en templates:** decidir operaciones admitidas, errores y representación de valores `state`.
- [ ] **Importación de componentes:** imports Python, imports específicos de markup o ambas opciones.
- [ ] **Estado y props:** mutabilidad, defaults, validación y eventos personalizados.
- [ ] **Estilos:** lista exacta de propiedades y estrategia de encapsulación.
- [ ] **Qt avanzado:** establecer una vía de escape para componentes personalizados QML y APIs nativas.
- [ ] **Validación comunitaria:** definir cómo solicitar pruebas externas, recoger consentimientos cuando corresponda y registrar resultados sin recopilar telemetría innecesaria.
- [ ] **Umbral para estudiar C++:** determinar qué limitación medible, si aparece, justificaría un prototipo nativo y cómo compararlo con el runtime PySide6.
- [ ] **Versión base:** fijar versiones mínimas de Python, Qt y PySide6 tras el prototipo.
- [ ] **Licencia del proyecto:** seleccionar una licencia compatible con dependencias y distribución prevista.
- [ ] **Identidad de publicación:** verificar en PyPI y otros índices el nombre de distribución, módulo importable y ejecutable CLI antes de consolidarlos.
- [ ] **Política de versiones y releases:** fijar versionado, compatibilidad de Python/PySide6, publicación automatizada y procedimiento de recuperación ante versiones defectuosas.
- [ ] **Contrato de `run()`:** definir cómo se resuelven rutas, errores de compilación, cierre de Qt y argumentos de aplicación.
- [ ] **Formato de proyecto generado:** distinguir dependencias del framework de las dependencias de una aplicación y decidir cómo fijar versiones en la plantilla.

## 11. Primer backlog ejecutable

Para comenzar, crear un repositorio con esta secuencia de entregas pequeñas:

- [ ] **PR-001:** esqueleto instalable de la biblioteca (`pyproject.toml`, estructura `src/janelkit/` o equivalente, tests y declaración de `project.scripts` para `janel`).
- [ ] **PR-002:** aplicación Qt Quick mínima con ventana y botón, iniciada desde `main.py`.
- [ ] **PR-003:** `QObject` con valor observable, señal de cambio y manejador de clic.
- [ ] **PR-004:** campo editable que sincroniza valor entre Qt y Python, sin bucles.
- [ ] **PR-005:** documentación de hallazgos del puente; decisión de continuar o replantear.
- [ ] **PR-006:** extractor de secciones `.janel` con pruebas y localizaciones de error.
- [ ] **PR-007:** parser de elementos anidados y atributos estáticos.
- [ ] **PR-008:** generación de una ventana QML a partir de `App.janel` y API `run()`.
- [ ] **PR-009:** `janel new <nombre>` mínimo que genere `main.py`, `src/App.janel` y metadatos del proyecto; prueba de arranque desde una carpeta nueva.
- [ ] **PR-010:** construir un wheel de desarrollo e instalarlo en un entorno limpio para verificar que `janel` y sus plantillas están disponibles sin acceso al repositorio fuente.

**Primera demostración que vale la pena enseñar:** tras instalar el paquete localmente, `janel new ejemplo` crea un proyecto con `main.py`; al ejecutar `python main.py`, `App.janel` abre una ventana moderna con un contador reactivo y un campo de texto. Hasta llegar ahí, no es necesario construir CLI avanzada, sistema CSS completo ni biblioteca extensa de componentes.

## 12. Definición de terminado

Una tarea se considera terminada cuando:

- Tiene una funcionalidad observable y una prueba asociada.
- No rompe los ejemplos de los incrementos anteriores.
- Los errores conocidos están registrados y son reproducibles.
- Las limitaciones están documentadas sin prometer soporte inexistente.
- El código respeta los contratos entre parser, compilador, runtime y backend.

El proyecto debe revisarse al finalizar cada hito. Si el puente reactivo o el coste de generación QML revelan limitaciones importantes, es preferible modificar la arquitectura antes de ampliar el lenguaje. La prioridad tras la versión preliminar es la adopción comprobable, no una reescritura tecnológica.

## 13. Decisión de plataforma y evaluación eventual de C++

### Decisión vigente (ADR-001)

- **Qt 6 / Qt Quick** constituye la plataforma visual y de ejecución.
- **PySide6** es el único binding de Python admitido en el alcance actual. El framework, las pruebas, los ejemplos y la documentación utilizarán exclusivamente PySide6.
- El compilador `.janel` generará QML y se apoyará en un runtime Python integrado con Qt mediante PySide6.
- No se desarrollará un segundo binding ni una capa genérica de compatibilidad entre bindings. Separar compilador y backend sigue siendo útil para el mantenimiento, no una promesa de múltiples implementaciones.
- **Prioridad de producto:** publicar un MVP usable, aprender de proyectos desarrollados por terceros y comprobar si la comunidad encuentra valor en la experiencia SFC antes de reconsiderar la implementación interna.

### C++ es una posibilidad, no una etapa comprometida

La evolución hacia C++ se considerará **solo después de la validación comunitaria** y si aparece una limitación técnica reproducible. Incluso en ese caso, la primera opción será evaluar si un componente nativo acotado resuelve el problema; reescribir todo el runtime sería una decisión distinta y mucho más costosa.

Para justificar la evaluación deben cumplirse estas condiciones:

1. Existen desarrolladores externos que utilizan el framework en proyectos o prototipos propios y reportan necesidades consistentes.
2. Se identifica una limitación medible del enfoque PySide6/Qt Quick —por ejemplo, latencia de un caso concreto, coste de memoria o interoperabilidad— y se reproduce con una prueba representativa.
3. Se han probado alternativas más simples, como mejorar el compilador, el modelo de actualización, la estructura de datos o el uso de API Qt ya disponibles.
4. Un prototipo limitado en C++ muestra una mejora relevante y se documenta el coste adicional de empaquetado, mantenimiento y compatibilidad.

**Decisión por defecto:** continuar con PySide6. El éxito del producto no requiere ni presupone una migración a C++. Una evaluación futura de C++ no implica necesariamente reemplazar Python: podría limitarse a extensiones o a un componente interno identificado mediante perfiles.

### Puertas de decisión

| Momento | Decisión permitida | Decisión que se pospone |
|---|---|---|
| Prototipo y MVP (incrementos 0–6) | Mejorar el lenguaje, el compilador y el runtime sobre PySide6. | Investigar una sustitución general por C++. |
| Herramientas y primera versión pública (7–8) | Resolver instalación, ergonomía, compatibilidad y errores de uso reales. | Iniciar una reescritura por preferencia tecnológica. |
| Validación comunitaria (9) | Evaluar continuidad del proyecto y necesidades reiteradas de usuarios externos. | Suponer que adoptar C++ es el siguiente paso obligatorio. |
| Solo después de validar el producto | Si existen métricas y un cuello de botella reproducible, comparar alternativas y, si procede, hacer un prototipo C++ acotado. | Comprometer una migración completa sin evidencia técnica. |

## 14. Distribución pública, CLI y contrato de arranque

### 14.1 Biblioteca distribuida mediante `pip`

JanelKit será un **paquete Python reutilizable**, publicado con artefactos estándar (`wheel` y `sdist`) en **PyPI**. Su código estará disponible en un repositorio público, con documentación, ejemplos, pruebas y versiones etiquetadas. El medio principal de instalación de la biblioteca será:

```bash
python -m pip install janelkit
```

**Estado:** comando objetivo para cuando exista una publicación válida. `janelkit` es un nombre provisional y la versión **0.1 de este documento no es una versión publicada del paquete**. Antes del lanzamiento hay que comprobar disponibilidad del nombre, licencias y requisitos de Python/Qt/PySide6. También puede ofrecerse un enlace a cada release del repositorio, pero no se crearán instalaciones incompatibles entre sí.

Durante el desarrollo interno, el equipo podrá instalar el framework desde el repositorio:

```bash
python -m pip install -e .
```

El `pyproject.toml` del **repositorio de la biblioteca** definirá metadatos, dependencias, recursos de plantilla y un punto de entrada de consola equivalente a:

```toml
[project.scripts]
janel = "janelkit.cli.main:main"
```

Ese fragmento define la intención del paquete, no una implementación disponible. En particular, `janelkit.cli.main:main` deberá existir y devolver un código de salida apropiado. Los archivos necesarios para generar proyectos deben quedar incluidos en el wheel y en el sdist.

### 14.2 Comando generador de proyectos

`janel new nombre-proyecto` será una capacidad temprana: su versión mínima se desarrollará **junto al primer SFC ejecutable (incrementos 1–2)**, en lugar de esperar al incremento 7. La implementación podrá empezar como un comando sencillo y crecer después.

Contrato básico:

- Acepta un nombre de proyecto y opcionalmente una ruta de destino.
- Crea una carpeta con `main.py` **en su raíz**, `src/App.janel` y los metadatos mínimos.
- Copia las plantillas desde recursos instalados con la biblioteca, no desde rutas relativas al repositorio de JanelKit.
- Si el directorio de destino ya contiene archivos, no los sobrescribe silenciosamente; indica el conflicto.
- Presenta al finalizar instrucciones reproducibles para abrir el proyecto, instalar dependencias cuando corresponda y ejecutar `python main.py`.
- Se prueba mediante un proyecto temporal que se genera y se ejecuta desde fuera del repositorio fuente.

La distribución del framework y la generación del proyecto son operaciones diferentes: **`pip` instala la herramienta; `janel new` crea una aplicación que utiliza esa herramienta**.

### 14.3 Punto de entrada único de cada aplicación

Se establece como convención que todo proyecto generado tenga:

```text
mi-app/main.py         # Inicio de la aplicación, siempre en la raíz
mi-app/src/App.janel    # Raíz visual de la aplicación
```

`main.py` será Python ordinario y permanecerá editable por el desarrollador para cargar configuración, definir recursos, registrar servicios o personalizar el arranque. El mínimo generado utilizará una API pública estable cuando se implemente:

```python
from pathlib import Path
from janelkit import run

if __name__ == "__main__":
    run(Path(__file__).parent / "src" / "App.janel")
```

El contrato de `run()` incluye inicializar Qt con PySide6, compilar o cargar `App.janel`, informar de los errores con referencia al SFC y ejecutar el ciclo de eventos; no debe crear múltiples aplicaciones Qt en el mismo proceso. El componente visual de arranque no contiene una segunda función `main()` obligatoria. El usuario podrá iniciar siempre mediante `python main.py`, con o sin CLI de desarrollo.

### 14.4 Comandos previstos y orden incremental

| Momento | Comando | Responsabilidad |
|---|---|---|
| Paquete instalable local (incremento 0–1) | `python -m pip install -e .` | Probar instalación del framework durante el desarrollo. |
| Primer SFC ejecutable (incrementos 1–2) | `janel new mi-app` | Crear proyecto y `main.py`; se implementa en una versión mínima y se puede ampliar. |
| Desde el primer ejemplo Qt y todos los proyectos generados | `python main.py` | Punto de entrada **canónico**, independiente del CLI. |
| Experiencia de desarrollo (incremento 7) | `janel dev` | Observar cambios, recompilar y recargar durante el desarrollo. |
| Distribución de aplicaciones (incrementos 7–8, según viabilidad) | `janel build` | Preparar salida compilada y, cuando esté resuelto, apoyar el empaquetado de aplicaciones. Su alcance exacto se documentará; no se prometerán ejecutables autónomos prematuramente. |
| Primera publicación (incremento 8) | `python -m pip install janelkit` | Instalar la versión pública del framework desde PyPI. |

### 14.5 Publicación y prueba de instalación limpia

Se publicará primero una distribución de prueba y, cuando el recorrido esté verificado, una versión preliminar en PyPI. Antes de cada publicación se comprobará que:

1. El wheel y el sdist incluyen runtime, compilador y recursos de plantillas.
2. Un entorno virtual nuevo instala el paquete con las dependencias declaradas y sin importar archivos desde el checkout original.
3. El comando `janel --help` se ejecuta después de instalar.
4. `janel new demo` crea `demo/main.py` y `demo/src/App.janel`.
5. Desde `demo/`, `python main.py` inicia la aplicación y abre una ventana de Qt Quick.
6. El ejemplo documentado funciona en los sistemas operativos comprobados y registra explícitamente los que aún no se han probado.

**Distinción de producto:** instalar la biblioteca por `pip` no genera automáticamente un ejecutable empaquetado de una aplicación. Las distribuciones `.exe`, `.app` o equivalentes pertenecen al despliegue de cada aplicación y serán una función posterior, con requisitos propios.

## 15. Referencias técnicas de partida

- [Svelte: archivos de componente `.svelte`](https://svelte.dev/docs/svelte/svelte-files) — referencia para estructura SFC.
- [Qt for Python: QML Application Tutorial](https://doc.qt.io/qtforpython-6/tutorials/qmlapp/qmlapplication.html) — punto de partida para integrar Python y Qt Quick.
- [Qt Quick: Models and Views](https://doc.qt.io/qt-6/qtquick-modelviewsdata-modelview.html) — base para la representación de listas.
- [Qt Quick Controls: Customizing Controls](https://doc.qt.io/qt-6/qtquickcontrols-customize.html) — personalización visual sin escribir un motor gráfico nuevo.
- [Qt for Python: deployment](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) — referencia para distribución, a validar en una etapa posterior.
- [Python Packaging User Guide](https://packaging.python.org/) — referencia sobre paquetes instalables, metadatos y publicación.
- [PyPA: Creating and discovering plugins / entry points](https://packaging.python.org/en/latest/specifications/entry-points/) — referencia del punto de entrada de consola que expone `janel`.

---

**Siguiente acción recomendada:** ejecutar el **Incremento 0** en un proyecto iniciado mediante `main.py` y crear desde el primer commit una biblioteca instalable en modo editable. Al completar los incrementos 1–2, entregar `janel new` mínimo y la API `run()`; así el primer SFC podrá comprobarse ejecutando `python main.py` dentro de un proyecto recién generado.
