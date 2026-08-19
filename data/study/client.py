"""Single logging HTTP client for the whole study.

Every request made against shoovy.wtf goes through here, and every request is
appended to requests.jsonl: method, url, request headers (secrets redacted),
status, response headers, size, duration. That file is the audit trail.

Requests are serialized behind one global gap so two callers can never burst.

    from client import get, post, LOG
"""
import json, os, threading, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "requests.jsonl")
BASE = "https://shoovy.wtf"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# ponytail: fixed gap, not a token bucket. Calibrate once the limiter's real
# window is known; the serialization point is already here either way.
GAP_SECONDS = 30.0

# Response headers worth keeping; the rest is Cloudflare noise.
KEEP_HEADERS = ("content-type", "content-length", "retry-after", "server",
                "x-railway-edge", "cf-cache-status", "set-cookie",
                "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")

_lock = threading.Lock()
_last = [0.0]


def _redact(headers):
    """Never let a session value reach the log."""
    out = {}
    for k, v in headers.items():
        if k.lower() == "cookie":
            names = [c.split("=")[0].strip() for c in v.split(";")]
            out[k] = "<cookies: " + ",".join(names) + ">"
        else:
            out[k] = v
    return out


BODY_CAP = 262144  # 256 KB: every API response fits; only big HTML pages truncate


def _body_for_log(raw):
    """Full response body in the log. JSON is parsed so the log stays queryable;
    anything else is kept as text, truncated past BODY_CAP (raw/ has the whole
    thing anyway)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"_binary": len(raw)}
    stripped = text.lstrip()
    if stripped[:1] in ("{", "["):
        try:
            return json.loads(text)
        except ValueError:
            pass
    if len(text) > BODY_CAP:
        return text[:BODY_CAP] + f"\n...[tronque, {len(text)} octets au total]"
    return text


def request(method, path, body=None, headers=None, timeout=70):
    url = path if path.startswith("http") else BASE + path
    hdrs = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}
    if headers:
        hdrs.update(headers)
    if body is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"

    data = body.encode() if isinstance(body, str) else body

    with _lock:
        wait = GAP_SECONDS - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)

        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw, status, rh = r.read(), r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw, status, rh = e.read(), e.code, dict(e.headers)
        except Exception as e:
            _last[0] = time.time()
            entry = {"ts": int(time.time()), "method": method, "url": url,
                     "req_headers": _redact(hdrs), "error": f"{type(e).__name__}: {e}",
                     "secs": round(time.time() - t0, 2)}
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            raise
        dt = time.time() - t0
        _last[0] = time.time()

    enc = rh.get("Content-Encoding", "")
    if enc == "gzip":
        import gzip
        raw = gzip.decompress(raw)
    elif enc == "deflate":
        import zlib
        raw = zlib.decompress(raw, -zlib.MAX_WBITS)

    entry = {
        "ts": int(time.time()), "method": method, "url": url,
        "req_headers": _redact(hdrs), "http": status,
        "resp_headers": {k: v for k, v in rh.items() if k.lower() in KEEP_HEADERS},
        "bytes": len(raw), "secs": round(dt, 2),
        "body": _body_for_log(raw),
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return status, raw, rh


def get(path, **kw):
    return request("GET", path, **kw)


def post(path, body=None, **kw):
    return request("POST", path, body=body, **kw)
