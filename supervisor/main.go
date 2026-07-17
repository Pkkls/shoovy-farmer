// supervisor — keeps the shoovy-farmer bots running 24/7 on a PC (Windows/Linux/mac).
// Replaces the RISC-V board's init.d keepalive. Launches each bot, restarts it if it dies,
// and honors the STOP flag (data/STOP_ALL): while the flag exists, all bots are killed and
// not relaunched (the dashboard's STOP button just creates that flag). Writes data/status.json
// so the dashboard can show which bots are up (cross-platform, no /proc needed).
//
// Run it with the install root as the working directory (run.bat does `cd /d %~dp0`).
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"
)

const stopFlag = "data/STOP_ALL"

type bot struct {
	name string
	exe  string
	env  []string
}

var bots = []bot{
	{"fisher", filepath.Join("bin", "fisher.exe"), []string{"FISHD_CONFIG=fisher.config.json", "FISHD_ACCOUNTS=accounts.json"}},
	{"econ", filepath.Join("bin", "econ.exe"), []string{"ECON_CONFIG=econ.config.json", "ECON_ACCOUNTS=accounts.json", "ECON_STATE=data/econ_state.json"}},
	{"watchdog", filepath.Join("bin", "watchdog.exe"), []string{"WATCHDOG_CONFIG=watchdog.config.json"}},
	{"dashboard", filepath.Join("bin", "dashboard.exe"), []string{"DASHBOARD_CONFIG=dashboard.config.json"}},
}

type proc struct {
	cmd     *exec.Cmd
	running bool
	logf    *os.File
}

var (
	mu    sync.Mutex
	procs = map[string]*proc{}
)

func stopped() bool {
	_, err := os.Stat(stopFlag)
	return err == nil
}

func logmsg(f string, a ...any) {
	fmt.Printf(time.Now().Format("2006/01/02 15:04:05")+" [supervisor] "+f+"\n", a...)
}

// launch starts a bot, redirects its output to data/<name>.log, and watches for it to exit.
func launch(b bot) {
	_ = os.MkdirAll("data", 0755)
	lf, err := os.OpenFile(filepath.Join("data", b.name+".log"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		logmsg("%s: log: %v", b.name, err)
		return
	}
	cmd := exec.Command(b.exe)
	cmd.Env = append(os.Environ(), b.env...)
	cmd.Stdout = lf
	cmd.Stderr = lf
	if err := cmd.Start(); err != nil {
		logmsg("%s: start: %v", b.name, err)
		lf.Close()
		return
	}
	logmsg("%s started (pid %d)", b.name, cmd.Process.Pid)
	mu.Lock()
	procs[b.name] = &proc{cmd: cmd, running: true, logf: lf}
	mu.Unlock()
	go func() {
		cmd.Wait()
		mu.Lock()
		if p := procs[b.name]; p != nil {
			p.running = false
		}
		mu.Unlock()
		lf.Close()
	}()
}

func killAll() {
	mu.Lock()
	defer mu.Unlock()
	for name, p := range procs {
		if p.running && p.cmd.Process != nil {
			p.cmd.Process.Kill()
			p.running = false
			logmsg("%s killed (STOP flag)", name)
		}
	}
}

func writeStatus() {
	mu.Lock()
	st := map[string]bool{}
	for _, b := range bots {
		st[b.name] = procs[b.name] != nil && procs[b.name].running
	}
	mu.Unlock()
	st["stopped"] = stopped()
	b, _ := json.Marshal(st)
	os.WriteFile(filepath.Join("data", "status.json"), b, 0644)
}

func main() {
	_ = os.MkdirAll("data", 0755)
	logmsg("supervisor started — %d bots. STOP flag: %s", len(bots), stopFlag)
	wasStopped := false
	for {
		if stopped() {
			if !wasStopped {
				killAll()
				logmsg("STOP flag present — bots stopped, waiting for the flag to be removed")
				wasStopped = true
			}
		} else {
			if wasStopped {
				logmsg("STOP flag removed — relaunching bots")
				wasStopped = false
			}
			for _, b := range bots {
				mu.Lock()
				p := procs[b.name]
				mu.Unlock()
				if p == nil || !p.running {
					launch(b)
					time.Sleep(1 * time.Second) // stagger léger entre lancements
				}
			}
		}
		writeStatus()
		time.Sleep(3 * time.Second)
	}
}
