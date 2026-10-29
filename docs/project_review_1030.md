# 项目全量审查 v4 — 几何修正时代的代码与实况核查

> 2026-10-30 凌晨 | 曼波: "再次全量审查项目, 代码和实际工作情况分析, 完成下一步部署, 整理文档"
> 上接 `project_review_1029.md` (v3)。本版 = 基准事故后的第一次全面体检。

## 1. 实况核查 (取证时间 01:00-01:15)

| 线 | 状态 | 证据 |
|---|---|---|
| T0-v2b 蓝表 (填实几何 v2) | 第三次清表重跑 (01:07), case#1 建网格中 | sweep.log / 引擎 PID 确认 |
| 链式 T1-v2 | 在岗 (chain_t1_v2.sh, **完成判据版**: 引擎消失 + t0_table≥360 行才放行) | PID 385521 |
| T2 R8b (LBM) | 三版完跑对照: 无孔 0.245 / 全锥填 0.221 / 圆柱填 0.247 lu | forces_*.csv ×3 |
| 桌面 | J1/J2/J3 任务包全链路通 (拉表+审计+仪表台 4.9s) | 本轮实跑 |

**审查中抓到并处置的实况问题**: 孤儿 snappyHexMesh 污染求解——引擎被 pkill 时网格子进程存活,
往新引擎的 case#1 里覆盖写 polyMesh。处置: 杀孤儿+清表重启; 根治: 启动器 pkill 列表补全
(snappy/blockMesh/decompose/reconstruct), T1 启动器同款补丁。**教训: 进程树击杀, 不杀单点。**

## 2. 代码审查 (本轮新增/修改脚本)

| 脚本 | 审查结论 |
|---|---|
| `fit_hinge_axis.py` | ✅ 逐切片孔径带 (r 1.15-2.25) 圆拟合 + 圆心串 TLS; RMS 0.000 证明 CAD 级直线; **隐患: 依赖旧 hinges.json 做方向种子** — 若换镖体需先跑 find_hinges.py |
| `fill_nose.py` (v2) | ✅ 圆柱填充体参数化明确; 体积+2.51cm³ 与腔体积分吻合; 2-流形 0 坏边; **原件备份 .bak_nosehole 在** |
| `fuse_body.py --fill-nose` | ✅ 直连网格化优先 (healShapes 兜底); **注意: 填充参数与 fill_nose.py 是两处硬编码, 换几何要同步改** |
| `check_fin_sweep.py` | ✅ 扫掠干涉验证 (±45° 零穿透); 近距用点云哈希近似非真面距 — 够用但不精确到 0.1mm |
| `cyl_census.py` | ✅ 普查工具; bb 键名有误导 (bb_zmin 实为 zmax) — 普查用完即弃, 不修 |
| `wt_jobs/lib/*` | ✅ verdict 子串匹配已修; sync 幂等; **A1 的 Cm 零点离散虚高**待蓝表满后调 tol |
| `deflect_stl.py` (下游) | ✅ `A, B = surf["hinge_line"]` 两端点解包 = 与修复后结构匹配; 舵效层前置条件成立 |
| `run_sweep_v2.sh` | ✅ 引擎本体无改动; OUT_CSV 链 (qianli t0_table → J1 拉取) 通 |

**结构事故复盘 (hinge_line 写坏)**: 下游 3 个消费方 (deflect_stl/dashboard/未来 MuJoCo) 都按
"两端点"语义读; 我更新时凭记忆写成了逐分量对。**修正流程: 改共享 JSON 前先 grep 消费方的
读取代码** — 已写入复盘 v3 的流程修正条目, 本次是它的第一次实战失败 (没执行), 引以为戒。

## 3. 数据资产台账 (当前有效)

| 资产 | 状态 |
|---|---|
| `guidance_sim/aero/aero_table.csv` | **空 (等待 T0-v2b)** — 当前无有效主表 |
| `aero_table_foldedfin_T0.csv` | v0.9 红表 364 点 (归档, 全舵满偏 45° 标定点) |
| `sweep_t1_foldedfin_T1/` (qianli) | v0.9 红表 T1 36 工况 (归档) |
| 几何真源 `cad/v1/cfd_parallel/` | 平行基准 + 填实 body + 孔心铰链 assembly ✅ |
| LBM 三版力数据 (qianli out/) | forces_r8_folded(body-only) / r8b_fullcone / r8b(cyl) |

## 4. 下一步部署 (依赖排序, 已在轨)

```
[P0] T0-v2b 蓝表 364 工况 (qianli, ETA 10-31 晚) — 无人值守
      桌面 J1 每日拉表 + audit A1-A6 (含 A6: CY(β=0)≈0 / β镜像恢复 / CL_α 漂移<8%)
[P1] 蓝表满 → 拉回合入 aero_table.csv → lookup_aero 回归 → v0.96 交付
[P1'] chain_t1_v2 自动续 T1-v2 (L6/L8, ~9.6 天) — 无需人守
[P2] 舵效层 (单舵 ±10/±20°): 前置条件已全部验证 (deflect_stl 消费 ✅ / 扫掠零穿透 ✅ /
     折叠方向确认 ✅), 排 T1-v2 之后; 每舵独立角走 --angles 直传
[P2'] T2 已完成阶段性使命 (瞬态管线 + 三版几何对照); 下一步 = 大攻角瞬态专项 (α=±12.5/15°)
      与 FVM 趋势对拍 → v1.0 拟真度背书
[P3] RL 期按需补点通道 (append-only + 热加载) — 协议已定, 等 RL 侧开跑
```

**桌面职责**: audit 审查 / 拉表合并 / git 中心 / 仪表台 (J1+J2) / 文档。生产全部在 qianli。

## 5. 风险登记 (滚动更新)

| 项 | 等级 | 缓解 |
|---|---|---|
| T0-v2b 第三次重跑 (前两次: 错基准 / 过度填孔) | 已消化 | 几何真源已冻结 — **下次几何变更必须曼波点头** |
| chain 误触发 | 已根治 (v2 完成判据) | 桌面每日 ssh 探活 |
| 孤儿进程污染 | 已根治 (启动器全杀) | 重启后查 `pgrep snappyHexMesh` 应 ≤1 |
| mass_properties 占位 | **高** | 等曼波实机称重 — 积分链最大不确定性 |
| 视觉侧 MuJoCo 对齐清单 | 中 | 待曼波转交回复 |
| LBM 绝对量级不可信 (阶梯噪声) | 已定性 | 绝对量级以 FVM 为准; T2 只做趋势/瞬态 |

## 6. 文档更新清单 (本审查配套)

- `dataset_delivery.md` → **v0.96-preview**: 基准+几何双变更声明、缺口声明 (舵维层2/3 未跑、动导数边界、质量参数占位)
- 本文档 (project_review_1030.md)
- `devlog/2026-10-29.md` 增补 (跨零点段) / `devlog/2026-10-30.md` 新建
- 记忆库: guidance-loop-project-status (几何修正 + 事故三连) / compute-node-multimachine (进程树击杀)
