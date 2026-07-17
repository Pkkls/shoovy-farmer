// fisher — casts "!fish" in Kick chat, respecting the real in-game cooldown, in an
// ASYNCHRONOUS way (per-account jitter + stagger) with strict anti-spam guards.
//
// Past bug (2026-07-17): the old'logic did send()+sleep(5s) when
// /api/fishing returned remaining=0. When a cast fails (BANNED/feature off), no server
// cooldown starts -> remaining stays 0 -> a burst every 5s -> accounts banned. FIXED:
//  - absolute rate floor (never two posts closer than hard_floor_seconds), whatever the logic
//  - after a successful cast: wait the FULL cooldown (cooldown_min), never less
//  - on failure/ban: long backoff + loud log (no fast retry)
//  - if fishing enabled=false: do not post at all
//  - random jitter + startup stagger: accounts never post at the same time
//  - the main account is excluded via the "workers" list
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"hash/fnv"
	"log"
	"math/rand"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	http "github.com/bogdanfinn/fhttp"

	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

const userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"

// ── config.json ──────────────────────────────────────────────────────────────
type fishConfig struct {
	Channel                string   `json:"channel"`
	ChatroomID             string   `json:"chatroom_id"`
	Message                string   `json:"message"`
	Workers                []string `json:"workers"`                  // accounts allowed to fish (main account excluded)
	HardFloorSeconds       int      `json:"hard_floor_seconds"`       // absolute min between two posts of an account
	JitterSeconds          int      `json:"jitter_seconds"`           // random added to each wait
	StaggerMaxSeconds      int      `json:"stagger_max_seconds"`      // random startup offset
	ErrorBackoffMinutes    int      `json:"error_backoff_minutes"`    // wait after failure/ban
	DisabledRecheckMinutes int      `json:"disabled_recheck_minutes"` // recheck when fishing is off
	FallbackIntervalMin    int      `json:"fallback_interval_minutes"` // if /api/fishing is unreachable
}

func configPath() string {
	if p := os.Getenv("FISHD_CONFIG"); p != "" {
		return p
	}
	exe, _ := os.Executable()
	return filepath.Join(filepath.Dir(exe), "config.json")
}

func loadConfig() (fishConfig, error) {
	var c fishConfig
	b, err := os.ReadFile(configPath())
	if err != nil {
		return c, err
	}
	if err := json.Unmarshal(b, &c); err != nil {
		return c, err
	}
	if c.Message == "" {
		c.Message = "!fish"
	}
	if c.HardFloorSeconds < 30 { // plancher dur: jamais moins de 30s meme si mal configure
		c.HardFloorSeconds = 60
	}
	if c.JitterSeconds <= 0 {
		c.JitterSeconds = 90
	}
	if c.StaggerMaxSeconds <= 0 {
		c.StaggerMaxSeconds = 120
	}
	if c.ErrorBackoffMinutes <= 0 {
		c.ErrorBackoffMinutes = 30
	}
	if c.DisabledRecheckMinutes <= 0 {
		c.DisabledRecheckMinutes = 20
	}
	if c.FallbackIntervalMin <= 0 {
		c.FallbackIntervalMin = 15
	}
	return c, nil
}

func (c fishConfig) isWorker(name string) bool {
	if len(c.Workers) == 0 {
		return false // safety: no worker listed -> fish for nobody (excludes the main account by default)
	}
	for _, w := range c.Workers {
		if strings.EqualFold(w, name) {
			return true
		}
	}
	return false
}

// ── accounts.json ────────────────────────────────────────────────────────────
type cookie struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

type account struct {
	Name          string          `json:"name"`
	Bearer        string          `json:"bearer"`
	Cookies       json.RawMessage `json:"cookies"`
	ShoovySession string          `json:"shoovy_session"`
}

func (a account) cookieHeader() string {
	var arr []cookie
	if json.Unmarshal(a.Cookies, &arr) == nil && len(arr) > 0 {
		parts := make([]string, 0, len(arr))
		for _, c := range arr {
			if c.Name != "" {
				parts = append(parts, c.Name+"="+c.Value)
			}
		}
		return strings.Join(parts, "; ")
	}
	var m map[string]string
	if json.Unmarshal(a.Cookies, &m) == nil {
		parts := make([]string, 0, len(m))
		for k, v := range m {
			parts = append(parts, k+"="+v)
		}
		return strings.Join(parts, "; ")
	}
	return ""
}

func accountsPath() string {
	if p := os.Getenv("FISHD_ACCOUNTS"); p != "" {
		return p
	}
	exe, _ := os.Executable()
	return filepath.Join(filepath.Dir(exe), "accounts.json")
}

func loadAccounts() ([]account, error) {
	b, err := os.ReadFile(accountsPath())
	if err != nil {
		return nil, err
	}
	var accs []account
	if err := json.Unmarshal(b, &accs); err != nil {
		return nil, err
	}
	return accs, nil
}

// ── HTTP impersonation (tls-client, profil Chrome) ───────────────────────────
func newClient() (tls_client.HttpClient, error) {
	return tls_client.NewHttpClient(tls_client.NewNoopLogger(),
		tls_client.WithTimeoutSeconds(30),
		tls_client.WithClientProfile(profiles.Chrome_146),
		tls_client.WithCookieJar(tls_client.NewCookieJar()),
	)
}

type acctRunner struct {
	name          string
	bearer        string
	cookies       string
	shoovySession string
	client        tls_client.HttpClient
	rng           *rand.Rand
}

func (a *acctRunner) logf(f string, v ...any) {
	log.Printf("[%s] "+f, append([]any{a.name}, v...)...)
}

// jitter returns a random duration in [0, maxSec) (desyncs accounts).
func (a *acctRunner) jitter(maxSec int) time.Duration {
	if maxSec <= 0 {
		return 0
	}
	return time.Duration(a.rng.Intn(maxSec)) * time.Second
}

func (a *acctRunner) postChat(cfg fishConfig) (int, string) {
	body := fmt.Sprintf(`{"content":%q,"type":"message"}`, cfg.Message)
	req, err := http.NewRequest(http.MethodPost, "https://kick.com/api/v2/messages/send/"+cfg.ChatroomID, strings.NewReader(body))
	if err != nil {
		return 0, err.Error()
	}
	req.Header = http.Header{
		"User-Agent":    {userAgent},
		"Accept":        {"application/json"},
		"Content-Type":  {"application/json"},
		"Referer":       {"https://kick.com/" + cfg.Channel},
		"Origin":        {"https://kick.com"},
		"Authorization": {"Bearer " + a.bearer},
		"Cookie":        {a.cookies},
		http.HeaderOrderKey: {"user-agent", "accept", "content-type", "referer", "origin", "authorization", "cookie"},
	}
	resp, err := a.client.Do(req)
	if err != nil {
		return 0, err.Error()
	}
	defer resp.Body.Close()
	buf := make([]byte, 300)
	n, _ := resp.Body.Read(buf)
	return resp.StatusCode, string(buf[:n])
}

type fishState struct {
	Enabled     bool
	Remaining   int
	CooldownMin int
	LoggedIn    bool
}

// fishState lit /api/fishing (shoovy). ok=false si session absente / non-200 / illisible.
func (a *acctRunner) fishState() (fishState, bool) {
	var st fishState
	if a.shoovySession == "" {
		return st, false
	}
	req, err := http.NewRequest(http.MethodGet, "https://shoovy.wtf/api/fishing", nil)
	if err != nil {
		return st, false
	}
	req.Header = http.Header{
		"User-Agent":        {userAgent},
		"Accept":            {"application/json"},
		"Referer":           {"https://shoovy.wtf/fishing"},
		"Cookie":            {"session=" + a.shoovySession},
		http.HeaderOrderKey: {"user-agent", "accept", "referer", "cookie"},
	}
	resp, err := a.client.Do(req)
	if err != nil {
		return st, false
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return st, false
	}
	var r struct {
		Enabled     bool `json:"enabled"`
		Remaining   int  `json:"remaining"`
		CooldownMin int  `json:"cooldown_min"`
		LoggedIn    bool `json:"logged_in"`
	}
	if json.NewDecoder(resp.Body).Decode(&r) != nil {
		return st, false
	}
	st = fishState{Enabled: r.Enabled, Remaining: r.Remaining, CooldownMin: r.CooldownMin, LoggedIn: r.LoggedIn}
	return st, r.LoggedIn
}

func (a *acctRunner) run() {
	c, err := newClient()
	if err != nil {
		a.logf("client tls: %v", err)
		return
	}
	a.client = c

	cfg0, _ := loadConfig()
	// Startup stagger: each account starts at a different time.
	stag := a.jitter(cfg0.StaggerMaxSeconds)
	a.logf("starting — stagger %s", stag.Round(time.Second))
	time.Sleep(stag)

	var lastPost time.Time
	for {
		cfg, err := loadConfig()
		if err != nil {
			a.logf("config.json: %v — retry in 60s", err)
			time.Sleep(60 * time.Second)
			continue
		}

		// GARDE-FOU ABSOLU: jamais 2 posts a moins de hard_floor, quoi qu'il arrive.
		floor := time.Duration(cfg.HardFloorSeconds) * time.Second
		if !lastPost.IsZero() {
			if since := time.Since(lastPost); since < floor {
				time.Sleep(floor - since)
			}
		}

		st, ok := a.fishState()
		if !ok {
			// /api/fishing unreachable -> wait cautiously (do NOT post blindly).
			w := time.Duration(cfg.FallbackIntervalMin)*time.Minute + a.jitter(cfg.JitterSeconds)
			a.logf("fishing state unavailable — waiting %s (no post)", w.Round(time.Second))
			time.Sleep(w)
			continue
		}
		if !st.Enabled {
			w := time.Duration(cfg.DisabledRecheckMinutes)*time.Minute + a.jitter(cfg.JitterSeconds)
			a.logf("fishing DISABLED (enabled=false) — no post, recheck in %s", w.Round(time.Second))
			time.Sleep(w)
			continue
		}
		if st.Remaining > 0 {
			w := time.Duration(st.Remaining+3)*time.Second + a.jitter(cfg.JitterSeconds)
			time.Sleep(w)
			continue
		}

		// Ready to fish (remaining==0) and hard floor satisfied -> ONE post.
		code, resp := a.postChat(cfg)
		lastPost = time.Now()
		a.logf("%q -> HTTP %d %.90s", cfg.Message, code, resp)

		if code != 200 || strings.Contains(resp, `"error":true`) {
			// Ban/erreur/feature off cote chat -> backoff LONG + log fort (jamais de re-tir rapide).
			w := time.Duration(cfg.ErrorBackoffMinutes)*time.Minute + a.jitter(cfg.JitterSeconds)
			a.logf("!! FAILURE/BAN detected (HTTP %d) — BACKOFF %s", code, w.Round(time.Second))
			time.Sleep(w)
			continue
		}

		// Succes -> on attend le cooldown PLEIN (jamais moins), + jitter.
		cd := st.CooldownMin
		if cd <= 0 {
			cd = cfg.FallbackIntervalMin
		}
		w := time.Duration(cd)*time.Minute + a.jitter(cfg.JitterSeconds)
		a.logf("fish OK — next cast in ~%s", w.Round(time.Second))
		time.Sleep(w)
	}
}

func seedFor(name string) int64 {
	h := fnv.New64a()
	h.Write([]byte(name))
	// XOR avec l'horloge pour varier entre reboots (1970 au boot = ok, juste moins d'entropie).
	return int64(h.Sum64()) ^ time.Now().UnixNano()
}

func main() {
	check := flag.Bool("check", false, "valide accounts.json/config.json et sort")
	flag.Parse()

	accs, err := loadAccounts()
	if err != nil {
		log.Fatalf("accounts.json: %v", err)
	}
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("config.json: %v", err)
	}
	if *check {
		fmt.Printf("OK  workers=%v hard_floor=%ds error_backoff=%dm\n", cfg.Workers, cfg.HardFloorSeconds, cfg.ErrorBackoffMinutes)
		for _, a := range accs {
			fmt.Printf("  %-18s worker=%v bearer=%dch shoovy=%v\n", a.Name, cfg.isWorker(a.Name), len(a.Bearer), a.ShoovySession != "")
		}
		return
	}

	log.SetFlags(log.LstdFlags)
	log.Printf("fisher — workers=%v (main account excluded by default)", cfg.Workers)
	var wg sync.WaitGroup
	started := 0
	for _, acc := range accs {
		if !cfg.isWorker(acc.Name) {
			log.Printf("[%s] skip: not in the workers list", acc.Name)
			continue
		}
		if acc.Bearer == "" {
			log.Printf("[%s] skip: empty bearer", acc.Name)
			continue
		}
		bearer := acc.Bearer
		if dec, e := url.QueryUnescape(bearer); e == nil {
			bearer = dec
		}
		r := &acctRunner{
			name: acc.Name, bearer: bearer, cookies: acc.cookieHeader(),
			shoovySession: acc.ShoovySession, rng: rand.New(rand.NewSource(seedFor(acc.Name))),
		}
		started++
		wg.Add(1)
		go func() {
			defer wg.Done()
			r.run()
		}()
	}
	if started == 0 {
		log.Fatal("no active worker (check the 'workers' list in config.json)")
	}
	wg.Wait()
}
