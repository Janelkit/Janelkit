# Reto 3: tablero Kanban

Tablero de tareas hecho con la API pública de JanelKit. Forma parte de los retos de [docs/challenges_to_test.md](../../../docs/challenges_to_test.md); lo que se aprendió está en [HALLAZGOS.md](HALLAZGOS.md).

## Ejecutar

```bash
python main.py                                   # tablero.json junto a la app (si no existe, empieza con un ejemplo)
KANBAN_FILE=mi_tablero.json python main.py       # otro archivo
KANBAN_DEMO=20x200 python main.py                # 20 columnas × 200 tarjetas generadas, sin archivo
```

Mediciones (20 × 200 por defecto, sin ventana):

```bash
python bench.py
python bench.py --cols 4 --cards 200
```

## Qué hace

- Columnas con tarjetas que se **arrastran** entre columnas y dentro de una (se colocan delante de la tarjeta sobre la que se sueltan, o al final si se sueltan en el hueco). Cada columna es una `<List animate>`: las tarjetas se recolocan con animación y solo se crean las que se ven. Cerca del borde, la columna o el tablero se desplazan solos.
- Tarjetas con etiquetas de colores, responsable, fecha y una descripción que se despliega (estado local de la tarjeta, que se conserva al moverla, también a otra columna).
- **Doble clic** (o Intro) abre el detalle para editar título, descripción, responsable, fecha y etiquetas; «Guardar» (Ctrl+Intro) lo aplica como un solo cambio.
- **Clic derecho** (o Mayús+F10) abre el menú: mover a otra columna, abrir, duplicar, borrar. Todo tiene su tecla: Alt+←/→ (otra columna), Alt+↑/↓ (subir o bajar), Ctrl+D, Supr, Intro.
- Columnas: añadir, renombrar (doble clic en el nombre), borrar y reordenar (arrastrando la cabecera).
- Búsqueda y filtros por etiqueta y por persona: las tarjetas que no coinciden se atenúan.
- Todo se puede **deshacer y rehacer** (Ctrl+Z, Ctrl+Y o Ctrl+Mayús+Z, o los botones de la barra) y se guarda en JSON 300 ms después de cada ráfaga de cambios.

## Archivos

| Archivo | Contenido |
|---|---|
| `src/App.janel` | La ventana: barra (búsqueda, filtros, deshacer), tablero, detalle y menú contextual. |
| `src/components/Columna.janel` | Una columna: cabecera arrastrable y renombrable, `<List animate>` de tarjetas, «Añadir tarjeta». |
| `src/components/Tarjeta.janel` | Una tarjeta: arrastre, destino de otras tarjetas, teclas y descripción desplegable. |
| `src/components/Detalle.janel` | Panel de detalle con borrador y «Guardar». |
| `src/components/MenuContextual.janel` | Menú hecho con `<flex>` (foco, flechas, Escape, clic fuera). |
| `src/services/tablero.py` | Columnas y tarjetas, operaciones con su inversa (deshacer/rehacer), JSON y datos de ejemplo. |
| `src/services/interfaz.py` | Estado compartido de la ventana: detalle, menú, foco pendiente y filtro. |
| `bench.py` | Mediciones con 20 × 200. |

Las pruebas están en [`apps/challenges/tests/test_challenge_kanban.py`](../tests/test_challenge_kanban.py).
