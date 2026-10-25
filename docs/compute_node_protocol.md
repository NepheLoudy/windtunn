# 多机协作协议 — 算力节点接入方案

> 2026-10-26 | 背景: 算力平台 100.92.135.29:271828 (qianli) 接入, **作为扫气主力**;
> 台式机 DESKTOP-PCOONE5 转协调/监控/交付。
> 状态: **方案定稿, 待网络打通** (100.92.x.x 为 CGNAT 段, 疑似 Tailscale; 台式机侧当前不可达)。

## 1. 架构与分工

```
算力节点 (主力)                                台式机 (协调/监控/交付)
├─ git clone windtunn (代码+几何+表)           ├─ git origin 同步中心 (push 需加速器)
├─ run_sweep_v2.sh 全表扫气 (表判重自动接力)    ├─ 扫气可继续跑剩余区 (表判重保证不重复)
├─ 每 N 工况: git commit+push 表增量           ├─ pull 合并 → guidance_sim/aero 直读
├─ progress.json → 送达台式机 (scp/钩子)       ├─ 悬浮窗 + audit_sweep 消费
└─ 大攻角异常 → devlog 记录                    └─ 出域补点需求 ↔ 算力节点队列
```

**表判重是协作安全的核心**: `run_sweep_v2.sh` 启动时读 `aero_table.csv` 建
`(V,α,β)` 已完集合, 循环内跳过 — **多机同时跑同一列表不会重复算**, 谁先入库谁算数。
(表追加行级冲突由合并脚本按键去重; 两机同时 push 同一表文件时 git 会报冲突,
合并原则: 两行都保留 → audit A5 抓重复 → 人工留一。更稳做法见 §4 分区。)

## 2. 网络打通 (待办)

1. 确认 100.92.135.29 的网络类型 (疑似 **Tailscale** — CGNAT 段):
   - 若是: 台式机装 Tailscale 登同一账号/接受共享 → IP 直达;
   - 若是内网/端口映射: 需要可达路由或跳板。
2. 认证: 首次密码登录 (曼波提供密码) → 台式机 `ssh-copy-id -p 271828 qianli@IP` → 之后全免密。
3. 验收: `ssh -p 271828 qianli@IP "nproc; free -g; cat /etc/os-release | head -2"` → 机器画像。

## 3. 算力节点初始化 (网络通后照单执行)

```bash
git clone https://github.com/NepheLoudy/windtunn && cd windtunnel
# OpenFOAM v12 (openfoam.org): 官网脚本安装或 apt (见 README「风洞 CFD 线」v12 段)
# Python: guidance_sim venv 仅需 numpy-free (post_process 纯标准库) ✓ 无依赖
bash openfoam/airframe-sweep/run_sweep_v2.sh <root> <nproc>   # 表判重自动跳过已完成
```

- 几何 STL 在仓库 `openfoam/airframe-sweep/cad/v1/cfd_geom_multi/` ✓ 无需额外传输
- 需要确认: 算力节点能否直连 github (不能则经台式机中转 git bundle)

## 4. 分工与同步节奏

| 阶段 | 算力节点 | 台式机 |
|---|---|---|
| 过渡期 | 接入自检 → 试跑 1 工况对拍 (与台式机同工况 CL 差 <2%) | 现有队列继续 (α 负半区) |
| 主力期 | **α 正半区** (0~15° × 全 β × 全 V) | α 负半区收尾 → 转监控/审查 |
| 表同步 | 每 10 工况 commit+push | 每次 pull 后合并去重 → guidance_sim |
| 监控 | progress.json 本地 | 定时 ssh 拉取 → 悬浮窗双机视图 |

**分区避免写冲突** (比表判重更稳): 两机各扫 α 半区, 表文件按半区分文件
(`aero_table_neg.csv` / `aero_table_pos.csv`) → 合并脚本拼接 → 最终 `aero_table.csv`。

## 5. 验收对拍 (算力节点上岗条件)

同工况 (V=25, α=5°, β=0, δ=0) 两机各跑一遍: CL/CD 差 **<2%** (网格八叉树对齐差异量级)
→ 通过; 超差 → 查 OpenFOAM 版本/编译差异, 不可信不上岗。
