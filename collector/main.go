// collector — continuously logs the shoovy.wtf virtual market for backtesting.
// GET /api/stocks (public, no auth) every 15s.
// Writes 2 append-only JSONL files: quotes.jsonl (one line per poll) and news.jsonl
// (each labelled market event with amount+timestamp, deduped). Pure stdlib.
package main

import (
	"bufio"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

const (
	apiURL    = "https://shoovy.wtf/api/stocks"
	userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
	pollEvery = 15 * time.Second
)

type quote struct {
	Symbol    string  `json:"symbol"`
	Name      string  `json:"name"`
	Price     float64 `json:"price"`
	ChangePct float64 `json:"change_pct"`
	DayLow    float64 `json:"day_low"`
	DayHigh   float64 `json:"day_high"`
	Volume    int64   `json:"volume"`
}

type newsItem struct {
	Symbol    string `json:"symbol"`
	Headline  string `json:"headline"`
	CreatedAt int64  `json:"created_at"`
}

type stocksResp struct {
	Quotes         []quote    `json:"quotes"`
	News           []newsItem `json:"news"`
	FeePct         float64    `json:"fee_pct"`
	Depth          float64    `json:"depth"`
	TradingEnabled bool       `json:"trading_enabled"`
}

func dir() string {
	if p := os.Getenv("COLLECTOR_DIR"); p != "" {
		return p
	}
	exe, _ := os.Executable()
	return filepath.Dir(exe)
}

func newsKey(n newsItem) string {
	return n.Symbol + "|" + itoa(n.CreatedAt) + "|" + n.Headline
}

func itoa(i int64) string {
	return time.Unix(i, 0).UTC().Format("20060102T150405") // clef stable, lisible
}

// seedSeen rebuilds the set of already-logged news (dedup survives restarts).
func seedSeen(path string) map[string]bool {
	seen := map[string]bool{}
	f, err := os.Open(path)
	if err != nil {
		return seen
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		var n newsItem
		if json.Unmarshal(sc.Bytes(), &n) == nil {
			seen[newsKey(n)] = true
		}
	}
	return seen
}

func appendLine(path string, v any) error {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	_, err = f.Write(append(b, '\n'))
	return err
}

func main() {
	log.SetFlags(log.LstdFlags)
	base := dir()
	quotesPath := filepath.Join(base, "quotes.jsonl")
	newsPath := filepath.Join(base, "news.jsonl")
	seen := seedSeen(newsPath)
	log.Printf("collector — polling %s every %s | %d news already known", apiURL, pollEvery, len(seen))

	client := &http.Client{Timeout: 20 * time.Second}
	for {
		poll(client, quotesPath, newsPath, seen)
		time.Sleep(pollEvery)
	}
}

func poll(client *http.Client, quotesPath, newsPath string, seen map[string]bool) {
	req, err := http.NewRequest(http.MethodGet, apiURL, nil)
	if err != nil {
		log.Printf("req: %v", err)
		return
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("get: %v", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		log.Printf("http %d", resp.StatusCode)
		return
	}
	var sr stocksResp
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		log.Printf("decode: %v", err)
		return
	}

	// timestamp = local clock.
	
	ts := time.Now().Unix()
	snap := map[string]any{"ts": ts, "quotes": sr.Quotes}
	if err := appendLine(quotesPath, snap); err != nil {
		log.Printf("write quotes: %v", err)
	}

	fresh := 0
	for _, n := range sr.News {
		k := newsKey(n)
		if seen[k] {
			continue
		}
		seen[k] = true
		if err := appendLine(newsPath, n); err == nil {
			fresh++
		}
	}
	if fresh > 0 {
		log.Printf("tick ok | %d quotes | +%d news", len(sr.Quotes), fresh)
	}
}
