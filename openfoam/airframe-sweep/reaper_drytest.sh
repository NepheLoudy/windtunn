#!/usr/bin/env bash
# reaper 收割逻辑一次性试刀 (红档案 case) — 验证瘦身幅度与 results.json 完好
set -e
D=~/sweep_t1_foldedfin_T1/case_V15_a-15_b-15
echo "before: $(du -sm $D | cut -f1)M"
find "$D" -maxdepth 2 -path "*processor*/[0-9]*" -exec rm -rf {} + 2>/dev/null
find "$D" -maxdepth 1 -regextype posix-extended -regex ".*/[0-9]+(.[0-9]+)?" -not -name constant -exec rm -rf {} + 2>/dev/null
echo "after:  $(du -sm $D | cut -f1)M"
echo "kept:   $(ls $D | tr '\n' ' ')"
python3 - << 'PY'
import json, glob
p = glob.glob('/home/qianli/sweep_t1_foldedfin_T1/case_V15_a-15_b-15/results.json')[0]
j = json.load(open(p))
print('results.json OK, keys:', list(j)[:4])
PY
pp=$(ls $D/postProcessing 2>/dev/null | head -1)
[ -n "$pp" ] && echo "postProcessing OK: $pp"
