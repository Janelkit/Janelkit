"""Cliente del chat: una conexión WebSocket que vive toda la sesión.

Todo el estado es reactivo y se modifica en el hilo de la interfaz: la
corrutina `run()` corre sobre el bucle de Qt (qasync), así que no hace falta
pasar nada entre hilos.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable

from janelkit import Timer, batch, state, timeout

MAX_KEPT = 600  # mensajes que se guardan por sala cuando se está abajo (la memoria no crece sin fin)
PAGE = 50


class Room:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.messages = state([])  # lista reactiva de mensajes, del más antiguo al más reciente
        self.complete = state(False)  # ya no hay historial más antiguo en el servidor
        self.loading = state(False)
        self.unread = state(0)
        self.typing = state("")  # quién está escribiendo ahora mismo
        self._typing_clear: Timer | None = None  # borra el aviso de "escribiendo…"
        self.by_id: dict[int, dict] = {}

    @property
    def last_id(self) -> int:
        msgs = self.messages.peek()
        return msgs[-1]["id"] if msgs else 0

    def add(self, msg: dict) -> bool:
        if msg["id"] in self.by_id:
            return False
        msgs = self.messages.peek()
        msgs.append(msg)
        self.by_id[msg["id"]] = msgs[-1]
        return True

    def prepend(self, older: list[dict]) -> None:
        older = [m for m in older if m["id"] not in self.by_id]
        msgs = self.messages.peek()
        msgs[0:0] = older
        for m in msgs[: len(older)]:
            self.by_id[m["id"]] = m

    def trim(self) -> None:
        """Descarta los más antiguos si hay demasiados (el historial se vuelve a pedir al subir)."""
        msgs = self.messages.peek()
        extra = len(msgs) - MAX_KEPT
        if extra > PAGE:
            for m in msgs[:extra]:
                self.by_id.pop(m["id"], None)
            del msgs[:extra]
            self.complete.value = False


class ChatClient:
    def __init__(self, url: str, user: str):
        self.url = url
        self.user = user
        self.status = state("connecting")  # "connecting" | "online" | "offline"
        self.rooms: dict[str, Room] = {}
        self.room_list = state([])  # [Room] en el orden del servidor
        self.received = 0  # mensajes recibidos (para mediciones)
        self.on_message: Callable[[Room, dict], Any] | None = None  # lo fija la interfaz
        self._ws: Any = None
        self._outbox: list[dict] = []  # lo que se envía sin conexión sale al reconectar

    # -- conexión con reconexión -------------------------------------------------
    async def run(self) -> None:
        from websockets.asyncio.client import connect

        delay = 0.5
        while True:
            self.status.value = "connecting"
            try:
                async with connect(self.url, max_size=None, open_timeout=3) as ws:
                    self._ws = ws
                    self.status.value = "online"
                    delay = 0.5
                    last = {room.id: room.last_id for room in self.rooms.values() if room.last_id}
                    await ws.send(json.dumps({"type": "hello", "user": self.user, "last": last}))
                    while self._outbox:
                        await ws.send(json.dumps(self._outbox.pop(0)))
                    async for raw in ws:
                        self.handle(json.loads(raw))
            except (OSError, asyncio.TimeoutError):
                pass  # servidor caído o inalcanzable: se reintenta
            except Exception as exc:  # noqa: BLE001 - cierre del servidor, protocolo...
                if type(exc).__module__.split(".")[0] != "websockets":
                    raise
            finally:
                self._ws = None
            self.status.value = "offline"
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5)

    def send_json(self, data: dict) -> None:
        if self._ws is None:
            if data["type"] == "send":
                self._outbox.append(data)
            return

        async def go() -> None:
            try:
                await self._ws.send(json.dumps(data))
            except Exception:  # noqa: BLE001 - se perdió la conexión: run() reconecta
                if data["type"] == "send":
                    self._outbox.append(data)

        asyncio.ensure_future(go())

    # -- mensajes del servidor ------------------------------------------------
    def handle(self, data: dict) -> None:
        kind = data["type"]
        if kind == "rooms":
            for r in data["rooms"]:
                if r["id"] not in self.rooms:
                    self.rooms[r["id"]] = Room(r["id"], r["name"])
            self.room_list.value = [self.rooms[r["id"]] for r in data["rooms"]]
            for room in self.rooms.values():
                if not room.messages.peek():
                    self.load_history(room)
        elif kind == "history":
            room = self.rooms[data["room"]]
            with batch():
                room.prepend(data["messages"])
                room.complete.value = data["complete"]
                room.loading.value = False
        elif kind == "message":
            room = self.rooms[data["room"]]
            self.received += 1
            if room.add(data["message"]):
                room.typing.value = "" if room.typing.peek() == data["message"]["author"] else room.typing.peek()
                if self.on_message is not None:
                    self.on_message(room, room.messages.peek()[-1])
        elif kind == "typing":
            self.show_typing(self.rooms[data["room"]], data["user"])
        elif kind == "reaction":
            room = self.rooms[data["room"]]
            msg = room.by_id.get(data["id"])
            if msg is not None:
                msg["reactions"] = data["reactions"]

    def show_typing(self, room: Room, user: str) -> None:
        room.typing.value = user
        if room._typing_clear is None:
            room._typing_clear = timeout(3000, lambda: room.typing.set(""))
        else:
            room._typing_clear.restart()  # otro aviso: vuelve a contar los 3 s

    # -- acciones de la interfaz ----------------------------------------------
    def load_history(self, room: Room) -> None:
        if room.loading.peek() or room.complete.peek():
            return
        msgs = room.messages.peek()
        room.loading.value = True
        self.send_json({"type": "history", "room": room.id, "before": msgs[0]["id"] if msgs else None, "limit": PAGE})

    def send(self, room: Room, text: str) -> None:
        self.send_json({"type": "send", "room": room.id, "text": text, "user": self.user})

    def typing(self, room: Room) -> None:
        now = time.monotonic()
        if now - getattr(room, "_typing_sent", 0) > 2:
            room._typing_sent = now
            self.send_json({"type": "typing", "room": room.id, "user": self.user})

    def react(self, room: Room, msg_id: int, emoji: str) -> None:
        self.send_json({"type": "react", "room": room.id, "id": msg_id, "emoji": emoji})
