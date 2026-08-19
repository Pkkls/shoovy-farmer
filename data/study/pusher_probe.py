"""Does the legacy Pusher chat transport still accept a server client?

Route A of the chat-reception plan rests on inherited knowledge, and Kick has
already moved this transport once. This settles whether it is still live, from a
plain server socket with no browser and no TLS impersonation.

Touches Kick/Pusher only, never shoovy.wtf, so it works while the game site is
down. Listens only: it subscribes and reads, and posts nothing.

    python pusher_probe.py <chatroom_id> [seconds]
"""
import asyncio, json, sys, time

import websockets

# Public client key, the one kick.com's own web client presents. Not a secret:
# it is served to every browser that loads the site.
APP_KEY = "32cbd69e4b950bf97679"
URL = (f"wss://ws-us2.pusher.com/app/{APP_KEY}"
       "?protocol=7&client=js&version=8.5.0&flash=false")

# The gateway uses chatrooms.<id>.v2; the legacy transport used chatroom.<id>.
# Which one this endpoint still honours is exactly what is being tested.
CHANNEL_FORMS = ["chatrooms.{id}.v2", "chatroom.{id}"]


async def probe(chatroom_id, seconds):
    verdict = {"connected": False, "subscribed": [], "rejected": [],
               "events": [], "error": None}
    try:
        async with websockets.connect(URL, open_timeout=20) as ws:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            print("<-", hello.get("event"), str(hello.get("data"))[:120])
            if hello.get("event") != "pusher:connection_established":
                verdict["error"] = f"unexpected hello: {hello.get('event')}"
                return verdict
            verdict["connected"] = True

            for form in CHANNEL_FORMS:
                chan = form.format(id=chatroom_id)
                await ws.send(json.dumps({"event": "pusher:subscribe",
                                          "data": {"auth": "", "channel": chan}}))
                print("->", "subscribe", chan)

            deadline = time.time() + seconds
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(),
                                                 timeout=max(1, deadline - time.time()))
                except asyncio.TimeoutError:
                    break
                msg = json.loads(raw)
                ev, chan = msg.get("event", ""), msg.get("channel", "")
                if ev == "pusher_internal:subscription_succeeded":
                    verdict["subscribed"].append(chan)
                    print("<- SUBSCRIBED", chan)
                elif ev in ("pusher:error", "pusher_internal:subscription_error"):
                    verdict["rejected"].append({"channel": chan,
                                                "data": msg.get("data")})
                    print("<- REJECTED", chan, str(msg.get("data"))[:160])
                elif ev.startswith("pusher:"):
                    print("<-", ev)
                else:
                    verdict["events"].append({"event": ev, "channel": chan})
                    print(f"<- EVENT {ev} on {chan}")
    except Exception as e:
        verdict["error"] = f"{type(e).__name__}: {e}"
        print("ERREUR:", verdict["error"])
    return verdict


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    chatroom_id = sys.argv[1]
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    print(f"chatroom {chatroom_id}, ecoute {seconds}s\n")
    v = asyncio.run(probe(chatroom_id, seconds))
    print("\nverdict:", json.dumps(v, indent=2)[:1500])
    return 0 if v["connected"] else 1


if __name__ == "__main__":
    sys.exit(main())
