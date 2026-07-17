// econ — funnel autonome vers le compte principal (StormRock). Sur carte Lichee 24/7.
// Par compte worker (JAMAIS StormRock): claim !daily (200 credits gratuits/20h) quand dispo,
// et tip le surplus de balance a StormRock (!tip @StormRock <montant>). Consolide les gains
// (fishing, daily, trading) vers le compte principal. ROI+ garanti (daily gratuit + transfert
// sans rake, verifie empiriquement 10 envoyes = 10 recus).
//
// Lecture balance/daily: shoovy.wtf /api/me + /api/stocks (plain, Railway). Post commandes chat:
// kick.com/api/v2/messages/send (Kasada -> tls-client impersonation Chrome, comme fishd).
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	http "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

const userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"

// ── config.json ──────────────────────────────────────────────────────────────
type config struct {
	TargetUser      string             `json:"target_user"`      // StormRock (destinataire des tips)
	Channel         string             `json:"channel"`          // slug kick (stormrock)
	ChatroomID      string             `json:"chatroom_id"`      // 29834074
	Workers         []string           `json:"workers"`          // comptes actionnes (JAMAIS StormRock)
	KeepFloat       map[string]float64 `json:"keep_float"`       // balance a laisser par worker (trading)
	MinTip          float64            `json:"min_tip"`          // seuil min pour tipper
	CycleMinutes    int                `json:"cycle_minutes"`    // periode de la boucle
	PostGapSeconds  int                `json:"post_gap_seconds"` // pause entre 2 posts chat
	TipCooldownHrs  float64            `json:"tip_cooldown_hrs"` // min heures entre 2 tips PAR worker (discretion)
}

func configPath() string {
	if p := os.Getenv("ECON_CONFIG"); p != "" {
		return p
	}
	exe, err := os.Executable()
	if err != nil {
		return "config.json"
	}
	return filepath.Join(filepath.Dir(exe), "config.json")
}

func loadConfig() (config, error) {
	var c config
	b, err := os.ReadFile(configPath())
	if err != nil {
		return c, err
	}
	if err := json.Unmarshal(b, &c); err != nil {
		return c, err
	}
	if c.TargetUser == "" {
		c.TargetUser = "StormRock"
	}
	if c.ChatroomID == "" {
		c.ChatroomID = "29834074"
	}
	if c.Channel == "" {
		c.Channel = "stormrock"
	}
	if c.MinTip <= 0 {
		c.MinTip = 50
	}
	if c.CycleMinutes <= 0 {
		c.CycleMinutes = 30
	}
	if c.PostGapSeconds <= 0 {
		c.PostGapSeconds = 8
	}
	if c.TipCooldownHrs <= 0 {
		c.TipCooldownHrs = 36
	}
	return c, nil
}

// ── etat persistant: dernier tip (unix) par worker, survit aux reboots ────────
func statePath() string {
	if p := os.Getenv("ECON_STATE"); p != "" {
		return p
	}
	return filepath.Join(filepath.Dir(configPath()), "econ_state.json")
}

func loadState() map[string]int64 {
	m := map[string]int64{}
	if b, err := os.ReadFile(statePath()); err == nil {
		json.Unmarshal(b, &m)
	}
	return m
}

func saveState(m map[string]int64) {
	if b, err := json.Marshal(m); err == nil {
		os.WriteFile(statePath(), b, 0644)
	}
}

// ── accounts.json (format fishd: bearer kick + cookies + shoovy_session) ──────
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
	return ""
}

func loadAccounts() ([]account, error) {
	p := os.Getenv("ECON_ACCOUNTS")
	if p == "" {
		exe, _ := os.Executable()
		p = filepath.Join(filepath.Dir(exe), "accounts.json")
	}
	b, err := os.ReadFile(p)
	if err != nil {
		return nil, err
	}
	var accs []account
	if err := json.Unmarshal(b, &accs); err != nil {
		return nil, err
	}
	return accs, nil
}

// ── HTTP ──────────────────────────────────────────────────────────────────────
func newClient() (tls_client.HttpClient, error) {
	return tls_client.NewHttpClient(tls_client.NewNoopLogger(),
		tls_client.WithTimeoutSeconds(30),
		tls_client.WithClientProfile(profiles.Chrome_146),
		tls_client.WithCookieJar(tls_client.NewCookieJar()),
	)
}

// shoovyGet lit un endpoint shoovy authentifie par le cookie session (plain suffit, Railway).
func shoovyGet(client tls_client.HttpClient, path, shoovySession string) (map[string]any, error) {
	req, err := http.NewRequest(http.MethodGet, "https://shoovy.wtf"+path, nil)
	if err != nil {
		return nil, err
	}
	req.Header = http.Header{
		"User-Agent": {userAgent},
		"Accept":     {"application/json"},
		"Cookie":     {"session=" + shoovySession},
		http.HeaderOrderKey: {"user-agent", "accept", "cookie"},
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var m map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&m); err != nil {
		return nil, err
	}
	return m, nil
}

// postChat poste une commande dans le chat kick (bearer + cookies, impersonation Chrome).
func postChat(client tls_client.HttpClient, a account, bearer, chatroomID, content string) (int, string) {
	body := fmt.Sprintf(`{"content":%q,"type":"message"}`, content)
	req, err := http.NewRequest(http.MethodPost,
		"https://kick.com/api/v2/messages/send/"+chatroomID, strings.NewReader(body))
	if err != nil {
		return 0, err.Error()
	}
	req.Header = http.Header{
		"User-Agent":    {userAgent},
		"Accept":        {"application/json"},
		"Content-Type":  {"application/json"},
		"Referer":       {"https://kick.com/stormrock"},
		"Origin":        {"https://kick.com"},
		"Authorization": {"Bearer " + bearer},
		"Cookie":        {a.cookieHeader()},
		http.HeaderOrderKey: {"user-agent", "accept", "content-type", "referer", "origin", "authorization", "cookie"},
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, err.Error()
	}
	defer resp.Body.Close()
	buf := make([]byte, 300)
	n, _ := resp.Body.Read(buf)
	return resp.StatusCode, string(buf[:n])
}

func asFloat(v any) (float64, bool) {
	f, ok := v.(float64)
	return f, ok
}

func asBool(v any) bool {
	b, _ := v.(bool)
	return b
}

func main() {
	log.SetFlags(log.LstdFlags)
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("config.json: %v", err)
	}
	accs, err := loadAccounts()
	if err != nil {
		log.Fatalf("accounts.json: %v", err)
	}
	byName := map[string]account{}
	for _, a := range accs {
		byName[a.Name] = a
	}
	client, err := newClient()
	if err != nil {
		log.Fatalf("tls client: %v", err)
	}
	lastTip := loadState()
	log.Printf("econ | target=%s | workers=%v | min_tip=%.0f | cycle=%dm | tip_cooldown=%.0fh",
		cfg.TargetUser, cfg.Workers, cfg.MinTip, cfg.CycleMinutes, cfg.TipCooldownHrs)

	for {
		cfg, _ = loadConfig() // relu a chaud
		gap := time.Duration(cfg.PostGapSeconds) * time.Second
		for _, name := range cfg.Workers {
			if strings.EqualFold(name, cfg.TargetUser) {
				continue // securite: jamais d'action sur le compte principal
			}
			a, ok := byName[name]
			if !ok || a.Bearer == "" || a.ShoovySession == "" {
				log.Printf("[%s] skip: incomplete account (bearer/shoovy_session)", name)
				continue
			}
			bearer := a.Bearer
			if dec, e := url.QueryUnescape(bearer); e == nil {
				bearer = dec
			}

			// 1) Daily gratuit si dispo
			if me, e := shoovyGet(client, "/api/me", a.ShoovySession); e == nil {
				if asBool(me["logged_in"]) && asBool(me["daily_ready"]) {
					code, resp := postChat(client, a, bearer, cfg.ChatroomID, "!daily")
					log.Printf("[%s] !daily -> HTTP %d %.60s", name, code, resp)
					time.Sleep(gap)
				}
			} else {
				log.Printf("[%s] /api/me error: %v", name, e)
			}

			// 2) Consolidation: tip le surplus au-dessus du float garde
			st, e := shoovyGet(client, "/api/stocks", a.ShoovySession)
			if e != nil {
				log.Printf("[%s] /api/stocks error: %v", name, e)
				continue
			}
			if !asBool(st["logged_in"]) {
				log.Printf("[%s] shoovy session invalid (logged_in=false)", name)
				continue
			}
			bal, _ := asFloat(st["balance"])
			keep := cfg.KeepFloat[name]
			surplus := bal - keep
			// Discretion: au plus 1 tip / tip_cooldown_hrs par worker.
			cdSecs := int64(cfg.TipCooldownHrs * 3600)
			elapsed := time.Now().Unix() - lastTip[name]
			if surplus >= cfg.MinTip && elapsed >= cdSecs {
				amt := int(surplus)
				code, resp := postChat(client, a, bearer, cfg.ChatroomID,
					fmt.Sprintf("!tip @%s %d", cfg.TargetUser, amt))
				log.Printf("[%s] !tip @%s %d (bal=%.0f keep=%.0f) -> HTTP %d %.60s",
					name, cfg.TargetUser, amt, bal, keep, code, resp)
				if code == 200 {
					lastTip[name] = time.Now().Unix()
					saveState(lastTip)
				}
				time.Sleep(gap)
			}
		}
		time.Sleep(time.Duration(cfg.CycleMinutes) * time.Minute)
	}
}
