#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_tables.py -- 跨机数据验证器
用法: py -3 verify_tables.py <table1.csv> <table2.csv> ... --legacy <aero_table.csv> --shards <dir> --json <out.json>
校验:
  1. 表头/注释行一致 (S_REF/L_REF/RHO/MOMENT_REF)
  2. 表内键唯一 (V,alpha,beta,de,da,dr)
  3. 跨表键零重叠
  4. 行键归属分片定义 (alpha,beta 必须属于该分片 groups)
  5. 物理合理性: CD>0, |CL|<3, 六系数有限
  6. 老表对拍: 同键六系数相对差, CL/CD>15% 告警
"""
import sys, os, json, argparse

def parse_table(path):
    """returns (meta_dict, rows_list) ; rows: dict keyed (V,a,b,de,da,dr)->coef dict"""
    meta, rows = {}, {}
    header = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                for tok in line.lstrip("#").split():
                    if "=" in tok:
                        k, _, v = tok.partition("=")
                        meta[k] = v.rstrip(",")
                continue
            if header is None:
                header = [c.strip() for c in line.split(",")]
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != len(header):
                rows[("MALFORMED", line)] = None
                continue
            r = dict(zip(header, parts))
            key = (round(float(r["V"]), 2), round(float(r["alpha"]), 2),
                   round(float(r["beta"]), 2), round(float(r["de"]), 2),
                   round(float(r["da"]), 2), round(float(r["dr"]), 2))
            rows[key] = {c: float(r[c]) for c in ("CL", "CD", "Cm", "CY", "Cl", "Cn") if c in r}
    return meta, header, rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="+")
    ap.add_argument("--legacy", required=True)
    ap.add_argument("--shards", default=None, help="dir with P01s*.json for ownership check")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    problems, warns = [], []
    tables = {}
    for t in args.tables:
        name = os.path.basename(t).replace("_table.csv", "").replace(".csv", "")
        try:
            meta, header, rows = parse_table(t)
        except Exception as e:
            problems.append(f"[P0] {name}: 无法解析 ({e})")
            continue
        tables[name] = (meta, header, rows)
        bad = [k for k in rows if k[0] == "MALFORMED"]
        if bad:
            problems.append(f"[P1] {name}: {len(bad)} 行格式错误")

    # 1. 表头与 meta 一致性
    metas = {n: m[0] for n, m in tables.items()}
    if len({json.dumps(m, sort_keys=True) for m in metas.values()}) > 1:
        problems.append(f"[P0] 表头 meta 不一致: {metas}")
    hdrs = {n: m[1] for n, m in tables.items()}
    if len({tuple(h) for h in hdrs.values()}) > 1:
        problems.append(f"[P1] 列结构不一致: {set(tuple(h) for h in hdrs.values())}")

    # 2/3. 键唯一 + 跨表零重叠
    all_keys = {}
    for n, (_, _, rows) in tables.items():
        for k in rows:
            if k[0] == "MALFORMED":
                continue
            if k in all_keys:
                problems.append(f"[P0] 跨机键重叠: {k} 在 {all_keys[k]} 和 {n}")
            else:
                all_keys[k] = n
        dup = len(rows) - len(set(k for k in rows if k[0] != "MALFORMED"))
        if dup > 0:
            problems.append(f"[P1] {n}: 表内键重复 {dup}")

    # 4. 分片归属
    if args.shards and os.path.isdir(args.shards):
        for n, (_, _, rows) in tables.items():
            pj = os.path.join(args.shards, n + ".json")
            if not os.path.isfile(pj):
                warns.append(f"[P2] {n}: 无分片定义 {pj}, 跳过归属校验")
                continue
            conf = json.load(open(pj, encoding="utf-8"))
            allowed = {(g["alpha"], g["beta"]) for g in conf["groups"]}
            bad = [k for k in rows if k[0] != "MALFORMED" and (k[1], k[2]) not in allowed]
            if bad:
                problems.append(f"[P0] {n}: {len(bad)} 行不属于该分片: {bad[:3]}")

    # 5. 物理合理性
    for n, (_, _, rows) in tables.items():
        for k, c in rows.items():
            if k[0] == "MALFORMED":
                continue
            cd, cl = c.get("CD"), c.get("CL")
            import math
            if any(not math.isfinite(v) for v in c.values()):
                problems.append(f"[P0] {n} {k}: 系数含 NaN/Inf")
            if cd is not None and not (0 < cd < 2.0):
                problems.append(f"[P0] {n} {k}: CD={cd} 出合理域 (0,2)")
            if cl is not None and abs(cl) > 3.0:
                problems.append(f"[P1] {n} {k}: |CL|={abs(cl)} >3")

    # 6. 老表对拍
    if os.path.isfile(args.legacy):
        _, _, legacy = parse_table(args.legacy)
        matched = 0
        for n, (_, _, rows) in tables.items():
            for k, c in rows.items():
                if k[0] == "MALFORMED":
                    continue
                if k in legacy:
                    matched += 1
                    L = legacy[k]
                    for coef in ("CL", "CD"):
                        a, b = c[coef], L[coef]
                        denom = max(abs(a), abs(b), 1e-6)
                        rel = abs(a - b) / denom
                        if rel > 0.15:
                            warns.append(f"[P1] {n} {k} {coef}: 新={a:.4f} 旧={b:.4f} 相对差 {rel*100:.1f}% >15%")
        if matched == 0:
            warns.append("[P2] 无任何键与老表重叠 (V<15 或非老表域), 无法对拍")
        else:
            print(f"legacy crosscheck: {matched} keys matched")
    else:
        warns.append(f"[P2] 老表不存在: {args.legacy}")

    total_rows = sum(len(r) for _, _, r in tables.values())
    print(f"=== 跨机数据验证 ===")
    print(f"tables: {len(tables)}  total rows: {total_rows}")
    for w in warns:
        print(f"WARN {w}")
    if problems:
        print(f"FAIL ({len(problems)} problems)")
        for p in problems:
            print(f"  {p}")
        rc = 1
    else:
        print("PASS")
        rc = 0
    if args.json:
        json.dump({"rc": rc, "rows": total_rows, "problems": problems,
                   "warns": warns, "tables": {n: len(m[2]) for n, m in tables.items()}},
                  open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(rc)

if __name__ == "__main__":
    main()
