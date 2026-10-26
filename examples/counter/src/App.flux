<script lang="python">
from fluxui import state, computed

count = state(0)
name = state("")

@computed
def greeting():
    return f"Hola, {name.value or 'invitado'}"

def increment():
    count.value += 1

def decrement():
    count.value -= 1
</script>

<Window title="Mi aplicación" width={640} height={400}>
  <Column class="page">
    <Text class="heading">{greeting}</Text>
    <TextField bind:value={name} placeholder="Tu nombre" width={320} />
    <Row class="actions">
      <Button on:click={decrement} enabled={count > 0}>−</Button>
      <Button on:click={increment}>Clicks: {count}</Button>
    </Row>

    {#if count >= 5}
      <Text class="success">Has llegado a cinco clicks.</Text>
    {:else}
      <Text class="muted">Faltan {5 - count} clicks para llegar a cinco.</Text>
    {/if}
  </Column>
</Window>

<style>
.page { padding: 24px; gap: 16px; }
.heading { font-size: 24px; font-weight: 600; }
.actions { gap: 8px; }
.success { color: #2e7d32; }
.muted { color: #757575; }
</style>
