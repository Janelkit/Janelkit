<script lang="python">
# Reto 1: panel de monitorización en tiempo real. Ver ../HALLAZGOS.md.
import os

from fluxui import computed, interval, notify, open_window, state, theme
from components.Card import Card
from components.ChartWindow import ChartWindow
from services.metrics import Monitor, SimulatedSource, SystemSource, format_value

# PANEL_SOURCE=sim: datos sintéticos (pruebas y mediciones); PANEL_METRICS: cuántas series.
if os.environ.get("PANEL_SOURCE") == "sim":
    source = SimulatedSource(metrics=int(os.environ.get("PANEL_METRICS", "30")), procs=int(os.environ.get("PANEL_PROCS", "300")))
else:
    source = SystemSource()
RATE_MS = int(os.environ.get("PANEL_RATE_MS", "250"))
monitor = Monitor(source, capacity=int(os.environ.get("PANEL_HISTORY", str(60_000 // RATE_MS))))

COLORS = ["#3b5bdb", "#2b8a3e", "#e8590c", "#ae3ec9", "#1098ad", "#f08c00"]
RATES = [{"label": "4 por segundo", "value": 250}, {"label": "2 por segundo", "value": 500}, {"label": "1 por segundo", "value": 1000}]
if RATE_MS not in [r["value"] for r in RATES]:
    RATES.insert(0, {"label": f"cada {RATE_MS} ms", "value": RATE_MS})
COLUMNS = [
    {"key": "name", "label": "Proceso", "width": 0},
    {"key": "pid", "label": "PID", "width": 64},
    {"key": "cpu", "label": "CPU", "width": 72},
    {"key": "mem", "label": "Memoria", "width": 84},
    {"key": "threads", "label": "Hilos", "width": 56},
]

paused = state(False)
rate = state(RATE_MS)
active = state(True)
sort_key = state("cpu")
descending = state(True)
query = state("")
selected = state(None)  # pid del proceso seleccionado
windows = {}  # id de la serie -> ventana abierta con su gráfica

card_rows = [monitor.main[i:i + 3] for i in range(0, len(monitor.main), 3)]
core_rows = [monitor.cores[i:i + 8] for i in range(0, len(monitor.cores), 8)]


@interval(RATE_MS)
def sampler():
    before = {s.id for s in monitor.alerts()}
    monitor.sample()
    fresh = [s for s in monitor.alerts() if s.id not in before]
    if fresh and not active.peek():
        notify("Umbral superado", ", ".join(f"{s.label}: {s.text()}" for s in fresh))


@interval(1000)
async def processes():
    await monitor.refresh_processes()


monitor.sample()  # para no empezar con todo a cero


def set_rate(ms):
    rate.value = ms
    sampler.ms = ms
    sampler.restart()


def set_paused(value):
    paused.value = value
    if value:
        sampler.stop()
        processes.stop()
    else:
        sampler.start()
        processes.start()


def sort_by(key):
    if sort_key.value == key:
        descending.value = not descending.value
    else:
        sort_key.value = key
        descending.value = key != "name"


@computed
def rows():
    q = query.value.strip().lower()
    procs = monitor.processes.value
    if q:
        procs = [p for p in procs if q in p["name"].lower() or q == str(p["pid"])]
    key = sort_key.value
    if key == "name":
        return sorted(procs, key=lambda p: (p["name"].lower(), p["pid"]), reverse=descending.value)
    return sorted(procs, key=lambda p: (p[key], -p["pid"]), reverse=descending.value)


@computed
def current():
    pid = selected.value
    return next((p for p in monitor.processes.value if p["pid"] == pid), None) if pid is not None else None


@computed
def alerts():
    return monitor.alerts()


def heading(col):
    if col["key"] != sort_key.value:
        return col["label"]
    return col["label"] + (" ▼" if descending.value else " ▲")


def cell(p, key):
    if key == "cpu":
        return f"{p['cpu']:.1f} %"
    if key == "mem":
        return format_value(p["mem"] / (1 << 30), "GB") if p["mem"] >= 1 << 30 else f"{p['mem'] / (1 << 20):.0f} MB"
    return str(p[key])


def open_chart(series):
    w = windows.get(series.id)
    if w is not None and w.is_open:
        w.focus()
        return
    windows[series.id] = open_window(ChartWindow, series=series, color=color_of(series))


def color_of(series):
    return COLORS[monitor.main.index(series) % len(COLORS)] if series in monitor.main else COLORS[0]
</script>

<Window title="Panel del sistema" width={1280} height={800} minWidth={900} minHeight={560}
        on:activate={active = True} on:deactivate={active = False}>
  <Column class="app">
    <Row class="toolbar">
      <Text class="brand">Panel del sistema</Text>
      <Text class="muted">{len(monitor.cores)} núcleos · {source.total_memory:.0f} GB</Text>
      <Spacer />
      <Text class="muted">Muestreo</Text>
      <Select value={rate} options={RATES} on:change={set_rate} width={150} />
      <Switch checked={paused} on:change={set_paused} text="Pausa" />
      <Button variant="ghost" on:click={theme.toggle()}>{"☀" if theme.name == "dark" else "☾"}</Button>
    </Row>

    {#if alerts}
      <Row class="banner" transition:fade>
        <Text class="banner-text">⚠ Por encima del umbral: {", ".join(s.label + " " + s.text() for s in alerts)}</Text>
      </Row>
    {/if}

    <Row class="body">
      <Scroll class="left">
        {#each card_rows as row}
          <Row class="cards">
            {#each row as s (s.id)}
              <Card series={s} color={color_of(s)} on:expand={open_chart} flex={1} />
            {/each}
          </Row>
        {/each}

        <Text class="section">CPU por núcleo</Text>
        {#each core_rows as row}
          <Row class="cores">
            {#each row as c (c.id)}
              <Column class="core" class:hot={c.value.value >= 90} flex={1} label={c.label}>
                <Row>
                  <Text class="muted" flex={1}>{c.id[4:]}</Text>
                  <Text class="core-value">{c.value.value:.0f}%</Text>
                </Row>
                <ProgressBar value={c.value.value} max={100} />
              </Column>
            {/each}
          </Row>
        {/each}
      </Scroll>

      <Column class="right">
        <Row class="filter">
          <TextField id="query" bind:value={query} placeholder="Filtrar por nombre o PID" flex={1} />
          <Text class="muted">{len(rows)} procesos</Text>
        </Row>
        <Row class="thead">
          {#each COLUMNS as col (col["key"])}
            {#if col["width"]}
              <Button variant="ghost" class="th" on:click={sort_by(col["key"])} width={col["width"]}>{heading(col)}</Button>
            {:else}
              <Button variant="ghost" class="th" on:click={sort_by(col["key"])} flex={1}>{heading(col)}</Button>
            {/if}
          {/each}
        </Row>
        <List id="procs" class="procs">
          {#each rows as p (p["pid"])}
            <Row class="tr" class:sel={p["pid"] == selected} on:click={selected = p["pid"]} label={p["name"]}>
              <Text class="td" flex={1}>{p["name"]}</Text>
              <Text class="td num" width={64}>{p["pid"]}</Text>
              <Text class="td num" width={72}>{cell(p, "cpu")}</Text>
              <Text class="td num" width={84}>{cell(p, "mem")}</Text>
              <Text class="td num" width={56}>{p["threads"]}</Text>
            </Row>
          {/each}
        </List>
        <Column class="details">
          {#if current is not None}
            <Text class="detail-title">{current["name"]}</Text>
            <Text class="muted">PID {current["pid"]} · {current["user"] or "—"} · {current["threads"]} hilos</Text>
            <Text>CPU {cell(current, "cpu")} · Memoria {cell(current, "mem")}</Text>
          {:else if selected is not None}
            <Text class="muted">El proceso {selected} ha terminado.</Text>
          {:else}
            <Text class="muted">Selecciona un proceso para ver sus detalles.</Text>
          {/if}
        </Column>
      </Column>
    </Row>
  </Column>
</Window>

<style>
.app { gap: 0; }
.toolbar { padding: 10px 16px; gap: 10px; background: var(--surface); border-color: var(--border); }
.brand { font-size: var(--font-size-lg); font-weight: 600; }
.muted { color: var(--text-muted); }
.banner { background: var(--danger); padding: 6px 16px; }
.banner-text { color: var(--on-danger); }
.body { flex: 1; align-self: stretch; gap: 0; }
.left { flex: 1; align-self: stretch; padding: 16px; gap: 12px; }
.cards { gap: 12px; }
.section { font-weight: 600; padding-top: 4px; }
.cores { gap: 8px; }
.core { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px 8px; gap: 4px;
        transition: background 300ms; }
.hot { background: #33e03131; }
.core-value { font-size: var(--font-size-sm); }
.right { width: 470px; align-self: stretch; background: var(--surface); padding: 12px; gap: 6px; }
.filter { gap: 8px; }
.thead { gap: 0; }
.th { font-weight: 600; }
.procs { gap: 0; }
.tr { padding: 3px 6px; border-radius: var(--radius-sm); gap: 0; }
.sel { background: #403b5bdb; }
.td { font-size: var(--font-size-sm); }
.num { text-align: right; }
.details { gap: 2px; padding-top: 8px; border-color: var(--border); }
.detail-title { font-weight: 600; }
</style>
