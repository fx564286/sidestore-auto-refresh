#!/usr/bin/env bash
set -Eeuo pipefail
REPO=fx564286/sidestore-auto-refresh
BRANCH=fix/nrg-v34-memory-display-profiles
BASELINE=39089480745
DEADLINE=$(( $(date +%s) + 86400 ))
INSTALLER=https://raw.githubusercontent.com/$REPO/7c3b7a231d4381988cc3212e10887ff8e1b4ceeb/scripts/nrg_v41_117_install_oneclick.sh
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/nrg-auto-install"
mkdir -p "$STATE"
for bin in gh python3 curl; do command -v "$bin" >/dev/null || { echo "[ERROR] missing $bin"; exit 1; }; done
echo "[WATCH] 24h latest successful builds; baseline $BASELINE"
while (( $(date +%s) < DEADLINE )); do
  if JSON=$(gh api "repos/$REPO/actions/runs?branch=$BRANCH&per_page=50" 2>/dev/null); then
    RUN=$(printf '%s' "$JSON" | python3 -c '
import json,sys
runs=json.load(sys.stdin).get("workflow_runs",[])
valid=[r["id"] for r in runs if r.get("status")=="completed" and r.get("conclusion")=="success" and r.get("id",0)>39089480745 and r.get("path","").endswith("livecontainer-build.yml")]
print(max(valid,default=0))
')
    if (( RUN > 0 )) && [[ ! -f "$STATE/$RUN.ok" ]]; then
      echo "[INSTALL] run $RUN"
      TMP=$(mktemp)
      if curl -fLsS "$INSTALLER" -o "$TMP" && grep -q '^R=39083771063$' "$TMP"; then
        sed -i "s/^R=39083771063$/R=$RUN/" "$TMP"
        if bash "$TMP"; then
          touch "$STATE/$RUN.ok"
          echo "[PASS] installed $RUN"
        else
          echo "[RETRY] $RUN failed; retry in 60s"
        fi
      else
        echo '[ERROR] installer fetch/validation failed'
      fi
      rm -f "$TMP"
    fi
  else
    echo '[WARN] GitHub API unavailable'
  fi
  sleep 60
done
echo '[DONE] 24h monitoring finished'
