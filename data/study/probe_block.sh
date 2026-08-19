#!/bin/sh
# Caracterise la duree du blocage: 1 requete / 15 min, jusqu'a 8h.
# Ecrit un JSONL horodate. Sort des que le blocage tombe.
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36'
OUT="$(dirname "$0")/block_probe.jsonl"
START=$(date +%s)
i=0
while [ $i -lt 32 ]; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 70 -A "$UA" https://shoovy.wtf/api/me)
  now=$(date +%s)
  printf '{"ts":%s,"elapsed_min":%s,"attempt":%s,"http":%s}\n' "$now" "$(( (now-START)/60 ))" "$((i+1))" "$code" >> "$OUT"
  if [ "$code" != "429" ]; then
    echo "DEBLOQUE apres $(( (now-START)/60 )) min de sonde (HTTP $code)"
    exit 0
  fi
  i=$((i+1))
  sleep 900
done
echo "TOUJOURS BLOQUE apres 8h"
exit 1
