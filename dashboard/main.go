// dashboard — small local web page to watch the shoovy-farmer bots and stop/start them.
// Open http://127.0.0.1:8088 in your browser. Read-only view + a STOP / START button.
// Cross-platform (no /proc, no killall): bot health comes from data/status.json written by
// the supervisor; STOP just creates data/STOP_ALL (the supervisor kills/holds the bots).
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"
)

const userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"

type cfg struct {
	Port           int     `json:"port"`
	AccountsFile   string  `json:"accounts_file"`
	EconStateFile  string  `json:"econ_state_file"`
	StatusFile     string  `json:"status_file"`
	StopFlag       string  `json:"stop_flag"`
	Target         string  `json:"target"`
	TipCooldownHrs float64 `json:"tip_cooldown_hrs"`
}

func loadCfg() cfg {
	c := cfg{Port: 8088, AccountsFile: "accounts.json", EconStateFile: "data/econ_state.json",
		StatusFile: "data/status.json", StopFlag: "data/STOP_ALL", Target: "main", TipCooldownHrs: 36}
	p := os.Getenv("DASHBOARD_CONFIG")
	if p == "" {
		p = "dashboard.config.json"
	}
	if b, err := os.ReadFile(p); err == nil {
		json.Unmarshal(b, &c)
	}
	return c
}

type account struct {
	Name          string `json:"name"`
	ShoovySession string `json:"shoovy_session"`
}
type position struct {
	Symbol string  `json:"symbol"`
	Shares float64 `json:"shares"`
	Value  float64 `json:"value"`
}
type quote struct {
	Symbol    string  `json:"symbol"`
	Price     float64 `json:"price"`
	ChangePct float64 `json:"change_pct"`
}
type stocksResp struct {
	Quotes    []quote    `json:"quotes"`
	Balance   float64    `json:"balance"`
	Portfolio []position `json:"portfolio"`
	LoggedIn  bool       `json:"logged_in"`
}

var httpc = &http.Client{Timeout: 12 * time.Second}

func fetchStocks(session string) (*stocksResp, error) {
	req, _ := http.NewRequest("GET", "https://shoovy.wtf/api/stocks", nil)
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Cookie", "session="+session)
	resp, err := httpc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var sr stocksResp
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		return nil, err
	}
	return &sr, nil
}

func loadJSON(path string, out any) {
	if b, err := os.ReadFile(path); err == nil {
		json.Unmarshal(b, out)
	}
}

func fmtN(f float64) string { return fmt.Sprintf("%.0f", f) }

func esc(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	return strings.ReplaceAll(s, ">", "&gt;")
}

const pageCSS = `
*{box-sizing:border-box}body{background:#0b0b0e;color:#eef0f2;font:14px/1.55 ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;margin:0;padding:28px 18px 60px}
.wrap{max-width:920px;margin:0 auto}.tnum{font-variant-numeric:tabular-nums}
.hdr{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:20px}
h1{font-size:19px;margin:0;display:flex;align-items:center;gap:9px}.logo{width:9px;height:9px;border-radius:3px;background:#53fc18;box-shadow:0 0 14px 1px rgba(83,252,24,.6)}
.sub{color:#6b6b74;font-size:12.5px;margin-top:2px}
.live{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:4px 10px;border-radius:999px;color:#53fc18;background:rgba(83,252,24,.12);border:1px solid rgba(83,252,24,.25)}
.live.off{color:#ff5d57;background:rgba(255,93,87,.12);border-color:rgba(255,93,87,.3)}
.btn{cursor:pointer;font:inherit;font-size:12.5px;font-weight:650;padding:7px 14px;border-radius:9px;border:1px solid transparent}
.btn.stop{background:rgba(255,93,87,.14);color:#ff5d57;border-color:rgba(255,93,87,.35)}.btn.go{background:rgba(83,252,24,.14);color:#53fc18;border-color:rgba(83,252,24,.4)}
.banner{margin:14px 0 0;padding:12px 16px;border-radius:12px;font-size:13px;background:rgba(255,93,87,.1);border:1px solid rgba(255,93,87,.3);color:#ffb4b0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}@media(max-width:720px){.grid{grid-template-columns:1fr}}
.card{background:linear-gradient(180deg,#111114,#0d0d10);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px 20px}.card.span{grid-column:1/-1}
.ttl{font-size:11px;font-weight:600;letter-spacing:.11em;text-transform:uppercase;color:#6b6b74;margin:0 0 14px}
.hero-num{font-size:46px;font-weight:700;letter-spacing:-.03em;color:#53fc18;text-shadow:0 0 40px rgba(83,252,24,.25)}.hero-num .u{font-size:15px;color:#6b6b74;margin-left:9px}
table{border-collapse:collapse;width:100%}th{color:#6b6b74;font-weight:500;font-size:11px;letter-spacing:.05em;text-transform:uppercase;text-align:left;padding:0 10px 8px;border-bottom:1px solid rgba(255,255,255,.07)}
td{padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.04)}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.name.main{color:#53fc18;font-weight:650}.up{color:#4ade80}.down{color:#ff5d57}.mut{color:#6b6b74}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%}
`

func handler(c cfg) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var accs []account
		loadJSON(c.AccountsFile, &accs)
		_, statErr := os.Stat(c.StopFlag)
		isStopped := statErr == nil

		var sb strings.Builder
		sb.WriteString(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="15"><title>Shoovy Farmer</title><style>` + pageCSS + `</style></head><body><div class="wrap">`)
		sb.WriteString(`<div class="hdr"><div><h1><span class="logo"></span>Shoovy Farmer</h1><div class="sub">local control panel</div></div><div style="display:flex;align-items:center;gap:12px">`)
		if isStopped {
			sb.WriteString(`<span class="live off">STOPPED</span><form method="post" action="/start" style="margin:0"><button class="btn go">&#9654; Start</button></form>`)
		} else {
			sb.WriteString(`<span class="live">Running</span><form method="post" action="/stop" style="margin:0" onsubmit="return confirm('Stop all bots?')"><button class="btn stop">&#9632; STOP</button></form>`)
		}
		sb.WriteString(`<span class="mut tnum">` + time.Now().Format("15:04:05") + `</span></div></div>`)
		if isStopped {
			sb.WriteString(`<div class="banner">All bots are stopped and will not restart while stopped. Click Start to resume.</div>`)
		}

		var accRows strings.Builder
		var quotes []quote
		var mainWorth, mainBal, mainPos float64
		for _, a := range accs {
			isMain := strings.EqualFold(a.Name, c.Target)
			cls := ""
			if isMain {
				cls = " main"
			}
			sr, err := fetchStocks(a.ShoovySession)
			if err != nil || !sr.LoggedIn {
				accRows.WriteString(`<tr><td class="name` + cls + `">` + esc(a.Name) + `</td><td class="num down">session invalid</td><td class="num mut">-</td></tr>`)
				continue
			}
			if len(quotes) == 0 {
				quotes = sr.Quotes
			}
			var pos float64
			for _, p := range sr.Portfolio {
				if p.Shares > 1e-6 {
					pos += p.Value
				}
			}
			worth := sr.Balance + pos
			if isMain {
				mainWorth, mainBal, mainPos = worth, sr.Balance, pos
			}
			accRows.WriteString(`<tr><td class="name` + cls + `">` + esc(a.Name) + `</td><td class="num` + cls + `">` + fmtN(sr.Balance) + `</td><td class="num tnum">` + fmtN(worth) + `</td></tr>`)
		}
		sb.WriteString(`<div class="card span"><div class="ttl">Main account net worth</div><div class="hero-num tnum">` + fmtN(mainWorth) + `<span class="u">credits</span></div><div class="mut" style="font-size:12.5px;margin-top:4px">cash ` + fmtN(mainBal) + ` &middot; in positions ` + fmtN(mainPos) + `</div></div>`)
		sb.WriteString(`<div class="grid">`)
		sb.WriteString(`<div class="card span"><div class="ttl">Accounts</div><table><thead><tr><th>Account</th><th class="num">Balance</th><th class="num">Net worth</th></tr></thead><tbody>` + accRows.String() + `</tbody></table></div>`)

		sb.WriteString(`<div class="card"><div class="ttl">Market</div><table><thead><tr><th>Ticker</th><th class="num">Price</th><th class="num">24h</th></tr></thead><tbody>`)
		for _, q := range quotes {
			cl := "up"
			if q.ChangePct < 0 {
				cl = "down"
			}
			sb.WriteString(fmt.Sprintf(`<tr><td>$%s</td><td class="num">%.2f</td><td class="num %s">%+.1f%%</td></tr>`, q.Symbol, q.Price, cl, q.ChangePct))
		}
		sb.WriteString(`</tbody></table></div>`)

		var status map[string]bool
		loadJSON(c.StatusFile, &status)
		sb.WriteString(`<div class="card"><div class="ttl">Bots</div><table><tbody>`)
		for _, b := range []string{"fisher", "econ", "watchdog", "dashboard"} {
			up := status[b] || b == "dashboard"
			color, label := "#ff5d57", "down"
			if up {
				color, label = "#53fc18", "up"
			}
			sb.WriteString(fmt.Sprintf(`<tr><td>%s</td><td class="num"><span class="dot" style="background:%s"></span> %s</td></tr>`, b, color, label))
		}
		sb.WriteString(`</tbody></table></div>`)

		var econState map[string]int64
		loadJSON(c.EconStateFile, &econState)
		sb.WriteString(`<div class="card span"><div class="ttl">Tips to main account</div><table><thead><tr><th>Worker</th><th>Last tip</th><th class="num">Next possible</th></tr></thead><tbody>`)
		names := make([]string, 0, len(econState))
		for k := range econState {
			names = append(names, k)
		}
		sort.Strings(names)
		cd := int64(c.TipCooldownHrs * 3600)
		for _, k := range names {
			last := econState[k]
			eta := last + cd - time.Now().Unix()
			etaStr := `<span class="up">now</span>`
			if eta > 0 {
				etaStr = fmt.Sprintf(`<span class="mut tnum">in %dh%02dm</span>`, eta/3600, (eta%3600)/60)
			}
			sb.WriteString(fmt.Sprintf(`<tr><td>%s</td><td class="mut tnum">%s</td><td class="num">%s</td></tr>`, esc(k), time.Unix(last, 0).Format("01-02 15:04"), etaStr))
		}
		if len(names) == 0 {
			sb.WriteString(`<tr><td class="mut" colspan="3">No tips yet</td></tr>`)
		}
		sb.WriteString(`</tbody></table></div>`)

		sb.WriteString(`</div></div></body></html>`)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Write([]byte(sb.String()))
	}
}

func main() {
	c := loadCfg()
	http.HandleFunc("/", handler(c))
	http.HandleFunc("/stop", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			os.WriteFile(c.StopFlag, []byte("stopped\n"), 0644)
		}
		http.Redirect(w, r, "/", http.StatusSeeOther)
	})
	http.HandleFunc("/start", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			os.Remove(c.StopFlag)
		}
		http.Redirect(w, r, "/", http.StatusSeeOther)
	})
	addr := fmt.Sprintf("127.0.0.1:%d", c.Port)
	fmt.Printf("dashboard on http://%s\n", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		fmt.Println("listen:", err)
		os.Exit(1)
	}
}
