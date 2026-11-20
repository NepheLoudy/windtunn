# 多机协作协议 — 算力节点接入方案

> ⚠ **§1–§5 为历史方案（2026-10-26 两机时代），已被任务包架构取代** —
> 现行协议见 `docs/task_pack_protocol.md`（pack 分片/判重三层防线/collect+verify/晨报值班）。
> §6 是 11-15 实况补丁，仍有效的坑位记录保留。
> IP 口径（100.92.x/271828）为当时猜测，实测 qianli 走 Tailscale 100.90.63.31、SSH 用户 qianli。

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

## 6. 新设备接入指南 (2026-11-15 实况版 — 第三台及以上照此办理)

> ⚠ 本文 §2/§3 写于 10-26 入网前 (IP/端口为当时的猜测口径, 已过时)。
> **实况**: qianli 经 Tailscale 入网 (节点名 `qianli-b460maoruselite`, IP **100.90.63.31**:22,
> 登录账号 NepheLoudy@), SSH 走 **qianli 用户**的公钥授权 (桌面 WSL root 的 ed25519 已在
> `/home/qianli/.ssh/authorized_keys`)。新设备照本节办理。

### 6.1 入网 (Tailscale)

1. 新设备装 Tailscale: Windows `winget install tailscale.tailscale` / Linux
   `curl -fsSL https://tailscale.com/install.sh | sh` / macOS App Store。
2. 登录 **NepheLoudy@ 同一 tailnet** (用账号的 SSO 登录; 三方设备走管理台 share 邀请亦可)。
3. 验收入网: `tailscale status` 应看到 `qianli-b460maoruselite  100.90.63.31`;
   `ping 100.90.63.31` 通即入网成功。
4. 安全边界须知: **入网=可直达 tailnet 全部节点** (含桌面机), 设备本身要设锁; 若需限制
   只准达 qianli, 在 Tailscale 管理台 ACL 里按设备收紧 (默认 ACL 全通)。

### 6.2 SSH 授权 (远控 qianli)

1. 新设备生成密钥: `ssh-keygen -t ed25519 -C "操作者@新设备名"`。
2. **公钥交给曼波或现有操作者** → 追加进 qianli 的 `/home/qianli/.ssh/authorized_keys`
   (一行一个, 与现有桌面钥并列; **root 账号无授权钥是刻意设计** — 操作者身份都走 qianli 用户)。
3. 验收画像: `ssh qianli@100.90.63.31 "nproc; free -g; uptime"` → 预期 14 核/16GB/负载视批次。
4. 密码登录兜底: sshd 默认允许 (Ubuntu 默认未显式关闭), 首次没带钥时曼波可给一次性密码。

### 6.3 远控纪律 (本周事故沉淀, 必读)

- **发射前先查在跑树**: `pgrep -af 'run_sweep|run_solve|foamRun|FluidX3D'` — 11-14 V25 双开
  (两工位同 case 双 mpirun, 16GB 机器 OOM 互杀) 的直接教训; 同 case 发射加 **flock 互斥**
  (v25_finish_1115.sh 有实装范例)。
- **绝不 pkill 在跑引擎/收割机/guard** (pkill 自杀陷阱: 字符类断自匹配, 见 §4);
  kill 别人的树前先发消息知会。
- **MSYS/Git Bash 调 wsl/ssh 传参必须 `MSYS2_ARG_CONV_EXCL='*'`** (路径会被改写)。
- **多工位并行时任务卡写明文件范围** (会话注册局纪律); 崩溃工位的遗留脚本仍是武装
  (11-14 双开源头=被误判死亡的子代理会话), 接手前先清点其遗留。
- **CPU/GPU 分域**: OpenFOAM 扫气占 CPU 14 核, LBM 占 GPU — 互不抢核; GPU 空转超 1h
  该接队就接队 (E1 精神)。
- 数据纪律: 表 append-only; V15/30 冷备; lookup 的 aero_table.csv 为 V20-25 完整笛卡尔格。

### 6.4 新设备算力接入路径 (如果要跑扫气)

现行路径 = **任务包领包制**: 按 `docs/new_node_onboarding.md` 全流程接入 (环境/冒烟/对拍硬门槛),
再按 `docs/task_pack_protocol.md` §2 领包跑 (`sweep_packs/run_pack.sh`)。
本节 §3 初始化 + §5 验收对拍是**历史两机方案**的口径, 保留作对照。GPU 类任务 (FluidX3D)
需自备 5070 级显卡 + 逐零件体素化管线 (见仓库 `openfoam/airframe-sweep/setup.cpp` v4asm 注释)。
