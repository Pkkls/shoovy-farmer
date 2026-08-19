"""Listen to the channel's chat and write everything to chat.jsonl.

The point is not to talk. It is that several hundred people are playing this
game in public and every payout is announced in chat, so the chat is a free
firehose of measurements we would otherwise have to buy with requests and with
risk to our own accounts. Catch values, chest sizes, frenzy and boom frequency,
cooldowns implied by how often a given player can repeat a command: all of it is
observable without sending anything.

It also runs while shoovy.wtf is down, because it only touches Kick.

Listens only. Never posts. Reconnects on drop.

    python chat_listen.py [chatroom_id]
"""
import asyncio, json, os, sys, time

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "chat.jsonl")

# Public client key, the one kick.com's own web client presents to every browser.
APP_KEY = "32cbd69e4b950bf97679"
URL = (f"wss://ws-us2.pusher.com/app/{APP_KEY}"
       "?protocol=7&client=js&version=8.5.0&flash=false")
CHATROOM = "29834074"

PING_EVERY = 25.0


def record(kind, payload):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": int(time.time()), "kind": kind,
                            "payload": payload}, ensure_ascii=False) + "\n")


async def pump(chatroom):
    async with websockets.connect(URL, open_timeout=30, close_timeout=5) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if hello.get("event") != "pusher:connection_established":
            raise RuntimeError(f"hello inattendu: {hello.get('event')}")
        await ws.send(json.dumps({"event": "pusher:subscribe",
                                  "data": {"auth": "",
                                           "channel": f"chatrooms.{chatroom}.v2"}}))
        record("connected", {"chatroom": chatroom})
        print(f"connecte, chatroom {chatroom}", flush=True)

        last_ping = time.time()
        while True:
            timeout = max(1.0, PING_EVERY - (time.time() - last_ping))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                await ws.send(json.dumps({"event": "pusher:ping", "data": {}}))
                last_ping = time.time()
                continue

            msg = json.loads(raw)
            ev = msg.get("event", "")
            if ev.startswith("pusher"):
                continue

            data = msg.get("data")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except ValueError:
                    pass

            if ev.endswith("ChatMessageEvent") and isinstance(data, dict):
                sender = (data.get("sender") or {}).get("username")
                record("msg", {"event": ev, "sender": sender,
                               "content": data.get("content"),
                               "type": data.get("type"),
                               "created_at": data.get("created_at")})
            else:
                # Everything else is kept whole: chests, gifts, moderation and
                # whatever else the channel emits are worth having verbatim
                # rather than guessed at now.
                record("other", {"event": ev, "data": data})


async def main():
    chatroom = sys.argv[1] if len(sys.argv) > 1 else CHATROOM
    backoff = 5
    while True:
        try:
            await pump(chatroom)
        except Exception as e:
            record("disconnect", {"error": f"{type(e).__name__}: {e}"})
            print(f"deconnecte ({type(e).__name__}), retry dans {backoff}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)
        else:
            backoff = 5


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
