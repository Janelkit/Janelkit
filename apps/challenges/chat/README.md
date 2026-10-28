# Reto 4: cliente de chat

Cliente de chat por WebSocket hecho solo con la API pública de JanelKit. Forma parte de los retos de [docs/challenges_to_test.md](../../../docs/challenges_to_test.md); lo que se aprendió está en [HALLAZGOS.md](HALLAZGOS.md).

## Ejecutar

Necesita `websockets` (`pip install websockets`, incluido en el extra `dev`).

```bash
python server.py               # terminal 1: servidor de pruebas en ws://127.0.0.1:8765
python main.py                 # terminal 2: el cliente
```

Variables de entorno del cliente: `CHAT_URL` (servidor), `CHAT_USER` (nombre, por defecto `yo`), `CHAT_LANG` (`es`, `en`, `ar`).

Prueba de carga (el servidor se lanza solo, en otro proceso):

```bash
python bench.py --rate 20 --seconds 300
```

## Qué hace

- Salas a la izquierda con contador de no leídos; mensajes a la derecha.
- Los mensajes nuevos llegan en tiempo real. Si estás abajo, la lista los sigue; si subiste a leer, aparece un botón «N mensajes nuevos ↓».
- Al llegar arriba se carga el historial anterior en bloques de 50 sin que la vista salte.
- Mensajes con Markdown (negrita, enlaces, código); el HTML que llega se escapa.
- Imágenes servidas por el propio servidor, reacciones e indicador «escribiendo…».
- Reconexión automática con aviso; al volver se recuperan los mensajes perdidos.
- Notificación del sistema si la ventana no está en primer plano.
- Español, inglés y árabe (de derecha a izquierda).
- Cada sala guarda como mucho unos 600 mensajes en memoria; lo anterior se vuelve a pedir al subir.

## Archivos

| Archivo | Contenido |
|---|---|
| `server.py` | Servidor de pruebas (`websockets`): salas, historial, bots, reacciones e imágenes por HTTP. |
| `src/App.janel` | La ventana: salas, lista de mensajes, redacción. |
| `src/components/Message.janel` | Una burbuja de mensaje. |
| `src/services/chat.py` | Conexión, reconexión y estado reactivo de las salas. |
| `bench.py` | Prueba de carga: memoria, CPU y retraso del bucle de eventos. |
| `../tests/test_challenge_chat.py` | Pruebas con `janelkit.inspect`. |
