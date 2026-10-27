<script lang="python">
# Barra de herramientas hecha solo con <flex>: grupos separados por un borde a la
# izquierda, el título a un lado y los grupos al otro (justify-content: space-between).
from fluxui import event, prop

title = prop("")
action = event()
</script>

<flex class="barra">
  <Text class="titulo">{title}</Text>
  <flex class="grupos">
    <flex class="grupo">
      <Button flat on:click={action.emit("nuevo")}>Nuevo</Button>
      <Button flat on:click={action.emit("abrir")}>Abrir</Button>
    </flex>
    <flex class="grupo separado">
      <Button flat on:click={action.emit("cortar")}>Cortar</Button>
      <Button flat on:click={action.emit("copiar")}>Copiar</Button>
      <Button flat on:click={action.emit("pegar")}>Pegar</Button>
    </flex>
    <flex class="grupo separado">
      <Button variant="primary" on:click={action.emit("compartir")}>Compartir</Button>
    </flex>
  </flex>
</flex>

<style>
.barra {
  justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;
  padding: 6px 12px; background: var(--surface); border-bottom: 1px solid var(--border);
}
.titulo { font-weight: 600; font-size: 15px; }
.grupos { align-items: center; flex-wrap: wrap; row-gap: 4px; }
.grupo { align-items: center; gap: 2px; padding: 0 8px; }
.separado { border-left: 1px solid var(--border); }
</style>
