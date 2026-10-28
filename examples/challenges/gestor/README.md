# Reto 6: gestor de proyectos

Gestor de proyectos para un equipo pequeño, todo local, hecho con la API pública de JanelKit a partir del tablero del reto 3 (Kanban). Forma parte de los retos de [docs/challenges_to_test.md](../../../docs/challenges_to_test.md); lo que se aprendió está en [HALLAZGOS.md](HALLAZGOS.md).

## Ejecutar

```bash
python main.py                                   # datos.json junto a la app (si no existe: ejemplo + el tablero.json del reto 3)
GESTOR_FILE=mis_datos.json python main.py        # otro archivo
GESTOR_DEMO=10x4x50x300 python main.py           # 10 proyectos × 4 columnas × 50 tarjetas y 300 personas, sin archivo
```

Mediciones (por defecto, los tamaños de «Hecho cuando»):

```bash
python bench.py
python bench.py --proyectos 20 --tarjetas 100 --personas 1000
```

## Qué hace

Tres **secciones** en la cabecera de la ventana (Ctrl+1, Ctrl+2, Ctrl+3), cada una con su propia pila de páginas. Cambiar de sección conserva lo que había en cada una: la búsqueda, el proyecto abierto, el desplazamiento. Debajo, cada página tiene su propia cabecera (título, resumen y acciones; en un proyecto, también «← Proyectos» y las pestañas). Deshacer y rehacer están a la derecha de la cabecera de la ventana.

- **Proyectos:** una rejilla con el color, el nº de tarjetas, el progreso (las tarjetas de la última columna) y los miembros de cada proyecto. Se puede buscar, ver los archivados y crear uno nuevo. Al abrir un proyecto se apila su página (Alt+←, el botón «atrás» del ratón o «← Proyectos» vuelven).
  - **Tablero:** el del reto 3, con las etiquetas y los miembros del proyecto: arrastrar, menú contextual, detalle, filtros. El responsable se elige entre los miembros. Las columnas ocupan el alto de la ventana y el tablero se desplaza a lo ancho. Una columna nueva («+ Columna» o el hueco «+ Añadir columna» del final) empieza con su nombre en edición.
  - **Miembros:** una tabla con su rol y sus tarjetas; al lado, añadir personas y el reparto por rol. Si quien se quita tiene tarjetas en el proyecto, se avisa y se quedan sin responsable.
  - **Ajustes:** nombre, color y descripción (un borrador), un resumen del proyecto, y archivar o borrar (con confirmación).
  - Las pestañas usan `{#hidden}`: al cambiar de una a otra se conservan los filtros y el detalle abierto.
- **Personas:** el directorio en una tabla, con búsqueda por nombre o correo y cuántas tarjetas tiene cada una. La ficha de una persona edita sus datos, lista sus tarjetas en todos los proyectos (abrir una lleva a su tablero) y la da de baja con aviso de cuántas tarjetas tiene.
- **Mi trabajo:** las tarjetas de una persona en todos los proyectos activos, por proyecto o por fecha. Abrir una cambia a la sección Proyectos, abre su tablero y la enfoca. Si el proyecto ya estaba abierto, solo la enfoca.
- **Salir con cambios sin guardar** (el detalle de una tarjeta, los ajustes del proyecto o la ficha de una persona) pregunta antes, también al cerrar la ventana con la X (`before_leave`).
- Las tarjetas guardan el **id** de su responsable: renombrar a una persona se ve al momento en todos los proyectos.
- Un solo **historial de deshacer** para todo (Ctrl+Z, Ctrl+Y o los botones de la barra), que dice qué se desharía y en qué proyecto. Se guarda en JSON 300 ms después de cada ráfaga de cambios.

Del plan del reto quedan sin hacer la pestaña Lista (tabla ordenable y editable), las etiquetas y columnas en Ajustes del proyecto, exportar, los ajustes generales y abrir un proyecto en otra ventana (ver [HALLAZGOS.md](HALLAZGOS.md#lo-que-queda-del-plan)).

## Archivos

| Archivo | Contenido |
|---|---|
| `src/App.janel` | La ventana: cabecera con las secciones, `sections(...)`, deshacer y el enlace a una tarjeta desde cualquier sección. |
| `src/vistas/Proyectos.janel` | Inicio de la sección Proyectos: la rejilla. |
| `src/vistas/Proyecto.janel` | Un proyecto: cabecera, pestañas con `{#hidden}`, tablero, detalle y menú contextual. |
| `src/vistas/Personas.janel`, `Persona.janel` | El directorio y la ficha de una persona. |
| `src/vistas/MiTrabajo.janel` | Las tarjetas de una persona en todos los proyectos. |
| `src/components/Miembros.janel`, `AjustesProyecto.janel` | Las pestañas Miembros y Ajustes. |
| `src/components/Columna.janel`, `Tarjeta.janel`, `Detalle.janel`, `MenuContextual.janel` | El tablero del reto 3, adaptado a etiquetas y miembros por proyecto. |
| `src/services/datos.py` | Proyectos, personas, el historial común, el archivo, importar el reto 3 y los datos de ejemplo. |
| `src/services/tablero.py` | Las operaciones del tablero de un proyecto (con su inversa, sobre el historial común). |
| `src/services/interfaz.py` | Estado de un proyecto abierto: detalle, menú, tarjeta que enfocar y filtro. |
| `bench.py` | Mediciones. |

Las pruebas están en [`tests/test_challenge_gestor.py`](../../../tests/test_challenge_gestor.py).
