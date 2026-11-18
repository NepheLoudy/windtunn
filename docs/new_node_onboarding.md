# 新机器加入算力池 — 接入手册

> 2026-11-18 | 适用：任何一台新电脑参与镖体气动数据集（T0/T1 扫气）计算
> 前置阅读：`compute_node_protocol.md`（网络/权限）、`dataset_delivery.md`（数据集语义）
> 本手册目标：**新机 30-60 分钟内从零到产出首个有效工况，且绝不影响在跑产线**

---

## 0. 一分钟判断：这台机器适合干什么

| 机器条件 | 能干的活 | 不适合的活 |
|---|---|---|
| ≥8 核 + ≥8GB 可用内存 + 能装 OpenFOAM v12 | **T0/T1 扫气主力**（本项目唯一算力密集型任务） | — |
| 有 NVIDIA GPU（≥8GB 显存）+ CUDA | LBM 快扫/探针（FluidX3D，4min/例级） | **不能出 T1 力矩可信数据**（Re 限界，见 §6） |
| 只有 CPU 但核少（4-6 核） | 单例验证/对拍/审计 | 大批量扫气 |
| 任意 | 数据消费（读 aero_table 做 RL/分析），零算力要求 | — |

**核心约束**：T1 单例需 **~3GB 内存**（1.88M 网格），双道并行需 ~6GB。低于 8GB 可用内存的机器只能单道跑。

---

## 1. 网络接入（Tailscale）

1. 装 Tailscale：
   - Windows: `winget install tailscale.tailscale`
   - Linux: `curl -fsSL https://tailscale.com/install.sh | sh`
   - macOS: App Store
2. 登录 **NepheLoudy@ 同一 tailnet**（或从管理台 share 邀请）
3. 验收：`tailscale status` 应看到 `qianli-b460maoruselite 100.90.63.31`；`ping 100.90.63.31` 通

⚠ **安全边界**：入网后可达 tailnet 全部节点（含桌面机）。要收紧就在 Tailscale 管理台 ACL 按设备限制。

---

## 2. SSH 授权（如果需要远程被调度）

1. 生成密钥：`ssh-keygen -t ed25519 -C "operator@<机器名>"`
2. 公钥交给协调方 → 追加进 **qianli 的 `/home/qianli/.ssh/authorized_keys`**
   - ⚠ qianli 的 `root` 账号**无授权钥是刻意设计**，操作者身份一律走 `qianli` 用户
3. 验收：`ssh qianli@100.90.63.31 "nproc; free -g; uptime"`

---

## 3. 环境准备（OpenFOAM v12 + 项目代码）

### 3.1 系统依赖
```bash
sudo apt update && sudo apt install -y build-essential cmake flex bison zlib1g-dev \
  libboost-system-dev libboost-thread-dev libopenmpi-dev openmpi-bin \
  libfftw3-dev libscotch-dev libptscotch-dev gnuplot
```

### 3.2 OpenFOAM v12（openfoam.org 版，**不是** ESI/OpenCFD 版）
```bash
# 官方 deb 源（Ubuntu 24.04）
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt update && sudo apt install -y openfoam12
# 或源码编译（校园网不通 dl.openfoam.org 时）：
#   git clone https://github.com/OpenFOAM/OpenFOAM-12.git
#   注意：编译前 ./Allwmake -j 前先确认 ThirdParty 的 MPI 配置（见 compute_node_protocol §编译坑）
```
验收：`blockMesh -help` / `snappyHexMesh -help` / `foamRun -help` 三件套都通。

### 3.3 项目代码 + 几何
```bash
git clone https://github.com/NepheLoudy/windtunn && cd windtunn
# 几何 STL 31 件（仓库已含 cad/v1/cfd_geom_multi_parallel/，确认 30 个 .stl 存在）
ls openfoam/airframe-sweep/cad/v1/cfd_geom_multi_parallel/*.stl | wc -l   # 应为 30
# 质量属性（力矩参考点，必须与主控机一致）
cat openfoam/airframe-sweep/cad/v1/cfd/mass_properties.json
```

### 3.4 Python（仅标准库需求，后处理不需要 numpy）
```bash
python3 --version   # ≥3.8 即可
```
⚠ 若该机有 `python` 指向 Windows Store stub（WSL 常见），用 `python3` 显式调用。

---

## 4. 首次冒烟（**必做，不合格不上岗**）

### 4.1 环境自检
```bash
cd openfoam/airframe-sweep
bash -c 'source /opt/openfoam12/etc/bashrc && command -v blockMesh snappyHexMesh foamRun'
# 三行路径都打出来才算过
```

### 4.2 单例全链路（约 40-50 分钟，T1 口径）
```bash
export GEOM_DIR=$PWD/cad/v1/cfd_geom_multi_parallel
export SURF_LEVEL=6 FIN_LEVEL=8 BOX_LEVEL=3
CASE=/tmp/smoke_case
bash make_case.sh 20 -15 -15 "$CASE"
cd "$CASE" && source /opt/openfoam12/etc/bashrc && blockMesh > log.blockMesh 2>&1 \
  && snappyHexMesh -overwrite > log.snappy 2>&1
grep -E "Finished meshing|Layers added" log.snappy    # 必须有这两行
cd - && bash run_solve.sh "$CASE" 8 600
python3 post_process.py "$CASE" --mass-profiles cad/v1/cfd/mass_properties.json \
  --json "$CASE/results.json" --out "$CASE/smoke_table.csv"
cat "$CASE/smoke_table.csv"
```

### 4.3 对拍验收（**上岗硬门槛**）
把 `smoke_table.csv` 的六系数与主表同点对照：
```bash
grep '^20.0000,-15.0000,-15.0000' guidance_sim/aero/aero_table.csv
```
| 判据 | 阈值 | 不过怎么办 |
|---|---|---|
| CL/CD/CY 相对偏差 | **<2%** | 查 OpenFOAM 版本（必须 v12 openfoam.org）/ 几何 STL 完整性 / 编译选项 |
| Cm/Cn 相对偏差 | <10%（力矩对网格/设置敏感） | 同上，另查 mass_properties.json 是否同一份 |

> 依据：既有跨机对拍 CD −0.14%、六项全 <2%（2026-10-31 记录）。

---

## 5. 加入产线（多机协同）

### 5.1 为什么天然安全：表判重
`run_sweep_v2.sh` 启动时读 `OUT_CSV` 建 `(V,α,β)` 已完集合，循环内跳过 —— **多机同时跑同一任务清单不会重复算**。
- 谁先入库谁算数
- 两机同时写同一表文件会 git 冲突：**合并原则 = 两行都保留 → 审计抓重复 → 人工留一**
- 更稳做法：**分区**（各机跑不同 α 半区/V 档，表文件分开 → 合并脚本拼接）

### 5.2 推荐分区（当前产线）
| 机器 | 分工 | 说明 |
|---|---|---|
| qianli（14 核 16GB） | 主力：α∈[-15,15] 主区 | 三道并行 np≈5×3 |
| 桌面机（12 核 / WSL 10GB） | 分摊：失速带 α∈[±20,30] 或 V 奇档 | 双道 np=5×2 |
| 新机 | 按剩余区间认领（协调方分配） | 避免与上面两机重叠 |

### 5.3 启动命令模板（**必须写脚本文件，不要内联到 ssh**）
```bash
#!/usr/bin/env bash
# launch_sweep_<机名>.sh — 铁律：env 自检不过不发车
set +u
source /opt/openfoam12/etc/bashrc      # ← 必须显式 source（踩过「裸环境 blockMesh 未找到」）
unset DISPLAY; export HWLOC_COMPONENTS=-gl
cd "$HOME/windtunn/openfoam/airframe-sweep" || exit 1

export OUT_CSV="$HOME/sweep_t1/t1_table.csv"      # 本机表文件
export SWEEP_V="10 11 12 13 14 15 16 17 18 19 20"
export SWEEP_ALPHA="-30 -27.5 ... 27.5 30"
export SWEEP_BETA="-5 -2.5 0 2.5 5"
export SURF_LEVEL=6 FIN_LEVEL=8 BOX_LEVEL=3
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"

# 三件套自检（11-17 事故后固化）
for t in blockMesh snappyHexMesh foamRun; do
  command -v $t >/dev/null || { echo "FATAL: $t 不在 PATH — bashrc 未生效"; exit 1; }
done
echo "launch OK $(date) blockMesh=$(command -v blockMesh)"

setsid nohup ./run_sweep_v2.sh "$HOME/sweep_t1" 8 >> "$HOME/sweep_t1/sweep.log" 2>&1 < /dev/null &
sleep 3
pgrep -cf 'run_sweep_v[2]' >/dev/null && echo RUNNER_ALIVE || echo RUNNER_DEAD
```

### 5.4 发车后必查（**三道验证，缺一不算发车成功**）
```bash
# ① 进程活着
pgrep -cf 'run_sweep_v[2]'
# ② environ 实证（进程活着 ≠ env 对！11-18 踩过：进程健康但网格口径全错）
P=$(pgrep -f 'run_sweep_v[2]' | head -1)
tr '\0' '\n' < /proc/$P/environ | grep -E 'SWEEP_V|SURF_LEVEL|FIN_LEVEL|OUT_CSV'
# ③ 首个 case 的 PHASE/建网日志有进展
tail -5 ../sweep_t1/sweep.log
```

---

## 6. 边界与禁令（血泪教训，务必读完）

### 6.1 绝对不能做
| 禁令 | 事故依据 |
|---|---|
| **不要 pkill 匹配自己命令行的进程** | `pkill -f 'xxx'` 会匹配到执行它的 shell 自身（10-31 自杀陷阱）；用 `[n]` 字符类断自匹配 |
| **不要在跑着的 `run_sweep_v2.sh` / `case_template` 上直接改** | bash 增量读脚本，改运行中的脚本会导致诡异语法错误；模板改动只影响后续新建 case，存量 case 需单独热修 |
| **不要忽略 `PHASE0` 的 `parts=/fins=` 计数** | GPU LBM 的 `read_stl_raw` 若路径错会 `parts=0` 且**静默出力恒为零**（11-16 事故：白跑 3 例） |
| **不要用 GPU LBM 出力矩可信数据** | LBM Re≈1.1e3 vs OpenFOAM 1.5e5，升力类量差 14 倍（N2 结论）。GPU 只做定性/量级/快扫 |
| **不要跨机直接对比绝对力值** | 必须先 Nx² 归一化再比（LBM 晶格标度律 p=−2.001） |

### 6.2 数据纪律
- 表 **append-only**：只追加不修改历史行
- **V15/V30 冷备**：旧域数据保留但不参与交付表
- 交付表 `guidance_sim/aero/aero_table.csv` 必须是**完整笛卡尔积**（缺格会被 `lookup_aero.from_csv` 拒绝）
- 每行带 `residual_rel`：未收敛的行要 WARN 标注，消费方自行判断

### 6.3 依赖耦合（重构时注意）
- `openfoam/airframe-sweep` 与 `wt_jobs` 被在跑产线和桌面 schtasks 硬引用 —— **物理移动需先改所有引用方**
- `extract_damp.py` 的对拍锚点硬引用 `wt_jobs/tmp/osc_f4/cache/`

---

## 7. 接入检查清单（打勾即上岗）

- [ ] Tailscale 入网，`ping 100.90.63.31` 通
- [ ] OpenFOAM v12 三件套（blockMesh/snappyHexMesh/foamRun）在 PATH
- [ ] 仓库 clone + 30 个 STL 齐
- [ ] `mass_properties.json` 与主控机一致（md5 比对）
- [ ] 单例全链路冒烟通过（mesh 有 `Finished meshing` + `Layers added`）
- [ ] **对拍：力系数 <2%、力矩 <10%** ← 唯一硬门槛
- [ ] 发车脚本三件套自检在位
- [ ] 发车后 environ 实证通过
- [ ] 认领的工况区间与其它机器不重叠
- [ ] 已读 §6 全部禁令

---

## 8. 排障速查

| 症状 | 根因 | 修法 |
|---|---|---|
| `blockMesh: 未找到命令` | 启动脚本没 source bashrc（setsid 裸环境） | 脚本里显式 `source /opt/openfoam12/etc/bashrc` + 三件套自检 |
| snappy `keyword XXX is undefined` | 字典与 OF 版本不匹配 | 用 `$FOAM_ETC/caseDicts/annotated/snappyHexMeshDict` 作底稿整块对齐（不要逐键补） |
| `Cannot find file "points" in polyMesh` | blockMesh 没跑成/没跑 | 查 `log.blockMesh` 尾部真实错误 |
| `SIGFPE` / `Floating point exception`（a0_b0 或大攻角） | 压力-速度耦合启动发散 | `fvSolution` 松弛 p/U 0.9→**0.5**（(k|omega) 留 0.85），已治愈 4 例 |
| 力恒为零（GPU） | 几何未加载（`parts=0`）或 TYPE_X 未标 | 查 PHASE0 打印；逐零件体素化 |
| 力矩符号/量级诡异（GPU） | `object_torque` 域中心化坐标 bug | `T_true = T_rep + (Nx/2,Ny/2,Nz/2)×F` 后处理恢复 |
| mesh 复用但流场错 | clone 的边界值 sed 未生效 | 查 `clone_case.sh` 的 U_inlet 校验输出 |

---

## 9. 联系与协调

- 协调方：CFD 侧主会话（分工分配/区间认领/合并表）
- 开工前先看：`devlog/<当日>.md` 与 `memory/domains/wt/events.jsonl` 最近条目 —— 避免重复踩已修的坑
- 报进度：完成工况数 + 首例耗时 + 对拍偏差，回给协调方并表
