// shoovy-sentinel — a gentle 24/7 availability probe for shoovy.wtf.
//
// The whole rank-1 goal is gated on Layer 0: is the site serving at all? The
// site is a sick Railway deployment (429 "rate limited" / 502), so the correct
// instrument is NOT the 15s market collector (that is the multi-poller
// anti-pattern) but one slow, single-request probe that measures availability
// without ever hammering.
//
// One GET /api/stocks every interval (default 5 min), 60s timeout (cold start
// is ~40s), a single request, NEVER a retry on failure. It appends one JSONL
// line per probe to avail.jsonl. When status flips 429/502 -> 200 the site is
// back and the farming stage can begin. Pure Go stdlib, so it cross-compiles
// to riscv64 static for the Claw with zero dependencies.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

const url = "https://shoovy.wtf/api/stocks"

type sample struct {
	Ts     int64  `json:"ts"`
	ISO    string `json:"iso"`
	Status int    `json:"status"` // HTTP code, or 0 on transport error
	Ms     int64  `json:"ms"`
	Up     bool   `json:"up"` // 200 with a parseable body
	Note   string `json:"note,omitempty"`
}

func probe(client *http.Client) sample {
	t0 := time.Now()
	s := sample{Ts: t0.Unix(), ISO: t0.UTC().Format(time.RFC3339)}
	resp, err := client.Get(url)
	s.Ms = time.Since(t0).Milliseconds()
	if err != nil {
		s.Note = "transport: " + err.Error()
		return s
	}
	defer resp.Body.Close()
	s.Status = resp.StatusCode
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode == 200 {
		var j map[string]any
		if json.Unmarshal(body, &j) == nil {
			s.Up = true
			if q, ok := j["quotes"].([]any); ok {
				s.Note = strconv.Itoa(len(q)) + " tickers"
			}
		} else {
			s.Note = "200 but unparseable body"
		}
	} else {
		// keep the tiny degradation body (e.g. "rate limited"), trimmed
		n := len(body)
		if n > 60 {
			n = 60
		}
		s.Note = string(body[:n])
	}
	return s
}

func main() {
	interval := 5 * time.Minute
	if len(os.Args) > 1 {
		if n, err := strconv.Atoi(os.Args[1]); err == nil && n >= 30 {
			interval = time.Duration(n) * time.Second
		}
	}
	out := "avail.jsonl"
	if v := os.Getenv("SENTINEL_OUT"); v != "" {
		out = v
	}
	// Timeout > cold start (~40s). One client, reused; no retry, ever.
	client := &http.Client{Timeout: 60 * time.Second}

	for {
		s := probe(client)
		line, _ := json.Marshal(s)
		f, err := os.OpenFile(out, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err == nil {
			f.Write(append(line, '\n'))
			f.Close()
		}
		fmt.Println(string(line))
		time.Sleep(interval)
	}
}
