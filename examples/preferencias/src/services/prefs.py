"""Lo que la aplicación recuerda entre sesiones. Cualquier componente lo importa y lo usa
como un state: los cambios se guardan solos (persisted)."""
from fluxui import persisted

DEFAULTS = {"nombre": "", "tema": "light", "letra": 14, "notas": []}

nombre = persisted("prefs.nombre", DEFAULTS["nombre"])
tema = persisted("prefs.tema", DEFAULTS["tema"])
letra = persisted("prefs.letra", DEFAULTS["letra"])
notas = persisted("notas", DEFAULTS["notas"])  # [{"id", "texto", "hecha"}]
aperturas = persisted("aperturas", 0)


def restablecer():
    """Vuelve a los valores de fábrica (las aperturas no se tocan)."""
    nombre.value = DEFAULTS["nombre"]
    tema.value = DEFAULTS["tema"]
    letra.value = DEFAULTS["letra"]
    notas.value = []
