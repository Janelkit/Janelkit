# Reto 2: hoja de cálculo

Hoja de cálculo de 10 000 × 26 hecha con la API pública de JanelKit. Forma parte de los retos de [docs/challenges_to_test.md](../../../docs/challenges_to_test.md); lo que se aprendió está en [HALLAZGOS.md](HALLAZGOS.md).

## Ejecutar

```bash
python main.py                                # hoja vacía
HOJA_FILE=datos.csv python main.py            # abre un CSV (separado por comas, punto y coma o tabuladores)
HOJA_DEMO=10000x26 python main.py             # datos generados, sin archivo
```

Mediciones (CSV generado de 10 000 × 26, sin ventana):

```bash
python bench.py
```

## Qué hace

- **Fórmulas** que se recalculan solas: `=A1+B2*2`, `=(A1-1)^2`, `=SUMA(A1:A100)`, `=PROMEDIO(B1:B10; 3)`, `MIN`, `MAX`, `CONTAR` (también en inglés: `SUM`, `AVERAGE`, `COUNT`). Errores `#DIV/0!`, `#VALOR!`, `#REF!`, `#NOMBRE?`, `#ERROR!` y `#CICLO!` para las referencias circulares. Los números admiten coma o punto decimal.
- **Teclado:** flechas, Tab, Intro (con Mayús, hacia atrás), AvPág/RePág, Inicio/Fin, Ctrl+flecha (al borde de los datos), Ctrl+Inicio/Fin, Mayús para seleccionar, Ctrl+A, Supr. Escribir empieza a editar; F2 o doble clic editan lo que hay; en el editor, Intro y Tab confirman y Escape cancela.
- **Ratón:** clic, Mayús+clic, arrastrar para seleccionar, clic en la cabecera de una columna, Mayús+rueda para las columnas.
- **Portapapeles:** Ctrl+C, Ctrl+X y Ctrl+V con texto separado por tabuladores, compatible con Excel y LibreOffice.
- **Deshacer y rehacer** (Ctrl+Z, Ctrl+Y o Ctrl+Mayús+Z, o los botones) de ediciones, borrados, pegados y ordenaciones.
- **Congelar** la fila 1 y la columna A; **ordenar** por la columna activa (las vacías al final; con la fila 1 congelada, no se mueve).
- **Barra de fórmulas** con la celda activa, y suma, promedio y recuento de la selección.
- **CSV:** abrir y guardar con el mismo separador.

Limitaciones de la aplicación (no del framework): al copiar o mover fórmulas sus referencias no se ajustan, las columnas tienen todas el mismo ancho y no hay formatos de número.

## Archivos

| Archivo | Contenido |
|---|---|
| `src/App.janel` | La ventana: barra, barra de fórmulas, cabecera de columnas, filas (`<List>`), resumen; teclado y portapapeles. |
| `src/components/Fila.janel` | Una fila: número y celdas visibles (un `<Text>` cada una), puntero y editor. |
| `src/components/Editor.janel` | El campo que edita una celda en el sitio. |
| `src/services/hoja.py` | Lo escrito, celdas reactivas perezosas, deshacer/rehacer, portapapeles, ordenar y CSV. |
| `src/services/formulas.py` | Analizador y evaluador de fórmulas. |
| `src/services/vista.py` | Celda activa, selección, columnas visibles, celdas congeladas, edición y teclado. |
| `bench.py` | Mediciones. |

Las pruebas están en [`apps/challenges/tests/test_challenge_hoja.py`](../tests/test_challenge_hoja.py).
