<script lang="python">
# Reto 4: cliente de chat por WebSocket. Ver ../HALLAZGOS.md.
import os
import re
import time
from pathlib import Path

from fluxui import computed, i18n, notify, on_mount, ref, spawn, state, t
from components.Message import Message
from services.chat import ChatClient

i18n.load(Path(__file__).parent / "locales")
i18n.set(os.environ.get("CHAT_LANG", "es"))

URL = os.environ.get("CHAT_URL", "ws://127.0.0.1:8765")
BASE = URL.replace("ws://", "http://").replace("wss://", "https://")
LANGUAGES = [{"label": "Español", "value": "es"}, {"label": "English", "value": "en"}, {"label": "العربية", "value": "ar"}]

client = ChatClient(URL, os.environ.get("CHAT_USER", "yo"))
current = state("general")
draft = state("")
language = state(i18n.language)
active = state(True)  # la ventana está en primer plano
at_bottom = state(True)  # la lista de mensajes está abajo del todo
new_below = state(0)  # mensajes nuevos que llegaron estando más arriba
messages = ref()
last_notice = {"at": 0.0}


@computed
def room():
    return next((r for r in client.room_list.value if r.id == current.value), None)


def on_message(r, msg):
    mine = msg["author"] == client.user
    here = r.id == current.peek()
    if here and not at_bottom.peek() and not mine:
        new_below.value += 1
    if not mine and not (here and active.peek() and at_bottom.peek()):
        r.unread.value += 1
        if not active.peek() and time.monotonic() - last_notice["at"] > 3:  # sin inundar el sistema
            last_notice["at"] = time.monotonic()
            notify(f"{msg['author']} · {r.name}", re.sub(r"[*_`]", "", msg["text"])[:120], on_click=lambda: select(r.id))
    if not here or at_bottom.peek():
        r.trim()


client.on_message = on_message


@on_mount
def connect():
    spawn(client.run())  # vive mientras viva la ventana; se cancela al cerrarla


def select(room_id):
    current.value = room_id
    new_below.value = 0
    mark_read()


def mark_read():
    r = room.value
    if r is not None and active.peek() and at_bottom.peek():
        r.unread.value = 0


def on_scroll(info):
    at_bottom.value = bool(info["bottom"])
    if at_bottom.peek():
        new_below.value = 0
        mark_read()


def on_activate():
    active.value = True
    mark_read()


def to_bottom():
    messages.scroll_to_end()
    new_below.value = 0


def send():
    text = draft.value.strip()
    if text and room.value is not None:
        client.send(room.value, text)
        draft.value = ""
        to_bottom()


def change_language(code):
    language.value = code
    i18n.set(code)
</script>

<Window title={t("title")} width={900} height={640} minWidth={560} minHeight={400}
        on:activate={on_activate} on:deactivate={active = False}>
  <Row class="app">
    <Column class="sidebar">
      <Text class="brand">{t("title")}</Text>
      {#each client.room_list.value as r (r.id)}
        <Row class={"room selected" if r.id == current else "room"} on:click={select(r.id)} label={r.name}>
          <Text flex={1}># {r.name}</Text>
          {#if r.unread.value}
            <Text class="badge">{r.unread.value}</Text>
          {/if}
        </Row>
      {/each}
      <Spacer />
      <Select value={language} options={LANGUAGES} on:change={change_language} />
    </Column>

    <Column class="main">
      {#if client.status.value != "online"}
        <Row class="banner" transition:fade>
          <Text>{t("connecting") if client.status.value == "connecting" else t("offline")}</Text>
        </Row>
      {/if}

      {#if room is not None}
        <Row class="header">
          <Text class="room-title"># {room.name}</Text>
          <Spacer />
          {#if room.loading.value}
            <Text class="muted">{t("loading")}</Text>
          {:else if room.complete.value}
            <Text class="muted">{t("start")}</Text>
          {/if}
        </Row>

        {#key current}
          <List id="messages" follow ref={messages} class="messages"
                on:top={client.load_history(room)} on:scroll={on_scroll}>
            {#each room.messages.value as m (m["id"])}
              <Message msg={m} mine={m["author"] == client.user} base={BASE}
                       on:react={lambda id, e: client.react(room, id, e)} />
            {/each}
          </List>
        {/key}

        {#if new_below}
          <Row class="jump">
            <Spacer />
            <Button variant="primary" on:click={to_bottom}>{t("new", n=new_below)} ↓</Button>
            <Spacer />
          </Row>
        {/if}

        <Text class="typing">{t("typing", user=room.typing.value) if room.typing.value else " "}</Text>
        <Row class="composer">
          <TextField id="draft" bind:value={draft} placeholder={t("placeholder")} flex={1}
                     on:submit={send} on:input={client.typing(room)} />
          <Button variant="primary" on:click={send} enabled={bool(draft.strip())}>{t("send")}</Button>
        </Row>
      {/if}
    </Column>
  </Row>
</Window>

<style>
.app { gap: 0; }
.sidebar { width: 220px; align-self: stretch; background: var(--surface-alt); padding: 12px; gap: 4px; }
.brand { font-size: var(--font-size-lg); font-weight: 600; padding: 4px 8px 12px 8px; }
.room { padding: 6px 8px; border-radius: var(--radius-sm); gap: 6px; align-items: center; }
.selected { background: var(--surface); }
.badge { background: var(--primary); color: var(--on-primary); border-radius: 9px; padding: 0 6px; font-size: var(--font-size-sm); }
.main { flex: 1; align-self: stretch; gap: 0; }
.banner { background: var(--danger); padding: 6px 12px; }
.header { padding: 10px 12px; border-color: var(--border); align-items: center; }
.room-title { font-weight: 600; font-size: var(--font-size-lg); }
.muted { color: var(--text-muted); }
.messages { padding: 4px 0; gap: 2px; }
.jump { padding: 4px; }
.typing { color: var(--text-muted); font-size: var(--font-size-sm); padding: 0 12px; font-style: italic; }
.composer { gap: 8px; padding: 8px 12px 12px 12px; }
</style>
