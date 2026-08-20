package shoovyclient

import (
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

// The client's whole job is discipline under a flaky backend. The test pins the
// three behaviours that matter: pacing, no-retry-into-429 with backoff, and the
// cache saving a request.
func TestClientDiscipline(t *testing.T) {
	var hits int32
	var mode atomic.Value // "ok" or "429"
	mode.Store("ok")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		if mode.Load() == "429" {
			w.WriteHeader(429)
			w.Write([]byte("rate limited"))
			return
		}
		w.WriteHeader(200)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	c := New(Options{MinGap: 60 * time.Millisecond, BackoffBase: 80 * time.Millisecond, CacheTTL: time.Second})

	// 1. min-gap: two uncached calls are spaced by at least MinGap.
	t0 := time.Now()
	if r := c.Do("GET", srv.URL+"/a", nil); r.Status != 200 {
		t.Fatalf("first call status %d", r.Status)
	}
	c.Do("GET", srv.URL+"/b", nil)
	if d := time.Since(t0); d < 60*time.Millisecond {
		t.Fatalf("min-gap not enforced: %v", d)
	}

	// 2. cache: repeat of the SAME path within TTL is served from cache, no hit.
	before := atomic.LoadInt32(&hits)
	r := c.Do("GET", srv.URL+"/a", nil)
	if !r.Cached || r.Status != 200 {
		t.Fatalf("expected cached 200, got cached=%v status=%d", r.Cached, r.Status)
	}
	if atomic.LoadInt32(&hits) != before {
		t.Fatalf("cache still hit the server")
	}

	// 3. 429 -> degraded, backoff set, NOT retried; a 200 later clears it.
	mode.Store("429")
	r = c.Do("GET", srv.URL+"/c", nil)
	if r.Status != 429 || !r.Degraded {
		t.Fatalf("expected degraded 429, got status=%d degraded=%v", r.Status, r.Degraded)
	}
	if c.Healthy() {
		t.Fatalf("client should report unhealthy after 429")
	}
	// The next call must WAIT out the backoff (never retry instantly). Measure it.
	mode.Store("ok")
	t1 := time.Now()
	r = c.Do("GET", srv.URL+"/d", nil)
	if d := time.Since(t1); d < 60*time.Millisecond {
		t.Fatalf("backoff not waited before next call: %v", d)
	}
	if r.Status != 200 {
		t.Fatalf("recovery call status %d", r.Status)
	}
	if !c.Healthy() {
		t.Fatalf("client should be healthy after a 200")
	}
}
