#!/usr/bin/env bash
# 补表行恢复 v2: 从 CASEINFO 取 (V,alpha,beta), 表缺行则重跑 post_process append
set -u
ENGINE=~/windtunnel/openfoam/airframe-sweep
TABLE=~/sweep_t0v2/t0_table.csv
cd "$ENGINE" || exit 1
for c in ~/sweep_t0v2/case_*/; do
  [ -f "$c/results.json" ] || continue
  [ -f "$c/CASEINFO" ] || continue
  V=$(grep '^V=' "$c/CASEINFO" | cut -d= -f2)
  A=$(grep '^alpha=' "$c/CASEINFO" | cut -d= -f2)
  B=$(grep '^beta=' "$c/CASEINFO" | cut -d= -f2)
  if awk -F, -v v="$V" -v a="$A" -v b="$B" 'NR>2 && $1==v+0 && $2==a+0 && $3==b+0 {f=1} END{exit !f}' "$TABLE" 2>/dev/null; then
    echo "have  V$V a$A b$B"
  else
    echo "MISS  V$V a$A b$B — re-appending"
    python3 "$ENGINE/post_process.py" "$c" \
      --mass-props "$ENGINE/cad/v1/cfd/mass_properties.json" \
      --json "$c/results.json" --out "$TABLE" | tail -1
  fi
done
echo "---"; wc -l "$TABLE"; tail -3 "$TABLE" | cut -c1-50
