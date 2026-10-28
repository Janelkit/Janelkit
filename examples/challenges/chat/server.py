"""Servidor de chat de pruebas para el reto (WebSocket, con `websockets`).

    python server.py                 # ws://127.0.0.1:8765, bots tranquilos
    python server.py --rate 20       # 20 mensajes por segundo (prueba de carga)

Salas con historial generado, bots que escriben (con "escribiendo…"), reacciones
e imágenes servidas por HTTP en el mismo puerto (`/img/<n>.png`).

Protocolo (JSON, un objeto por mensaje):

  cliente -> servidor
    {"type": "hello", "user": "yo", "last": {"general": 812, ...}}   # last: para recuperar lo perdido
    {"type": "history", "room": "general", "before": 700, "limit": 50}
    {"type": "send", "room": "general", "text": "hola"}
    {"type": "typing", "room": "general"}
    {"type": "react", "room": "general", "id": 812, "emoji": "👍"}

  servidor -> cliente
    {"type": "rooms", "rooms": [{"id", "name", "last_id"}]}
    {"type": "history", "room", "messages": [...], "complete": bool}   # complete: no hay más antiguos
    {"type": "message", "room", "message": {"id", "author", "text", "ts", "image"?, "reactions"}}
    {"type": "typing", "room", "user"}
    {"type": "reaction", "room", "id", "reactions": {"👍": 2}}
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import random
import struct
import time
import zlib
from http import HTTPStatus

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

ROOMS = [
    {"id": "general", "name": "General"},
    {"id": "python", "name": "Python"},
    {"id": "random", "name": "Aleatorio"},
    {"id": "arabic", "name": "العربية"},
]
BOTS = ["Ana", "Luis", "Marta", "Kenji", "Fátima"]
LINES = [
    "¿Alguien ha probado **JanelKit** con *asyncio*?",
    "Mirad esto: [documentación de Qt](https://doc.qt.io)",
    "El error estaba en `await background(fn)` 😅",
    "Hoy toca revisar el *pull request* de las listas",
    "```\nfor i in range(3):\n    print(i)\n```",
    "Esto es un mensaje bastante más largo de lo normal para comprobar que el texto se ajusta "
    "a varias líneas sin romper la disposición de la burbuja ni el desplazamiento de la lista.",
    "👍",
    "¿Comemos a las dos?",
    "<b>esto no debería verse en negrita</b> (HTML escapado)",
]
ARABIC = ["مرحبا بالجميع", "كيف حالكم اليوم؟", "**مهم**: الاجتماع غدًا", "شكرًا جزيلًا 🙏"]
REACTIONS = ["👍", "❤️", "😂", "🎉"]


def png(color: tuple[int, int, int], w: int = 240, h: int = 140) -> bytes:
    """PNG de un color liso (sin dependencias)."""
    row = b"\x00" + bytes(color) * w
    raw = zlib.compress(row * h)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


class ChatServer:
    def __init__(self, history: int = 400, rate: float = 0.5, seed: int = 1):
        self.rng = random.Random(seed)
        self.ids = itertools.count(1)
        self.messages: dict[str, list[dict]] = {r["id"]: [] for r in ROOMS}
        self.clients: set[ServerConnection] = set()
        self.rate = rate
        self.port = 0
        now = time.time() - history * 60
        for i in range(history):
            for room in self.messages:
                self.messages[room].append(self.new_message(room, ts=now + i * 60))

    def new_message(self, room: str, author: str | None = None, text: str | None = None, ts: float | None = None) -> dict:
        n = next(self.ids)
        if text is None:
            text = self.rng.choice(ARABIC if room == "arabic" else LINES)
        msg = {"id": n, "author": author or self.rng.choice(BOTS), "text": text, "ts": ts or time.time(), "reactions": {}}
        if author is None and n % 17 == 0:
            msg["image"] = f"/img/{n % 6}.png"
        return msg

    # -- conexión -------------------------------------------------------------
    async def handler(self, ws: ServerConnection) -> None:
        self.clients.add(ws)
        try:
            async for raw in ws:
                await self.on_message(ws, json.loads(raw))
        except Exception:  # noqa: BLE001 - cliente desconectado a lo bruto
            pass
        finally:
            self.clients.discard(ws)

    async def on_message(self, ws: ServerConnection, data: dict) -> None:
        kind = data.get("type")
        if kind == "hello":
            rooms = [{**r, "last_id": self.messages[r["id"]][-1]["id"]} for r in ROOMS]
            await ws.send(json.dumps({"type": "rooms", "rooms": rooms}))
            for room, last in (data.get("last") or {}).items():  # lo que se perdió mientras estaba desconectado
                for msg in self.messages.get(room, []):
                    if msg["id"] > last:
                        await ws.send(json.dumps({"type": "message", "room": room, "message": msg}))
        elif kind == "history":
            room = self.messages[data["room"]]
            before = data.get("before") or 1 << 62
            older = [m for m in room if m["id"] < before]
            chunk = older[-int(data.get("limit", 50)):]
            await ws.send(json.dumps({"type": "history", "room": data["room"], "messages": chunk, "complete": len(chunk) == len(older)}))
        elif kind == "send":
            await self.publish(data["room"], self.new_message(data["room"], author=data.get("user", "yo"), text=data["text"]))
        elif kind == "typing":
            await self.broadcast({"type": "typing", "room": data["room"], "user": data.get("user", "?")}, skip=ws)
        elif kind == "react":
            msg = next((m for m in self.messages[data["room"]] if m["id"] == data["id"]), None)
            if msg is not None:
                msg["reactions"][data["emoji"]] = msg["reactions"].get(data["emoji"], 0) + 1
                await self.broadcast({"type": "reaction", "room": data["room"], "id": msg["id"], "reactions": msg["reactions"]})

    async def publish(self, room: str, msg: dict) -> None:
        self.messages[room].append(msg)
        await self.broadcast({"type": "message", "room": room, "message": msg})

    async def broadcast(self, data: dict, skip: ServerConnection | None = None) -> None:
        text = json.dumps(data)
        for client in list(self.clients):
            if client is not skip:
                try:
                    await client.send(text)
                except Exception:  # noqa: BLE001
                    self.clients.discard(client)

    # -- bots -----------------------------------------------------------------
    async def bots(self) -> None:
        due = time.monotonic()
        while True:
            # Plazos absolutos: sleep() se pasa (15 ms en Windows) y el ritmo real bajaría.
            due += 1 / self.rate if self.rate > 0 else 3600
            await asyncio.sleep(max(0, due - time.monotonic()))
            room = self.rng.choice(list(self.messages))
            author = self.rng.choice(BOTS)
            if self.rate <= 2 and self.rng.random() < 0.5:  # a ritmo humano, avisa antes de escribir
                await self.broadcast({"type": "typing", "room": room, "user": author})
                await asyncio.sleep(1.2)
                due += 1.2
            await self.publish(room, self.new_message(room, author=author, text=self.rng.choice(ARABIC if room == "arabic" else LINES)))
            if self.rng.random() < 0.1:
                msg = self.rng.choice(self.messages[room][-10:])
                emoji = self.rng.choice(REACTIONS)
                msg["reactions"][emoji] = msg["reactions"].get(emoji, 0) + 1
                await self.broadcast({"type": "reaction", "room": room, "id": msg["id"], "reactions": msg["reactions"]})

    # -- imágenes por HTTP en el mismo puerto -------------------------------------
    def http(self, connection: ServerConnection, request: Request) -> Response | None:
        if not request.path.startswith("/img/"):
            return None  # es un WebSocket
        n = int(request.path.rsplit("/", 1)[1].split(".")[0]) % 6
        color = [(79, 70, 229), (16, 185, 129), (245, 158, 11), (239, 68, 68), (14, 165, 233), (168, 85, 247)][n]
        body = png(color)
        headers = Headers({"Content-Type": "image/png", "Content-Length": str(len(body))})
        return Response(HTTPStatus.OK, "OK", headers, body)

    async def serve(self, host: str = "127.0.0.1", port: int = 8765, ready: asyncio.Event | None = None) -> None:
        async with serve(self.handler, host, port, process_request=self.http) as server:
            self.port = server.sockets[0].getsockname()[1]
            bots = asyncio.ensure_future(self.bots())
            if ready is not None:
                ready.set()
            try:
                await asyncio.Future()  # para siempre
            finally:
                bots.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--rate", type=float, default=0.5, help="mensajes de los bots por segundo")
    args = parser.parse_args()
    server = ChatServer(rate=args.rate)
    print(f"chat en ws://127.0.0.1:{args.port} ({args.rate} mensajes/s)")
    try:
        asyncio.run(server.serve(port=args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
