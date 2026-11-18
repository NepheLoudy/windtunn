# 镖体气动仿真 — 面向强化学习控制的气动数据集与全链路 CFD

**一句话**: 给真实飞镖镖体 (南航镖复刻构型, X 布局四板翼 + 四片尾缘舵) 建一条
CAD → 网格 → 求解 → 气动表的全链路 CFD 产线, 产出强化学习飞控**直接可查**的
定常气动数据集 —— 状态 (V, α, β, δ) → 六分量力/力矩, 运动积分归 MuJoCo。

新读者按身份走:
- **视觉/算法侧 (RL/制导)** → 读 [§ v0.97 交付](#v097-交付-2026-11-15-handoff) +
  [docs/dataset_delivery.md](docs/dataset_delivery.md) §0 (五分钟接入);
- **CFD/产线侧** → 读 [§ 全链路管线](#全链路管线) + [AUTOPILOT.md](AUTOPILOT.md) (无人值守规程);
- 想了解风洞实物 → 直接跳 [§ 风洞技术栈 (ver1.0 遗产)](#风洞技术栈-ver10-遗产)。

```
WindTunnelSuite/
├── README.md            ← 本文件 (镖体主线总览)
├── docs/                镖体优先文档 (交付/规格/路线/排期) + legacy-windtunnel/ 风洞遗产线文档
├── guidance_sim/        闭环仿真 + 气动查表: sim_core/detector/guidance/eval + aero/ (主表+lookup+damp)
├── openfoam/            airframe-sweep = 镖体扫气产线 (主线); windtunnel-base/mrf = 风洞遗产 case
├── wt_jobs/             扫气任务队列 / 仪表台 / 探针-guard (qianli 链式生产)
├── wt/                  数据分层工具 (NAS vault 归档, 见 docs/data-vault.md)
├── renders/             渲染成果图
├── WindTunnel3D/        [遗产] 桌面风洞 GPU LBM (FluidX3D) 管线
├── FanSim3D/            [遗产] 供风离心风机 GPU LBM 管线
├── AUTOPILOT.md         无人值守自动化手册 (跨线基建, 定时任务唯一入口)
├── devlog/              全程决策与踩坑日志 (审计链)
└── memory/              域事件流 (wt 域, 全程可回放)
```

> 仓库可整体挪到任何盘符任何路径直接使用 (无盘符硬编码, 相对推导 + 环境变量覆盖,
> 详见各子目录 README)。物理目录 `openfoam/airframe-sweep` 与 `wt_jobs` 正被
> qianli 产线与桌面定时任务引用, 暂不移动。

## v0.97 交付 (2026-11-15 handoff)

| 件 | 路径 | 状态 |
|---|---|---|
| **气动主表** | `guidance_sim/aero/aero_table.csv` — **546 工况** = V{20~25 m/s 六档} × 13α × 7β 完整笛卡尔格 (δ=0, T0 全表 546/546 于 2026-11-15 达成) | ✅ |
| **查表实现** | `guidance_sim/aero/lookup_aero.py` — 纯 numpy 引擎无关, 三线性插值, 出域钳位+RuntimeWarning (警告即补点信号), 表更新热加载 | ✅ 自测 7 项 + 生产端往返对拍 89 点恒等 (2.8e-15) |
| **动导数 damp** | `guidance_sim/aero/damp_defaults.json` — Cmq=−0.0879 / Cnr=−0.0911 / Clp=null, `lookup_aero` 默认启用 | ✅ 实装 |
| **舵效 T1q 表** | `delta_table_t1q.csv` — 10 位形 (8 单舵 ±10° + 2 合成) × L6/L8 (ET600), 增量=δ行−d0 行叠加 | ✅ 已入库 |
| **几何真源** | `openfoam/airframe-sweep/cad/v1/cfd_parallel/` — B 系平行基准 (δ=0=舵面平行弹轴, 填实镖头深孔, 铰链=孔心精拟合 v4 真轴) + `glider.mjcf` (MuJoCo 3.16 实测加载) | ✅ |
| **交付文档** | [docs/dataset_delivery.md](docs/dataset_delivery.md) — 口径/限制/责任分工的真源 (§0 交接指南 → §0.2 五分钟接入) | ✅ |

五分钟接入: `sys.path` 指到 `guidance_sim/aero` 后
`lookup_aero(V, alpha, beta, de, da, dr) → (F_B, M_B)` —— 完整 Quickstart 见
[dataset_delivery.md §0.2](docs/dataset_delivery.md)。

## 核心气动结论 (RL 增稳设计的定量输入)

| 结论 | 实测铁证 | 含义 |
|---|---|---|
| **双轴强静不稳定** | Cm_α = **+0.59/rad** (线性区 \|α\|≤5°, R²=0.999; 5~10° 段 +0.21, 拐折双向复现); Cn_β = **−0.434/rad** (α=0 剖面, R²=0.993) | 弹体天然发散, **增稳是 RL/制导的硬责任, 纯 PN 外环必发散** (不只是"飘") |
| 升力线性 | CL_α = +2.40/rad (R²=1.000), ±10° 线性 + ±15° 弯曲 | 可信域 α/β∈[−15,15°] 内插值安全 (15°=奖励终止阈值, 表边界对齐) |
| **8 项特征验收 8/8 兑现** | 镜像 CY 2.8% · 跨 V 力钝感 0.3~0.4% · 压心随 α 系统移动跨 V ±0.3mm · β=±15° 失速回落 · CL ±15° 对称剖面 (564 行复核, 脚本可复现) | 数据集与规划文档零偏差, 出处 [dataset_delivery §0.7](docs/dataset_delivery.md) |
| **damp 口径** | Cmq=−0.0879 / Cnr=−0.0911 (tfixed 口径, N1 力矩 bug 修正后); k≈8.7 **远超准定常域 k<<1** → 同频等效阻尼 (保守偏小); Clp 低于噪声底不可提取, 诚实置 null (滚转无阻尼补偿) | 防 RL 高频抖舵; 大角速度机动误差上升, 详见 [dataset_delivery §3](docs/dataset_delivery.md) |

已知边界 (诚实清单): GPU 线 Re 限界与 LBM 壁干扰 (定性结论可用, 量级以 OpenFOAM 线为定量真源) /
com·惯量 PLACEHOLDER (实机称重前力矩绝对精度以此为上限) / X 布局四舵独立角与 + 布局混控约定不混用
—— 全部七条见 [dataset_delivery §0.4](docs/dataset_delivery.md)。

## 全链路管线

三代版本谱系 (实物风洞 → 全链路架构 → 纯数据集) 总览:
[docs/aeroacoustic_project_versions.md](docs/aeroacoustic_project_versions.md) (ver1.0→1.2)。
当前产线架构 (ver1.1, 双引擎 + 审计链):

```
CAD (STEP 30 实体) ──解析──> 镖体装配 (B 系, 114.6×239.3mm, X 布局四板翼+四舵 δ1..δ4)
   │                              │
   ├─ deflect_stl.py (v4 真铰链轴) ──> δ-位形几何 (独立 Rodrigues 自检 ±10.0000°)
   │
   ├─==> OpenFOAM v12 (CPU, qianli 链式) — snappyHexMesh L5/L7→L6/L8, simpleFoam k-ω SST
   │       make_case → clone_case(网格复用) → run_solve → post_process(风轴系数) → aero_table
   └─==> FluidX3D (GPU 5070, 桌面)    — LBM 瞬态/分支/舵效快扫 (300k 步 ~4min/例)
           逐零件体素化+装配变换 (v4asm) — 定性结论源 (结构/分支/手性/定常)
```

- **跨引擎互证**: FVM↔LBM 对拍 CD −0.14% (六项全<2%); 生产端↔lookup_aero 风轴往返 89 点 2.8e-15;
  同输入重跑 bit-identical。**OpenFOAM 线 = 定量真源, GPU 线 = 定性结论源 + 快扫**。
- **生产纪律**: qianli 链式生产 (桌面退出数据生产); 断电三防 (桌面哨兵 30min 拉回 + recover 回填 +
  chain 补跑); 表 append-only, 出域警告即补点队列。多机协作协议见
  [docs/compute_node_protocol.md](docs/compute_node_protocol.md);
  **新机器加入算力池**（环境/冒烟/对拍/发车三道验证/禁令速查）见
  [docs/new_node_onboarding.md](docs/new_node_onboarding.md)。
- **数据分层**: 大体积运行数据 (vtk 快照 ~110G+) 跑完即归档 NAS vault, 本地只留运算端 ——
  `bash wt/wt.sh push/pull`, 手册 [docs/data-vault.md](docs/data-vault.md)。
- **对接文档链**: [guidance_loop_dev_spec.md](docs/guidance_loop_dev_spec.md) (接口/坐标系/验收) →
  [control_approach_roadmap.md](docs/control_approach_roadmap.md) (B 保底/A 蒸馏) →
  [guidance_sim/README.md](guidance_sim/README.md) (闭环代码) →
  [openfoam/airframe-sweep/README.md](openfoam/airframe-sweep/README.md) (扫气工作区)。
- 算力排期与拟真度路线: [compute_schedule_1108.md](docs/compute_schedule_1108.md) /
  [fidelity_acceptance_1101.md](docs/fidelity_acceptance_1101.md);
  架构审查: [architecture_review_1103.md](docs/architecture_review_1103.md)。

## 交接与升级路径

| 里程碑 | 内容 | 状态 |
|---|---|---|
| 实机称重 → recompute_cm | 曼波提供质量/com/惯量数值 → `openfoam/airframe-sweep/recompute_cm.py` 零重跑重出全表力矩 (分钟级) | 链路就绪待数值 |
| 舵效 delta-mode 查表 | 基座=T0 表插值 + delta 表最近锚叠加, 四舵独立角口径 | 设计稿待对接会冻结 |
| T1 基座 546 (力矩可信档) | L6/L8 带层, ~14.5 天, 排后面; 扩域二期 (V10-15 / ±25°) 见 compute_schedule_1108 | 阈值已就位 |
| RL 期间按需补点 | append-only, lookup 出域警告即信号; 舵效姿态/位形随要随扩 | 常态运行 |
| v1.0 完整版 | T1 力矩档 + 舵效带层重扫 + N4 域重设计 (GPU 量级精化) | 排期中 |

开放项与责任分工: [dataset_delivery §0.6](docs/dataset_delivery.md)。

## 风洞技术栈 (ver1.0 遗产)

> **历史遗产线** — 当前主线为镖体数据集 (见上)。本节保留实物风洞技术栈的入口与关键结论,
> 供二期物理重构与溯源; ver1.0 由**张郭浩**负责实物落地 (3D 打印风机蜗壳/扇面/风洞结构)。

- **[WindTunnel3D/](WindTunnel3D/README.md)** — 桌面风洞 (试验段 300×200×200mm, 目标 25 m/s):
  1D 设计 → MATLAB 体素化 → FluidX3D GPU LBM → 渲染/报告; 与 OpenFOAM 五段 blockMesh
  (57600 格 simpleFoam k-ω SST) 交叉验证 **22.00 m/s 完全一致 — 22 m/s 是物理真实值**
  (25 m/s 差距 = 涵道沿程损失, 非仿真精度问题)。转速稳定窗口实测 790✗/960✓/1080✗/1180✓ rpm。
- **[FanSim3D/](FanSim3D/README.md)** — 抽风式离心风机 (D2=460mm 前弯多叶, 960rpm):
  1D 性能模型 → 几何/体素化 → FluidX3D; 与 WindTunnel3D 经定位器相对引用 (无盘符硬编码)。
- **openfoam/windtunnel-base / windtunnel-mrf** — 风洞 OpenFOAM 稳态 case (五段 blockMesh +
  MRF 叶轮全域 666k 格), 生成器 `WindTunnel3D/openfoam/gen_openfoam_mrf.m` 单一真源重建。
- **docs/legacy-windtunnel/** — 风洞线文档已归档于此 (git mv 保历史):
  [transient_rotation_plan.md](docs/legacy-windtunnel/transient_rotation_plan.md) (瞬态旋转两阶段方案) /
  [eval_3mm_of.md](docs/legacy-windtunnel/eval_3mm_of.md) (3mm 交叉验证可行性) /
  [gpu_plan_1101.md](docs/legacy-windtunnel/gpu_plan_1101.md) (GPU 利用计划) /
  [delta_early_plan_1104.md](docs/legacy-windtunnel/delta_early_plan_1104.md) (涵道线舵效排期)。
- 风洞→镖体的传承: **ver1.1 把镖体放进 ver1.0 标定的流场知识之上**, 同一仓库的求解器栈
  (FluidX3D/OpenFOAM) 与审计纪律沿用至今 —— 谱系见
  [aeroacoustic_project_versions.md](docs/aeroacoustic_project_versions.md)。

---

*数据出处: 本 README 全部数字来自仓库实测记录 (devlog/ 逐日 + memory/domains/wt/ 事件流 66+ 条,
任何一条可回放到原始日志与脚本)。项目复盘: project_review_* 系列 (跨线)。*
