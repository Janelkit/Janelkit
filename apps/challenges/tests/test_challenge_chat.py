"""Reto 4 (docs/challenges_to_test.md): cliente de chat por WebSocket, probado como un usuario."""
import asyncio
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("websockets")

from janelkit.inspect import mount  # noqa: E402

CHAT = Path(__file__).resolve().parents[1] / "chat"
sys.path.insert(0, str(CHAT))
from server import ChatServer  # noqa: E402


class ServerThread:
    """El servidor de pruebas en su propio hilo y bucle asyncio; se puede parar y volver a arrancar."""

    def __init__(self):
        self.server = ChatServer(history=200, rate=0)  # sin bots: los mensajes los manda la prueba
        self.port = 0
        self.loop = None
        self.task = None

    def start(self):
        started = threading.Event()

        def run():
            async def main():
                ready = asyncio.Event()
                self.loop = asyncio.get_running_loop()
                self.task = asyncio.ensure_future(self.server.serve(port=self.port, ready=ready))
                await ready.wait()
                self.port = self.server.port
                started.set()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass

            asyncio.run(main())

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert started.wait(5)

    def stop(self):
        async def close():
            for ws in list(self.server.clients):
                ws.transport.abort()  # corte brusco, como una caída de red
            self.task.cancel()

        asyncio.run_coroutine_threadsafe(close(), self.loop).result(5)
        self.thread.join(5)

    def say(self, room, text, author="Ana"):
        msg = self.server.new_message(room, author=author, text=text)
        asyncio.run_coroutine_threadsafe(self.server.publish(room, msg), self.loop).result(5)
        return msg


@pytest.fixture
def chat(monkeypatch):
    srv = ServerThread()
    srv.start()
    monkeypatch.setenv("CHAT_URL", f"ws://127.0.0.1:{srv.port}")
    monkeypatch.setenv("CHAT_LANG", "es")
    with mount(CHAT / "src" / "App.janel") as app:
        client = app.get("client")
        app.wait(until=lambda: len(client.room_list.value) == 4 and len(client.rooms["general"].messages.value) == 50)
        yield app, srv
    if srv.thread.is_alive():
        srv.stop()


def room(app, name="general"):
    return app.get("client").rooms[name]


def test_connects_and_shows_the_last_page_of_history(chat):
    app, srv = chat
    assert app.get("client").status.value == "online"
    last = srv.server.messages["general"][-1]["text"]
    texts = app.texts()
    assert "# General" in texts
    assert any(last.replace("**", "") in t or last in t for t in texts)


def test_scrolling_to_the_top_loads_older_messages(chat):
    app, _ = chat
    general = room(app)
    first = general.messages.value[0]["id"]
    app.get("messages").scroll_to_start()  # como si el usuario subiera del todo
    app.wait(until=lambda: len(general.messages.value) == 100)
    assert general.messages.value[50]["id"] == first
    assert not general.loading.value


def test_sending_a_message(chat):
    app, srv = chat
    app.find("TextField", id="draft").type("hola **mundo**")
    app.find("Button", text="Enviar").click()
    general = room(app)
    app.wait(until=lambda: general.messages.value[-1]["text"] == "hola **mundo**")
    assert srv.server.messages["general"][-1]["author"] == "yo"
    assert app.find("TextField", id="draft").value == ""


def test_unread_counters_and_switching_rooms(chat):
    app, srv = chat
    python = room(app, "python")
    srv.say("python", "uno")
    srv.say("python", "dos")
    app.wait(until=lambda: python.unread.value == 2)
    assert "2" in app.texts()
    app.find("Row", label="Python").click()
    assert python.unread.value == 0
    assert app.get("current") == "python"
    app.wait(until=lambda: any("dos" in t for t in app.texts()))


def test_new_messages_while_reading_older_ones(chat):
    app, srv = chat
    app.get("messages").scroll_to_start()
    app.wait(until=lambda: not app.get("at_bottom") and not room(app).loading.value)
    srv.say("general", "mientras leías")
    app.wait(until=lambda: app.get("new_below") == 1)
    assert room(app).unread.value == 1
    app.find("Button", text="1 mensaje nuevo ↓").click()
    app.wait(until=lambda: app.get("at_bottom"))
    assert app.get("new_below") == 0 and room(app).unread.value == 0


def test_notifies_only_when_the_window_is_not_active(chat):
    app, srv = chat
    before = len(app.notifications())
    srv.say("general", "con la ventana activa")
    app.wait(until=lambda: room(app).messages.value[-1]["text"] == "con la ventana activa")
    assert len(app.notifications()) == before
    app.namespace["active"].value = False  # lo que hace on:deactivate
    srv.say("random", "¿estás?", author="Luis")
    app.wait(until=lambda: len(app.notifications()) == before + 1)
    assert app.notifications()[-1] == {"title": "Luis · Aleatorio", "message": "¿estás?"}


def test_reconnects_and_recovers_missed_messages(chat):
    app, srv = chat
    client = app.get("client")
    srv.stop()
    app.wait(until=lambda: client.status.value != "online")
    assert any("Conectando" in t or "Sin conexión" in t for t in app.texts())
    # Mientras tanto la conversación sigue en el servidor.
    missed = [srv.server.new_message("general", author="Marta", text=f"perdido {i}") for i in range(3)]
    srv.server.messages["general"].extend(missed)
    srv.start()  # mismo puerto
    app.wait(timeout=10, until=lambda: client.status.value == "online" and room(app).last_id == missed[-1]["id"])
    texts = [m["text"] for m in room(app).messages.value[-3:]]
    assert texts == ["perdido 0", "perdido 1", "perdido 2"]


def test_arabic_mirrors_the_layout(chat):
    app, _ = chat
    from janelkit_i18n import i18n

    app.find("Select").choose("العربية")
    assert i18n.rtl
    assert "دردشة" in app.texts()
    i18n.set("es")
