<script lang="python">
# Una gráfica en su propia ventana: usa la misma Series (el mismo state) que la tarjeta.
from fluxui import prop
from widgets.LineChart import LineChart

series = prop()
color = prop("#3b5bdb")
</script>

<Window title={series.label} width={640} height={320} minWidth={320} minHeight={200}>
  <Column class="page">
    <Row class="head">
      <Text class="label" flex={1}>{series.label} · últimos 60 s</Text>
      <Text class="value">{series.text()}</Text>
    </Row>
    <LineChart values={series.history.value} max={series.max} color={color} unit={series.unit} capacity={series.capacity} flex={1} class="chart" />
  </Column>
</Window>

<style>
.chart { width: 100%; }
.page { padding: 16px; gap: 8px; }
.label { color: var(--text-muted); }
.value { font-weight: 600; font-size: var(--font-size-xl); }
</style>
