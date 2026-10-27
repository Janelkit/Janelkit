# Catálogo de `<flex>`

Elementos construidos solo con `.flux` sobre `<flex>`, el elemento base de las cajas ([docs/flex.md](../../docs/flex.md)). Cada fase del diseño añade aquí los elementos que la validan; hoy, la fase 1 (caja y disposición):

| Elemento | Archivo | Qué demuestra |
|---|---|---|
| Rejilla de tarjetas | `src/App.flux` (`.rejilla`, `.celda`) | `flex-wrap`, `flex: 1 1 200px`, `gap`: pasa de 4 a 2 y a 1 columna al estrechar la ventana, sin código Python |
| Tarjeta | `src/components/Tarjeta.flux` | columna, `margin-left: auto` (la etiqueta a la derecha), radio distinto por esquina |
| Barra de herramientas | `src/components/Barra.flux` | `justify-content: space-between`, grupos con `border-left` por lado, salto de línea al estrechar |

```bash
python main.py
python bench.py              # mediciones: montar y redimensionar 200 tarjetas
python bench.py --cards 500
```

Pruebas: `tests/test_example_flex.py` (el catálogo) y `tests/test_flex_qt.py` (el motor).
