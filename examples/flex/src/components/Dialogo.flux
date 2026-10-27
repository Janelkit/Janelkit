<script lang="python">
# Diálogo superpuesto hecho con <flex> (fase 6 de docs/flex.md). El velo es una caja
# fija sobre toda la ventana (position: fixed; inset: 0): no deja pulsar lo de debajo.
# Retiene el foco: Tab y Mayús+Tab dan la vuelta entre sus botones (on:keydown con
# event.prevent()). Escape o un clic en el velo lo cierran, y el foco vuelve a quien lo
# abrió (`opener`, una ref). Nada de esto es una función de <flex>: es este componente.
# El clic en el velo solo cierra si empezó fuera del diálogo (como en la web, un clic
# que empieza dentro y se suelta fuera no cuenta).
from fluxui import event, on_destroy, on_mount, prop, ref, state
from components.Boton import Boton

title = prop("")
text = prop("")
opener = prop(None)  # ref del elemento que lo abrió: recibe el foco al cerrar
accept = event()
close = event()
cancelar = ref()
aceptar = ref()
dentro = state(False)  # la última pulsación empezó dentro del diálogo
on_mount(lambda: aceptar.focus())


@on_destroy
def devolver_foco():
    if opener.value is not None:
        opener.value.focus()


def pulsar_dentro(event):
    dentro.set(True)
    event.stop()  # no llega al velo


def clic_velo():
    if not dentro.value:
        close.emit()


def tecla(event):
    if event.key == "Escape":
        close.emit()
    elif event.key == "Tab":
        orden = [cancelar, aceptar]
        actual = next((i for i, r in enumerate(orden) if r.focused), -1)
        orden[(actual + (-1 if event.shift else 1)) % len(orden)].focus()
    else:
        return
    event.prevent()
</script>

<flex class="velo" on:pointerdown={dentro = False} on:click={clic_velo()}>
  <flex as="dialog" class="dialogo" label={title} on:pointerdown={pulsar_dentro} on:keydown={tecla}>
    <Text class="titulo">{title}</Text>
    <Text class="texto">{text}</Text>
    <flex class="botones">
      <Boton text="Cancelar" ref={cancelar} on:click={close.emit()} />
      <Boton text="Aceptar" class="primary" ref={aceptar} on:click={accept.emit()} />
    </flex>
  </flex>
</flex>

<style>
.velo {
  position: fixed; inset: 0; z-index: 100;
  justify-content: center; align-items: center;
  background: rgba(0, 0, 0, 0.35);
}
.dialogo {
  direction: column; gap: 10px; padding: 20px; width: 360px;
  background: var(--surface); border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
}
.titulo { font-size: 18px; font-weight: 600; }
.texto { color: var(--text-muted); }
.botones { justify-content: end; gap: 8px; }
</style>
