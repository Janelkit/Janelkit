# Ejemplos

Aplicaciones pequeñas, una por tema. Cada una se ejecuta con `python apps/examples/<nombre>/main.py` desde la raíz del repositorio. Lo que necesitan además de JanelKit está en [`apps/requirements.txt`](../requirements.txt).

| Ejemplo | Muestra |
|---|---|
| `counter` | estado, `computed`, eventos, `{#if}` |
| `todo` | lista con claves, filtro, búsqueda, estado vacío |
| `todo-components` | la misma app dividida en `TodoList` y `TodoItem` con props y eventos |
| `notes` | barra lateral, formulario, tarjetas, `class:`, `{#key}` y cambio de tema |
| `books` | búsqueda en una API real sin bloquear la ventana: `@task`, `background`, cargando y errores |
| `compra` | la aplicación del [tutorial](../../docs/tutorial.md): componentes, slot, guardado en segundo plano y pruebas |
| `idiomas` | cambio de idioma en caliente, plurales, formatos según el idioma y árabe (derecha a izquierda), con `janelkit-i18n` |
| `files` | explorador de archivos: `<list>` virtualizada, slots, `provide`/`inject`, `ref`, atajos, diálogos (`janelkit-desktop`) y vista previa en segundo plano |
| `preferencias` | lo que se recuerda al cerrar: `persisted` (`janelkit-store`) |
| `carrito` | datos compartidos por dos ventanas: un store estricto, `use()` y el registro de cambios (`janelkit-store`) |
| `flex` | un catálogo de elementos hechos solo con `<flex>` y estilos: rejilla, menú, tabla, pestañas, diálogo ([README](flex/README.md)) |
| `video` | `<video>` con `Frames`: una escena que se mueve, un modelo en segundo plano, cajas con clic sobre la imagen y puntos marcados en sus píxeles (necesita numpy) |

Las aplicaciones grandes, que ponen a prueba el framework, están en [`apps/challenges`](../challenges).
