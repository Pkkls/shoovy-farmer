// trader — autonomous mean-reversion bot for the shoovy.wtf virtual stock market.
// Strategy: only buy deep dislocations (price <= MA*(1-entry_dev)), sell on the return toward
// the mean (dev >= -exit_dev) or after max_hold. Robust to rule changes (it relies on the
// announced "drift back to normal", not on the exact AMM formula). Continuous reconcile: the
// server portfolio is the source of truth every cycle, which absorbs timeouts and desyncs.
//
// Safety: set "live": false in trader.config.json for PAPER mode (computes and logs signals but
// never actually trades). Set it to true only once you trust it. The shoovy session comes from
// accounts.json (the account named in trader.config.json).
//
// API: GET /api/stocks (public) -> quotes+balance+portfolio+news+logged_in.
//   BUY  POST /api/stocks/trade {symbol,side:"buy",amount:<credits>}
//   SELL POST /api/stocks/trade {symbol,side:"sell",shares:"all"}   -> {ok,error,message,balance,portfolio}
//   Server enforces an 8s cooldown between trades.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

const (
	apiURL     = "https://shoovy.wtf/api/stocks"
	tradeURL   = "https://shoovy.wtf/api/stocks/trade"
	historyURL = "https://shoovy.wtf/api/stocks/history"
	userAgent  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
	cooldown   = 9 * time.Second // server: 8s min between trades
	maxLogSize = 5 << 20         // rotate trades.jsonl at 5 MB
	epsShares  = 1e-6
)

type config struct {
	Account      string   `json:"account"`
	Session      string   `json:"session"`
	Watch        []string `json:"watch"`
	MAWindow     int      `json:"ma_window"`
	EntryDev     float64  `json:"entry_dev"`
	ExitDev      float64  `json:"exit_dev"`
	MaxHoldS     int      `json:"max_hold_s"`
	SizeCredits  float64  `json:"size_credits"`
	MaxPositions int      `json:"max_positions"`
	PollSeconds  int      `json:"poll_seconds"`
	FeePct       float64  `json:"fee_pct"`
	Live         bool     `json:"live"`
}

func configPath() string {
	if p := os.Getenv("TRADER_CONFIG"); p != "" {
		return p
	}
	exe, err := os.Executable()
	if err != nil {
		return "config.json"
	}
	return filepath.Join(filepath.Dir(exe), "config.json")
}

// sessionFromAccounts looks up the shoovy_session of the given account in accounts.json.
// This keeps accounts.json the single file that holds credentials.
func sessionFromAccounts(accountName string) string {
	path := os.Getenv("TRADER_ACCOUNTS")
	if path == "" {
		path = "accounts.json"
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	var accs []struct {
		Name          string `json:"name"`
		ShoovySession string `json:"shoovy_session"`
	}
	if json.Unmarshal(b, &accs) != nil {
		return ""
	}
	for _, a := range accs {
		if a.Name == accountName {
			return a.ShoovySession
		}
	}
	return ""
}

func clampF(v, lo, hi, def float64) float64 {
	if v <= 0 {
		return def
	}
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
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
	// defaults + sanity bounds (config is reloaded live -> guard against typos)
	if c.MAWindow <= 0 || c.MAWindow > 500 {
		c.MAWindow = 20
	}
	c.EntryDev = clampF(c.EntryDev, 0.005, 0.5, 0.03)
	c.ExitDev = clampF(c.ExitDev, 0.0, 0.5, 0.005)
	if c.MaxHoldS <= 0 || c.MaxHoldS > 86400 {
		c.MaxHoldS = 360
	}
	c.SizeCredits = clampF(c.SizeCredits, 1, 1e9, 150)
	if c.MaxPositions <= 0 || c.MaxPositions > 100 {
		c.MaxPositions = 6
	}
	if c.PollSeconds <= 0 || c.PollSeconds > 3600 {
		c.PollSeconds = 15
	}
	if c.FeePct < 0 || c.FeePct > 100 {
		c.FeePct = 1
	}
	if len(c.Watch) == 0 {
		c.Watch = []string{"GAMBA", "CHAT", "STRMR", "WINS", "LOSS"}
	}
	return c, nil
}

type quote struct {
	Symbol string  `json:"symbol"`
	Price  float64 `json:"price"`
}

type position struct {
	Symbol  string  `json:"symbol"`
	Shares  float64 `json:"shares"`
	AvgCost float64 `json:"avg_cost"`
	Price   float64 `json:"price"`
	Value   float64 `json:"value"`
}

type stocksResp struct {
	Quotes    []quote    `json:"quotes"`
	Balance   float64    `json:"balance"`
	Portfolio []position `json:"portfolio"`
	LoggedIn  bool       `json:"logged_in"`
}

type tradeResp struct {
	OK        bool       `json:"ok"`
	Error     string     `json:"error"`
	Message   string     `json:"message"`
	Balance   *float64   `json:"balance"` // pointer: tells "absent" apart from "0"
	Portfolio []position `json:"portfolio"`
}

func (t *tradeResp) ok() bool { return t != nil && t.OK && t.Error == "" }

var client = &http.Client{Timeout: 20 * time.Second}

func setHeaders(req *http.Request, session string, withBody bool) {
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Origin", "https://shoovy.wtf")
	req.Header.Set("Referer", "https://shoovy.wtf/stocks")
	if session != "" {
		req.Header.Set("Cookie", "session="+session)
	}
	if withBody {
		req.Header.Set("Content-Type", "application/json")
	}
}

func getStocks(session string) (*stocksResp, error) {
	req, err := http.NewRequest(http.MethodGet, apiURL, nil)
	if err != nil {
		return nil, err
	}
	setHeaders(req, session, false)
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("http %d", resp.StatusCode)
	}
	var sr stocksResp
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		return nil, err
	}
	return &sr, nil
}

// postTrade returns (body, httpCode). code==0 on network error (uncertain -> continuous
// reconcile will fix the state next cycle from the server portfolio).
func postTrade(session string, payload map[string]any) (*tradeResp, int) {
	b, _ := json.Marshal(payload)
	req, err := http.NewRequest(http.MethodPost, tradeURL, bytes.NewReader(b))
	if err != nil {
		return nil, 0
	}
	setHeaders(req, session, true)
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0
	}
	defer resp.Body.Close()
	var tr tradeResp
	json.NewDecoder(resp.Body).Decode(&tr)
	return &tr, resp.StatusCode
}

func doBuy(session, symbol string, credits float64) *tradeResp {
	tr, code := postTrade(session, map[string]any{"symbol": symbol, "side": "buy", "amount": credits})
	if code == 200 && tr.ok() {
		return tr
	}
	if tr != nil {
		logf("BUY FAILED %s: code=%d err=%q msg=%q", symbol, code, tr.Error, tr.Message)
	} else {
		logf("BUY FAILED %s: network (code=%d)", symbol, code)
	}
	return nil
}

func doSellAll(session, symbol string) *tradeResp {
	tr, code := postTrade(session, map[string]any{"symbol": symbol, "side": "sell", "shares": "all"})
	if code == 200 && tr.ok() {
		return tr
	}
	if tr != nil {
		logf("SELL FAILED %s: code=%d err=%q msg=%q", symbol, code, tr.Error, tr.Message)
	} else {
		logf("SELL FAILED %s: network (code=%d)", symbol, code)
	}
	return nil
}

func seedWindow(session, symbol string, maWindow, poll int) []float64 {
	mins := (maWindow*poll)/60 + 2
	if mins < 6 {
		mins = 6
	}
	url := fmt.Sprintf("%s?symbol=%s&minutes=%d", historyURL, symbol, mins)
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil
	}
	setHeaders(req, session, false)
	resp, err := client.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	var h struct {
		History [][2]float64 `json:"history"`
	}
	if json.NewDecoder(resp.Body).Decode(&h) != nil {
		return nil
	}
	out := make([]float64, 0, maWindow)
	start := 0
	if len(h.History) > maWindow {
		start = len(h.History) - maWindow
	}
	for _, pt := range h.History[start:] {
		out = append(out, pt[1]) // [ts, price]
	}
	return out
}

func mean(xs []float64) float64 {
	if len(xs) == 0 {
		return 0
	}
	s := 0.0
	for _, x := range xs {
		s += x
	}
	return s / float64(len(xs))
}

func pushCap(w []float64, px float64, maWindow int) []float64 {
	w = append(w, px)
	if len(w) > maWindow {
		w = w[len(w)-maWindow:]
	}
	return w
}

type openPos struct {
	entryPx float64
	entryTs time.Time
	cost    float64
	shares  float64
}

var (
	tradesLog string
	logf      = log.Printf
)

func rotateIfBig(path string) {
	if fi, err := os.Stat(path); err == nil && fi.Size() > maxLogSize {
		os.Rename(path, path+".1") // garde une generation
	}
}

func logTrade(rec map[string]any) {
	rec["ts"] = time.Now().Unix()
	b, _ := json.Marshal(rec)
	rotateIfBig(tradesLog)
	f, err := os.OpenFile(tradesLog, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		logf("logTrade: ecriture impossible: %v", err)
	} else {
		f.Write(append(b, '\n'))
		f.Close()
	}
	logf("%s %v px=%v dev=%v pnl=%v", rec["event"], rec["symbol"], rec["price"], rec["dev"], rec["pnl"])
}

func round2(x float64) float64 { return math.Round(x*100) / 100 }

// reconcile aligns the in-memory map with the server portfolio (source of truth).
// Drops what the server no longer holds; adopts what it holds and we do not track yet.
// Absorbe les issues de trade incertaines (timeout, 200+ok:false) sans desync durable.
func reconcile(sr *stocksResp, watch map[string]bool, positions map[string]*openPos) {
	held := map[string]position{}
	for _, p := range sr.Portfolio {
		if watch[p.Symbol] && p.Shares > epsShares {
			held[p.Symbol] = p
		}
	}
	for sym := range positions {
		if _, ok := held[sym]; !ok {
			delete(positions, sym) // serveur ne detient plus -> stop suivi
		}
	}
	for sym, p := range held {
		if positions[sym] == nil {
			positions[sym] = &openPos{entryPx: p.AvgCost, entryTs: time.Now(),
				cost: p.Shares * p.AvgCost, shares: p.Shares}
			logf("reconcile: adopted %s %.4f @ %.2f (value %.0f)", sym, p.Shares, p.AvgCost, p.Value)
		}
	}
}

func main() {
	log.SetFlags(log.LstdFlags)
	_ = os.MkdirAll("data", 0755)
	tradesLog = filepath.Join("data", "trades.jsonl")

	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("config.json: %v", err)
	}
	if cfg.Session == "" {
		cfg.Session = sessionFromAccounts(cfg.Account) // read shoovy_session from accounts.json
	}
	if cfg.Session == "" {
		log.Fatalf("no shoovy session for account %q (set it in accounts.json or trader.config.json)", cfg.Account)
	}
	logf("trader %s | mode=%s | watch=%v | entry<=-%.1f%% exit>=-%.1f%% size=%.0f maxpos=%d",
		cfg.Account, ternary(cfg.Live, "LIVE", "PAPER"), cfg.Watch, cfg.EntryDev*100, cfg.ExitDev*100,
		cfg.SizeCredits, cfg.MaxPositions)

	watch := map[string]bool{}
	for _, s := range cfg.Watch {
		watch[s] = true
	}

	windows := map[string][]float64{}
	for _, s := range cfg.Watch {
		windows[s] = seedWindow(cfg.Session, s, cfg.MAWindow, cfg.PollSeconds)
	}
	logf("seeded: %s", seedSummary(windows, cfg.Watch))

	positions := map[string]*openPos{}
	// Blocking startup reconcile: retry until the first successful getStocks before trading.
	for {
		sr, err := getStocks(cfg.Session)
		if err == nil {
			reconcile(sr, watch, positions)
			logf("startup reconcile ok (%d position(s) adopted)", len(positions))
			break
		}
		logf("startup reconcile: getStocks failed (%v) — retry in 15s", err)
		time.Sleep(15 * time.Second)
	}

	var lastTrade time.Time
	var realized float64

	for {
		cfg, err = loadConfig()
		if err != nil {
			logf("config.json: %v — retry in 30s", err)
			time.Sleep(30 * time.Second)
			continue
		}
		sr, err := getStocks(cfg.Session)
		if err != nil {
			logf("fetch: %v", err)
			time.Sleep(time.Duration(cfg.PollSeconds) * time.Second)
			continue
		}
		// Dead session -> do not trade (refresh the shoovy cookie in accounts.json).
		if !sr.LoggedIn {
			logf("session INVALID (logged_in=false) — shoovy cookie expired; skipping cycle")
			time.Sleep(time.Duration(cfg.PollSeconds) * time.Second)
			continue
		}

		// Continuous reconcile: the server portfolio wins over memory.
		reconcile(sr, watch, positions)

		prices := map[string]float64{}
		for _, q := range sr.Quotes {
			prices[q.Symbol] = q.Price
		}
		balance := sr.Balance
		cdOK := time.Since(lastTrade) >= cooldown
		acted := false // au plus 1 trade/cycle (cooldown 8s < poll 15s)

		for _, sym := range cfg.Watch {
			px, ok := prices[sym]
			if !ok || px <= 0 {
				continue
			}
			windows[sym] = pushCap(windows[sym], px, cfg.MAWindow)
			w := windows[sym]
			if len(w) < cfg.MAWindow {
				continue
			}
			ma := mean(w)
			if ma <= 0 {
				continue
			}
			dev := px/ma - 1.0
			pos := positions[sym]

			// ── Sortie (prioritaire) ──
			if pos != nil {
				held := time.Since(pos.entryTs)
				if dev >= -cfg.ExitDev || held >= time.Duration(cfg.MaxHoldS)*time.Second {
					if acted || !cdOK {
						continue
					}
					if cfg.Live {
						tr := doSellAll(cfg.Session, sym)
						lastTrade = time.Now()
						acted = true // meme sur echec: stoppe le cycle, evite la rafale de 400
						if tr == nil {
							continue // reconcile will re-adopt/purge next cycle
						}
						proceeds := pos.cost // fallback neutre (pnl=0) si balance absente
						if tr.Balance != nil {
							proceeds = *tr.Balance - balance
							balance = *tr.Balance
						}
						pnl := proceeds - pos.cost
						realized += pnl
						reason := "timeout"
						if dev >= -cfg.ExitDev {
							reason = "revert"
						}
						logTrade(map[string]any{"event": "sell", "symbol": sym, "price": round2(px),
							"dev": round2(dev * 100), "held_s": int(held.Seconds()), "pnl": round2(pnl),
							"realized_total": round2(realized), "reason": reason})
						delete(positions, sym)
					} else {
						proceeds := pos.shares * px * (1 - cfg.FeePct/100)
						pnl := proceeds - pos.cost
						realized += pnl
						lastTrade = time.Now()
						acted = true
						reason := "timeout"
						if dev >= -cfg.ExitDev {
							reason = "revert"
						}
						logTrade(map[string]any{"event": "sell", "symbol": sym, "price": round2(px),
							"dev": round2(dev * 100), "held_s": int(held.Seconds()), "pnl": round2(pnl),
							"realized_total": round2(realized), "reason": reason})
						delete(positions, sym)
					}
				}
				continue
			}

			// ── Entree: dip profond seulement, sous le cap ──
			if dev <= -cfg.EntryDev && balance >= cfg.SizeCredits && len(positions) < cfg.MaxPositions && !acted && cdOK {
				shares := cfg.SizeCredits / px
				if cfg.Live {
					tr := doBuy(cfg.Session, sym, cfg.SizeCredits)
					lastTrade = time.Now()
					acted = true // meme sur echec: stoppe le cycle
					if tr == nil {
						continue
					}
					if tr.Balance != nil {
						balance = *tr.Balance
					} else {
						balance -= cfg.SizeCredits
					}
					// shares reelles: delta impossible a isoler proprement ici, mais on n'achete
					// que si pos==nil ET reconcile a purge -> le portfolio ne detenait rien avant.
					for _, p := range tr.Portfolio {
						if p.Symbol == sym {
							shares = p.Shares
						}
					}
				} else {
					balance -= cfg.SizeCredits
					lastTrade = time.Now()
					acted = true
				}
				positions[sym] = &openPos{entryPx: px, entryTs: time.Now(), cost: cfg.SizeCredits, shares: shares}
				logTrade(map[string]any{"event": "buy", "symbol": sym, "price": round2(px),
					"dev": round2(dev * 100), "ma": round2(ma), "size": cfg.SizeCredits,
					"open_positions": len(positions)})
			}
		}
		time.Sleep(time.Duration(cfg.PollSeconds) * time.Second)
	}
}

func seedSummary(windows map[string][]float64, watch []string) string {
	s := ""
	for _, sym := range watch {
		s += fmt.Sprintf("%s=%d ", sym, len(windows[sym]))
	}
	return s
}

func ternary(b bool, t, f string) string {
	if b {
		return t
	}
	return f
}
