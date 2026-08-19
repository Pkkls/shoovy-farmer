#!/bin/sh
# Patient harvest driver.
#
# The site answers roughly one request in six and never more than twice in a
# row, so a single pass never completes. harvest.py resumes from what is on
# disk, so this just keeps calling it until every target is captured.
#
# Refuses to start if another driver is already running. Two drivers doubled the
# request rate against an already sick backend and made the diagnosis worse,
# which is a mistake worth making structurally impossible rather than
# remembering not to repeat.

D="$(cd "$(dirname "$0")" && pwd)"
LOCK="$D/harvest.pid"

if [ -f "$LOCK" ]; then
  old=$(cat "$LOCK" 2>/dev/null)
  if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
    echo "un driver tourne deja (pid $old) — abandon"
    exit 2
  fi
  echo "verrou perime (pid $old mort) — reprise"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

i=0
while [ $i -lt 24 ]; do
  i=$((i + 1))
  echo "=== tentative $i  $(date '+%H:%M:%S') ==="
  python "$D/harvest.py"
  if [ $? -eq 0 ]; then
    echo "=== COLLECTE COMPLETE apres $i tentatives ==="
    exit 0
  fi
  echo "--- pause 10 min ---"
  sleep 600
done
echo "=== abandon apres $i tentatives ==="
exit 1
