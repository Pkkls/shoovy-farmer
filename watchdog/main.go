// watchdog — anti-spam guard. Watches how fast the bots' log files grow. If a bot writes
// too many lines per minute (a runaway spam, like the fishd bug that posted !fish every 5s),
// the watchdog: (1) logs a timestamped ALERT to data/watchdog.log, (2) creates the STOP flag
// (kill-switch). The supervisor then kills and holds the bots. The watchdog never stops itself.
//
// "log when we catch something": every detection is written to data/watchdog.log with the bot
// name, the measured rate, and the threshold it crossed.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"time"
)

type watch struct {
	Name      string `json:"name"`
	Log       string `json:"log"`
	MaxPerMin int    `json:"max_per_min"`
}

type config struct {
	PollSeconds      int     `json:"poll_seconds"`
	StopFlag         string  `json:"stop_flag"`
	LogFile          string  `json:"log_file"`
	Watch            []watch `json:"watch"`
	HeartbeatMinutes int     `json:"heartbeat_minutes"`
}

func loadConfig() config {
	c := config{PollSeconds: 15, StopFlag: "data/STOP_ALL", LogFile: "data/watchdog.log", HeartbeatMinutes: 15}
	p := os.Getenv("WATCHDOG_CONFIG")
	if p == "" {
		p = "watchdog.config.json"
	}
	if b, err := os.ReadFile(p); err == nil {
		json.Unmarshal(b, &c)
	}
	if c.PollSeconds <= 0 {
		c.PollSeconds = 15
	}
	if c.HeartbeatMinutes <= 0 {
		c.HeartbeatMinutes = 15
	}
	if c.LogFile == "" {
		c.LogFile = "data/watchdog.log"
	}
	return c
}

func wlog(logFile, f string, v ...any) {
	line := time.Now().Format("2006/01/02 15:04:05") + " " + fmt.Sprintf(f, v...) + "\n"
	fmt.Print(line)
	if fh, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644); err == nil {
		fh.WriteString(line)
		fh.Close()
	}
}

func countLines(path string) int {
	f, err := os.Open(path)
	if err != nil {
		return -1
	}
	defer f.Close()
	n := 0
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1<<20)
	for sc.Scan() {
		n++
	}
	return n
}

func flagSet(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// trip fires the kill-switch: log the alert and create the STOP flag. The supervisor sees the
// flag and kills/holds the bots (cross-platform, no direct process killing here).
func trip(cfg config, w watch, rate float64) {
	wlog(cfg.LogFile, "!!! SPAM DETECTED — bot=%s rate=%.1f lines/min (threshold %d). Kill-switch engaged.", w.Name, rate, w.MaxPerMin)
	if err := os.WriteFile(cfg.StopFlag, []byte("watchdog: spam "+w.Name+"\n"), 0644); err != nil {
		wlog(cfg.LogFile, "error writing STOP flag: %v", err)
	}
	wlog(cfg.LogFile, "Bots will be stopped by the supervisor. Click Start in the dashboard (or delete %s) to resume.", cfg.StopFlag)
}

func main() {
	cfg := loadConfig()
	_ = os.MkdirAll("data", 0755)
	wlog(cfg.LogFile, "watchdog started — watching %d logs, poll %ds, kill-switch=%s", len(cfg.Watch), cfg.PollSeconds, cfg.StopFlag)

	type sample struct {
		lines int
		when  time.Time
	}
	prev := map[string]sample{}
	for _, w := range cfg.Watch {
		prev[w.Name] = sample{lines: countLines(w.Log), when: time.Now()}
	}
	lastBeat := time.Now()

	for {
		time.Sleep(time.Duration(cfg.PollSeconds) * time.Second)
		alreadyStopped := flagSet(cfg.StopFlag)

		for _, w := range cfg.Watch {
			cur := countLines(w.Log)
			p := prev[w.Name]
			now := time.Now()
			// log rotated / recreated -> reset baseline, no false alert
			if cur < p.lines || p.lines < 0 {
				prev[w.Name] = sample{lines: cur, when: now}
				continue
			}
			elapsedMin := now.Sub(p.when).Minutes()
			if elapsedMin < 0.15 { // not enough time for a reliable rate
				continue
			}
			rate := float64(cur-p.lines) / elapsedMin
			prev[w.Name] = sample{lines: cur, when: now}

			// do not re-trip if already stopped (logs may still be flushing)
			if !alreadyStopped && w.MaxPerMin > 0 && rate > float64(w.MaxPerMin) {
				trip(cfg, w, rate)
				alreadyStopped = true
			}
		}

		if time.Since(lastBeat) >= time.Duration(cfg.HeartbeatMinutes)*time.Minute {
			state := "OK"
			if flagSet(cfg.StopFlag) {
				state = "STOPPED (flag set)"
			}
			wlog(cfg.LogFile, "heartbeat — %s", state)
			lastBeat = time.Now()
		}
	}
}
