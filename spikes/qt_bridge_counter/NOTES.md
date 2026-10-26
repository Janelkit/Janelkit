# Spike `qt_bridge_counter` — nota de viabilidad (Incremento 0)

**Entorno probado:** Windows 11, Python 3.13.9, PySide6 6.12.0, plataforma `offscreen` y ventana real.

- `python main.py` abre la ventana del contador.
- `python check.py` hace la verificación automática sin mostrar ventanas.

## Resultado

**Viable. Se continúa con el enfoque PySide6 + Qt Quick (PR-005).**

| Criterio de salida | Resultado |
|---|---|
| El texto cambia al cambiar el estado Python | ✅ `set_value` emite `<prop>Changed` y QML actualiza solo esa propiedad |
| Un clic modifica estado Python | ✅ `onClicked: fx.invoke("increment")` |
| Escribir en un campo sincroniza el valor | ✅ `onTextEdited: fx.write("name", text)` |
| Sin bucles de actualización | ✅ una sola escritura por edición; el puente no emite si el valor no cambió |
| El binding `text: fx.name` sobrevive a la edición del usuario | ✅ un cambio posterior desde Python sigue llegando al `TextField` |

## Hallazgos y restricciones

1. **Clase puente dinámica.** Se puede crear una subclase de `QObject` con `type(...)`, declarando un `Signal` y una `Property("QVariant", ..., notify=...)` por binding. Así cada componente compilado tiene propiedades con nombre (`b0`, `b1`, …) y QML solo reevalúa los bindings afectados.
2. **Los slots necesitan nombre.** `Slot(str)(lambda ...)` registra el slot como `<lambda>` y QML no lo encuentra (falla silenciosamente: el clic no hace nada). Hay que usar funciones con `__name__` correcto.
3. **Ciclo de vida del contexto.** Si el `QQmlContext` por instancia se recolecta en Python, la ventana se destruye (`Internal C++ object already deleted`). El runtime debe crear el contexto con padre (`QQmlContext(parent_ctx, engine)`) y mantener vivo el `QQmlComponent` junto a la instancia.
4. **Un contexto por instancia.** `setContextProperty("fx", bridge)` en un contexto hijo permite que varias instancias del mismo QML usen puentes distintos: es el mecanismo previsto para estado independiente por instancia.
5. **`textEdited` vs `textChanged`.** Se usa `textEdited` (solo edición del usuario) para escribir en Python; así las asignaciones desde Python no regresan como escritura.
6. **Tipos.** `QVariant` transporta `int`, `float`, `bool`, `str`, listas y diccionarios sin conversiones manuales. Objetos Python arbitrarios no deben cruzar al QML.
7. **Hilo de interfaz.** Todo ocurre en el hilo de Qt; el trabajo asíncrono queda pendiente de una integración explícita.
