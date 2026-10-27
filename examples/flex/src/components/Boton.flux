<script lang="python">
# Botón hecho solo con <flex>. as="button" le da el papel de botón: Tab para llegar,
# Espacio o Intro para pulsar, y el nombre para los lectores de pantalla. Los estados
# (:hover, :pressed, :focus-visible, :disabled) los cambia la vista: pasar el ratón
# por encima no llama a Python.
# Se usa como un elemento más (fase 5): on:click, disabled, ref y class van a la raíz
# sin declararlos aquí, y las variantes son clases: <Boton class="primary" on:click=...>.
from fluxui import prop

text = prop("")
</script>

<flex as="button" class="boton" label={text}>
  <Text>{text}</Text>
</flex>

<style>
.boton {
  justify-content: center; align-items: center; padding: 6px 14px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  cursor: pointer;
  transition: background 120ms, border-color 120ms, transform 80ms, box-shadow 120ms;
}
.boton:hover { background: var(--surface-alt); }
.boton:pressed { transform: scale(0.96); }
.boton:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.boton:disabled { opacity: 0.45; }
.boton { font-weight: 500; }

/* El texto hereda el color de la caja (fase 4): no hace falta estilar .texto. */
.boton.primary { background: var(--primary); border-color: var(--primary); color: var(--on-primary); }
.boton.primary:hover { box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25); }

.boton.ghost { background: transparent; border-color: transparent; }
.boton.ghost:hover { background: var(--surface-alt); }
</style>
