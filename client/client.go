// Package shoovyclient is the one HTTP client every shoovy.wtf request should go
// through. The binding constraint on this target is availability, not request
// budget: the Railway backend cold-starts (~40 s), rate-limits with a 12-byte
// 429 "rate limited", and the longest usable streak observed is ~2 requests.
// FINDINGS.md's conclusion was "one shared client with one global budget" — this
// is that client.
//
// What it optimizes:
//   - Serialization: at most one request in flight, so three callers (sentinel,
//     collector, farmer) can't each open an independent stream and burst.
//   - A global minimum gap between requests (token-bucket-lite), so a loop never
//     turns into the recon burst that got us rate-limited.
//   - 429/502 awareness with exponential backoff, and it NEVER retries a single
//     call into a 429 — the caller gets the status, and the client paces the
//     NEXT call past the backoff. Pressure never fixes a sick backend.
//   - A 60 s timeout (> cold start) so first contact after idle doesn't fail.
//   - An optional per-path TTL cache, because availability is scarce: don't
//     spend a request on something you just fetched.
//   - One JSONL audit line per request, so every call is accountable.
//
// Pure stdlib, so it cross-compiles static to the Claw's riscv64 with no deps.
package shoovyclient

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const Base = "https://shoovy.wtf"

type Options struct {
	MinGap      time.Duration // minimum spacing between requests (default 3s)
	Timeout     time.Duration // per-request timeout (default 60s, > cold start)
	BackoffBase time.Duration // first backoff after a 429/502 (default 30s)
	BackoffMax  time.Duration // backoff ceiling (default 30m)
	CacheTTL    time.Duration // 0 disables the cache
	LogPath     string        // JSONL audit trail; "" disables logging
	UserAgent   string        // "" sends a neutral UA (a plain stdlib client passes)

	// Credentials, only for session-gated endpoints. Leave empty for public reads.
	Bearer        string // kick session_token, URL-decoded -> Authorization: Bearer
	ShoovySession string // shoovy.wtf `session` cookie value
}

type Result struct {
	Status int
	Body   []byte
	Ms     int64
	Cached bool
	// Degraded is true when this call was served/blocked under active backoff,
	// i.e. the backend is currently considered unhealthy.
	Degraded bool
}

type cacheEntry struct {
	at   time.Time
	res  Result
}

type Client struct {
	o    Options
	http *http.Client

	mu           sync.Mutex // serializes requests AND guards the fields below
	lastAt       time.Time
	backoff      time.Duration
	degradedTill time.Time
	cache        map[string]cacheEntry
}

func New(o Options) *Client {
	if o.MinGap == 0 {
		o.MinGap = 3 * time.Second
	}
	if o.Timeout == 0 {
		o.Timeout = 60 * time.Second
	}
	if o.BackoffBase == 0 {
		o.BackoffBase = 30 * time.Second
	}
	if o.BackoffMax == 0 {
		o.BackoffMax = 30 * time.Minute
	}
	return &Client{
		o:     o,
		http:  &http.Client{Timeout: o.Timeout},
		cache: map[string]cacheEntry{},
	}
}

// Get is the common case: a GET on a shoovy path (with or without leading /api).
func (c *Client) Get(path string) Result { return c.Do("GET", path, nil) }

// Do runs one request through the global gate. It never retries; on a 429/502
// it records backoff and returns the status so the caller can decide. The gate
// enforces: one-at-a-time, min-gap spacing, and waiting out any active backoff.
func (c *Client) Do(method, path string, body []byte) Result {
	url := path
	if strings.HasPrefix(path, "/") {
		url = Base + path
	}
	key := method + " " + url

	// Serialize everything. The lock is held across the network call on
	// purpose: one request in flight at a time is the whole point.
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.o.CacheTTL > 0 {
		if e, ok := c.cache[key]; ok && time.Since(e.at) < c.o.CacheTTL {
			r := e.res
			r.Cached = true
			c.log(method, url, r)
			return r
		}
	}

	// Pace: honor min-gap, and wait out any active backoff window.
	now := time.Now()
	wait := c.o.MinGap - now.Sub(c.lastAt)
	if d := c.degradedTill.Sub(now); d > wait {
		wait = d
	}
	if wait > 0 {
		time.Sleep(wait)
	}

	t0 := time.Now()
	c.lastAt = t0
	res := Result{Degraded: t0.Before(c.degradedTill)}

	var rdr io.Reader
	if body != nil {
		rdr = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, url, rdr)
	if err != nil {
		res.Ms = time.Since(t0).Milliseconds()
		c.log(method, url, res)
		return res
	}
	req.Header.Set("Accept", "application/json")
	if c.o.UserAgent != "" {
		req.Header.Set("User-Agent", c.o.UserAgent)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.o.Bearer != "" {
		req.Header.Set("Authorization", "Bearer "+c.o.Bearer)
	}
	if c.o.ShoovySession != "" {
		req.Header.Set("Cookie", "session="+c.o.ShoovySession)
	}

	resp, err := c.http.Do(req)
	res.Ms = time.Since(t0).Milliseconds()
	if err != nil {
		// Transport error (timeout, reset): treat like a soft outage, back off.
		c.enterBackoff()
		res.Degraded = true
		c.log(method, url, res)
		return res
	}
	res.Body, _ = io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	resp.Body.Close()
	res.Status = resp.StatusCode

	switch {
	case resp.StatusCode == 200:
		c.backoff = 0
		c.degradedTill = time.Time{}
		if c.o.CacheTTL > 0 {
			c.cache[key] = cacheEntry{at: time.Now(), res: res}
		}
	case resp.StatusCode == 429 || resp.StatusCode == 502 || resp.StatusCode == 503:
		// The sick-backend signature. Back off; do NOT retry here.
		c.enterBackoff()
		res.Degraded = true
	}
	c.log(method, url, res)
	return res
}

func (c *Client) enterBackoff() {
	if c.backoff == 0 {
		c.backoff = c.o.BackoffBase
	} else {
		c.backoff *= 2
		if c.backoff > c.o.BackoffMax {
			c.backoff = c.o.BackoffMax
		}
	}
	c.degradedTill = time.Now().Add(c.backoff)
}

// Healthy reports whether the client currently believes the backend is servable
// (no active backoff). Callers can skip a whole pass when it's false.
func (c *Client) Healthy() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return time.Now().After(c.degradedTill)
}

func (c *Client) log(method, url string, r Result) {
	if c.o.LogPath == "" {
		return
	}
	note := ""
	if r.Status != 0 && r.Status != 200 {
		n := r.Body
		if len(n) > 60 {
			n = n[:60]
		}
		note = string(n)
	}
	line, _ := json.Marshal(map[string]any{
		"ts": time.Now().Unix(), "iso": time.Now().UTC().Format(time.RFC3339),
		"method": method, "url": url, "status": r.Status, "ms": r.Ms,
		"cached": r.Cached, "degraded": r.Degraded, "note": note,
	})
	f, err := os.OpenFile(c.o.LogPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err == nil {
		f.Write(append(line, '\n'))
		f.Close()
	}
}
