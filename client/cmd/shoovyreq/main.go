// shoovyreq — fetch one shoovy.wtf endpoint through the disciplined shared
// client, then print the result. This is the safe way to poke the API by hand
// or from a script: it paces, backs off on 429/502, and logs every call, so an
// exploration loop can't turn into the recon burst that gets rate-limited.
//
//	shoovyreq /api/games/info
//	shoovyreq -channel <streamer> /api/leaderboard
//	shoovyreq -o games.json -log requests.jsonl /api/games/info
//	shoovyreq -session <shoovy_session> /api/me
//
// The streamer is always a parameter, never baked in.
package main

import (
	"flag"
	"fmt"
	"net/url"
	"os"
	"strings"
	"time"

	shoovyclient "shoovyclient"
)

func main() {
	channel := flag.String("channel", "", "streamer channel to scope the request to (added as ?channel=)")
	out := flag.String("o", "", "write the response body to this file instead of stdout")
	logPath := flag.String("log", "", "append a JSONL audit line per request to this file")
	session := flag.String("session", "", "shoovy.wtf session cookie, for gated endpoints")
	bearer := flag.String("bearer", "", "kick session_token, for gated endpoints")
	minGap := flag.Duration("min", 3*time.Second, "minimum spacing between requests")
	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Fprintln(os.Stderr, "usage: shoovyreq [flags] <path>   e.g. shoovyreq -channel <streamer> /api/leaderboard")
		os.Exit(2)
	}
	path := flag.Arg(0)
	if *channel != "" {
		sep := "?"
		if strings.Contains(path, "?") {
			sep = "&"
		}
		path += sep + "channel=" + url.QueryEscape(*channel)
	}

	c := shoovyclient.New(shoovyclient.Options{
		MinGap: *minGap, LogPath: *logPath, ShoovySession: *session, Bearer: *bearer,
	})
	r := c.Get(path)

	fmt.Fprintf(os.Stderr, "HTTP %d  %dms  degraded=%v  %d bytes\n", r.Status, r.Ms, r.Degraded, len(r.Body))
	if *out != "" {
		if err := os.WriteFile(*out, r.Body, 0644); err != nil {
			fmt.Fprintln(os.Stderr, "write:", err)
			os.Exit(1)
		}
		fmt.Fprintln(os.Stderr, "saved ->", *out)
	} else {
		os.Stdout.Write(r.Body)
		fmt.Println()
	}
	if r.Status < 200 || r.Status >= 300 {
		os.Exit(1)
	}
}
