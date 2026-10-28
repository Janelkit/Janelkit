# Reto 1: panel de monitorización

Panel del sistema en tiempo real hecho con la API pública de JanelKit. Forma parte de los retos de [docs/challenges_to_test.md](../../../docs/challenges_to_test.md); lo que se aprendió está en [HALLAZGOS.md](HALLAZGOS.md).

## Ejecutar

Necesita `psutil` (`pip install psutil`, incluido en el extra `dev`).

```bash
python main.py                                   # el ordenador real
PANEL_SOURCE=sim python main.py                  # datos simulados (deterministas)
```

Variables de entorno: `PANEL_SOURCE=sim` (fuente simulada), `PANEL_METRICS` (series simuladas, por defecto 30), `PANEL_PROCS` (procesos simulados, 300), `PANEL_RATE_MS` (periodo de muestreo inicial, 250) y `PANEL_HISTORY` (muestras que guarda cada gráfica; por defecto, 60 s).

Prueba de carga (50 métricas, 10 veces por segundo, 10 minutos, y redimensionado al final):

```bash
python bench.py
python bench.py --metrics 50 --rate 10 --seconds 60
```

## Qué hace

- Tarjetas de CPU, memoria, red y disco con su valor y una gráfica de los últimos 60 s (4 muestras por segundo).
- CPU de cada núcleo con su barra.
- Si un valor supera su umbral (CPU o memoria ≥ 90 %), la tarjeta se tiñe con una transición, aparece un aviso arriba y, si la ventana no está en primer plano, una notificación del sistema.
- Tabla de procesos (se lee cada segundo, en otro hilo): ordenable por cualquier columna, filtrable por nombre o PID, con selección y detalles. Ordenar, filtrar o refrescar no pierde la selección ni la posición del scroll.
- `↗` abre cualquier gráfica en su propia ventana; las dos usan el mismo `state` y se actualizan juntas.
- Pausa, cambio del ritmo de muestreo y tema claro/oscuro.

## Archivos

| Archivo | Contenido |
|---|---|
| `src/App.janel` | La ventana: barra de herramientas, tarjetas, núcleos y tabla de procesos. |
| `src/components/Card.janel` | Tarjeta de una métrica (valor, gráfica, aviso por umbral). |
| `src/components/ChartWindow.janel` | Una gráfica en su propia ventana. |
| `src/widgets/LineChart.qml` | La gráfica de línea (QML propio: JanelKit no tiene gráficas, ver hallazgos). |
| `src/services/metrics.py` | Series con historia, fuentes (psutil y simulada) y lista de procesos. |
| `bench.py` | Prueba de carga: CPU del hilo de la interfaz, memoria, latencia hasta la pantalla y coste por fotograma. |
| `../../../tests/test_challenge_panel.py` | Pruebas con `janelkit.inspect`. |
