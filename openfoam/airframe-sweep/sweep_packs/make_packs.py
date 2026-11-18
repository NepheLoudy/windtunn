#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务包生成器 — 把扫气全集切成可独立分发的包 (每包给一台机器).

设计原则:
  ① **包内保持完整 (α,β) 姿态组**: 一个姿态组 = 1 次建网 + N 次求解 (含热启动),
     跨包拆开会让网格复用与热启动收益全丢。
  ② 优先级按 |α|+|β| 升序 — 核心区 (±5°/β=0) 先出, 增量交付。
  ③ 包级幂等: 同一 domain 重跑生成器输出稳定 (排序后切片), 便于断点/换机接力。

用法:
  make_packs.py [--pack-groups 5] [--out-dir packs] [--env-json env.json]
产出:
  packs/P01.json ...  每个 = {pack_id, groups, cases, env, priority}
  packs/index.json    总索引 (含生成时间/总例数/域定义)
"""
import argparse
import json
import os

# ---- 域定义 (2026-11-18 曼波裁: V 10-20 全覆盖 / α ±30 混合步进 / β ±5) ----
V_LIST = list(range(10, 21))                                  # 10..20 共 11 档
A_CORE = [-15, -10, -5, 0, 5, 10, 15]                         # 主体 5° 步进
A_STALL_NEG = [-30, -27.5, -25, -22.5, -20]                   # 失速带 2.5° 加密
A_STALL_POS = [20, 22.5, 25, 27.5, 30]
ALPHA_LIST = A_STALL_NEG + A_CORE + A_STALL_POS               # 17 档 (升序)
BETA_LIST = [-5, -2.5, 0, 2.5, 5]                             # 5 档

DEFAULT_ENV = {
    "SURF_LEVEL": 6,
    "FIN_LEVEL": 7,
    "BOX_LEVEL": 3,
    "NP": 5,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-groups", type=int, default=5, help="每包姿态组数 (一组=全 V)")
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs"))
    ap.add_argument("--env-json", default=None)
    args = ap.parse_args()

    env = dict(DEFAULT_ENV)
    if args.env_json and os.path.exists(args.env_json):
        env.update(json.load(open(args.env_json, encoding="utf-8")))

    groups = [(a, b) for a in ALPHA_LIST for b in BETA_LIST]
    # 优先级: |α|+|β| 升序 (核心区先跑), 同权按 α 升序稳定排序
    groups.sort(key=lambda g: (abs(g[0]) + abs(g[1]), g[0], g[1]))

    n = args.pack_groups
    chunks = [groups[i:i + n] for i in range(0, len(groups), n)]
    os.makedirs(args.out_dir, exist_ok=True)
    index = {
        "domain": {"V": V_LIST, "alpha": ALPHA_LIST, "beta": BETA_LIST},
        "env": env,
        "total_groups": len(groups),
        "total_cases": len(groups) * len(V_LIST),
        "pack_groups": n,
        "packs": [],
    }
    for i, chunk in enumerate(chunks, 1):
        pid = "P%02d" % i
        pack = {
            "pack_id": pid,
            "priority": min(abs(a) + abs(b) for a, b in chunk),
            "groups": [{"alpha": a, "beta": b} for a, b in chunk],
            "V": V_LIST,
            "cases": len(chunk) * len(V_LIST),
            "env": env,
            "status": "pending",
            "assigned_to": None,
        }
        path = os.path.join(args.out_dir, pid + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=1)
        index["packs"].append({"pack_id": pid, "cases": pack["cases"],
                               "priority": pack["priority"],
                               "alphas": sorted({g["alpha"] for g in pack["groups"]}),
                               "betas": sorted({g["beta"] for g in pack["groups"]})})
        print("%s: %d 组 × %d V = %d 例  (α=%s, β=%s)"
              % (pid, len(chunk), len(V_LIST), pack["cases"],
                 sorted({a for a, _ in chunk}), sorted({b for _, b in chunk})))
    index["packs"].sort(key=lambda p: (p["priority"], p["pack_id"]))
    with open(os.path.join(args.out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print("\n总计 %d 组 / %d 例 / %d 包 -> %s"
          % (index["total_groups"], index["total_cases"], len(chunks), args.out_dir))


if __name__ == "__main__":
    main()
