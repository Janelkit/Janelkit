<script lang="python">
# Una tarjeta de la rejilla: cabecera con la insignia empujada a la derecha (margin-left: auto).
# Al pasar el ratón se eleva (sombra y translate) y muestra sus acciones (.tarjeta:hover .acciones).
from fluxui import event, prop
from components.Boton import Boton

title = prop("")
tag = prop("")
body = prop("")
action = event()
</script>

<flex class="tarjeta">
  <flex class="cabecera">
    <Text class="nombre">{title}</Text>
    <Text class="etiqueta">{tag}</Text>
  </flex>
  <Text class="cuerpo">{body}</Text>
  <flex class="acciones">
    <Boton text="Abrir" class="primary" on:click={action.emit(f"abrir {title}")} />
    <Boton text="Archivar" class="ghost" on:click={action.emit(f"archivar {title}")} />
  </flex>
</flex>

<style>
.tarjeta {
  direction: column; gap: 6px; padding: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px 10px 10px 2px;
  transition: transform 150ms, box-shadow 150ms, border-color 150ms;
}
.tarjeta:hover {
  transform: translateY(-2px); border-color: var(--primary);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}
.cabecera { align-items: center; gap: 6px; }
.nombre { font-weight: 600; flex-shrink: 1; }
.etiqueta {
  margin-left: auto; padding: 1px 8px; border-radius: 8px;
  background: var(--surface-alt); color: var(--text-muted); font-size: 12px;
}
.cuerpo { color: var(--text-muted); }
/* Las acciones ocupan su sitio siempre (sin saltos), pero solo se ven al pasar por encima
   o al llegar con el teclado a uno de sus botones. */
.acciones { gap: 6px; opacity: 0; transition: opacity 150ms; }
.tarjeta:hover .acciones, .tarjeta:focus-within .acciones { opacity: 1; }
</style>
