#!/bin/sh
# Patient harvest driver.
#
# The site flaps between 200, 429 and 502, so a single pass never completes.
# harvest.py already resumes from what is on disk, so this just keeps calling it
# with a long wait between attempts until every target is captured.
#
# ponytail: fixed 10 min wait, not adaptive backoff. The site's downtime is
# measured in hours, so a smarter curve would not buy anything.

D="$(dirname "$0")"
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
