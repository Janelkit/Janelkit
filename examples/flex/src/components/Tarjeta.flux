<script lang="python">
# Una tarjeta de la rejilla: cabecera con la insignia empujada a la derecha (margin-left: auto).
from fluxui import prop

title = prop("")
tag = prop("")
body = prop("")
</script>

<flex class="tarjeta">
  <flex class="cabecera">
    <Text class="nombre">{title}</Text>
    <Text class="etiqueta">{tag}</Text>
  </flex>
  <Text class="cuerpo">{body}</Text>
</flex>

<style>
.tarjeta {
  direction: column; gap: 6px; padding: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px 10px 10px 2px;
}
.cabecera { align-items: center; gap: 6px; }
.nombre { font-weight: 600; flex-shrink: 1; }
.etiqueta {
  margin-left: auto; padding: 1px 8px; border-radius: 8px;
  background: var(--surface-alt); color: var(--text-muted); font-size: 12px;
}
.cuerpo { color: var(--text-muted); }
</style>
