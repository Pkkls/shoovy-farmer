// apimap — read-only sweep of the shoovy.wtf API surface through the one shared
// client, so the whole pass is paced by a single global budget instead of N
// bursting processes. It GETs the info endpoints, saves each raw body, and
// prints one classification line per endpoint. It NEVER invokes an action:
// no POST/DELETE to play/buy/trade/claim/tts/shocker paths. Method surface is
// probed only with a harmless PUT (405 lists methods) on a safe allowlist.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	shoovyclient "shoovyclient"
)

// GET-only info endpoints. name -> path. Action sub-paths are deliberately absent.
var endpoints = [][2]string{
	{"me", "/api/me"}, {"stats", "/api/stats"}, {"leaderboard", "/api/leaderboard"},
	{"leaderboards", "/api/leaderboards"}, {"user", "/api/user"}, {"feed", "/api/feed"},
	{"daily", "/api/daily"}, {"fishing", "/api/fishing"}, {"stocks", "/api/stocks"},
	{"predictions", "/api/predictions"}, {"games_info", "/api/games/info"},
	{"casino_lobby", "/api/casino/lobby"}, {"rakeback", "/api/rakeback"},
	{"business", "/api/business"}, {"crime", "/api/crime"}, {"shop", "/api/shop"},
	{"raffles", "/api/raffles"}, {"updates", "/api/updates"}, {"suggestions", "/api/suggestions"},
}

// PUT is non-mutating (returns 405 listing real methods). Safe allowlist only —
// never tts/shocker, whose servers might act on any verb.
var methodProbe = []string{"/api/stocks/trade", "/api/business", "/api/predictions", "/api/raffles"}

var econRe = regexp.MustCompile(`(?i)"(balance|rate|rate_pct|fee|fee_pct|payout|rtp|multiplier|cooldown|decay|price|amount|reward|stake|wagered|leaderboard|quotes|depth)"`)

func topKeys(body []byte) (string, string) {
	var m map[string]json.RawMessage
	if json.Unmarshal(body, &m) != nil {
		return "(non-object)", ""
	}
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	if len(keys) > 10 {
		keys = keys[:10]
	}
	ch := ""
	if v, ok := m["channel"]; ok {
		ch = strings.Trim(string(v), `"`)
	}
	return strings.Join(keys, ","), ch
}

func main() {
	outDir := "data/study/raw"
	if len(os.Args) > 1 {
		outDir = os.Args[1]
	}
	os.MkdirAll(outDir, 0755)

	c := shoovyclient.New(shoovyclient.Options{LogPath: filepath.Join(outDir, "..", "requests_apimap.jsonl")})

	fmt.Println("== GET sweep ==")
	pub, gated, down, gone := 0, 0, 0, 0
	for _, e := range endpoints {
		name, path := e[0], e[1]
		r := c.Get(path)
		if r.Status == 200 {
			os.WriteFile(filepath.Join(outDir, "api_"+name+".json"), r.Body, 0644)
		}
		keys, ch := topKeys(r.Body)
		econ := econRe.Match(r.Body)
		switch {
		case r.Status == 200:
			pub++
		case r.Status == 401 || r.Status == 403:
			gated++
		case r.Status == 404:
			gone++
		case r.Status == 429 || r.Status == 502 || r.Status == 0:
			down++
		}
		fmt.Printf("%-14s %-24s %3d %5dms econ=%-5v ch=%-8s %s\n",
			name, path, r.Status, r.Ms, econ, ch, keys)
		if r.Degraded {
			fmt.Println("  ! backend degraded, remaining calls will pace out; stop if this persists")
		}
	}

	fmt.Println("== method surface (harmless PUT -> 405 lists real methods) ==")
	for _, p := range methodProbe {
		r := c.Do("PUT", p, nil)
		note := strings.ReplaceAll(string(r.Body), "\n", " ")
		if len(note) > 90 {
			note = note[:90]
		}
		fmt.Printf("PUT %-22s %3d  %s\n", p, r.Status, note)
	}

	fmt.Printf("== summary: public=%d gated=%d gone=%d down=%d ==\n", pub, gated, gone, down)
}
