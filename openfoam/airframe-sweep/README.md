# airframe-sweep — 弹体气动库 CFD 侧工作区 (M0)

对接文档: `../../docs/guidance_loop_dev_spec.md` (v0.6) · MuJoCo 对齐清单: `../../docs/mujoco_alignment_questions.md`

## 定位

制导闭环全仿真的 CFD 侧交付 (**曼波/仿真数据集**): 参数化几何 → OpenFOAM v12 扫气 →
`guidance_sim/aero/aero_table.csv` + 查表参考实现 `guidance_sim/aero/lookup_aero.py`。

## 结构

| 路径 | 内容 | 状态 |
|---|---|---|
| `gen_airframe.m` | 参数化几何生成器 (MATLAB, flat/cone 头型; STL×5 + inertial + MJCF + 参数 JSON) | ✅ v1 |
| `geometry/` | 生成产物 (B 系 x前y右z下, 米制) | ✅ |
| `case_template/` | OpenFOAM v12 弹体绕流扫气 case 模板 (V/α/β/de/da/dr 长表输出) | ⬜ 待冻结会议后建 |

## 已验证 (2026-10-14)

- 生成器三重自检: 薄片积分惯量 vs 解析 (1.2e-05) / STL 包围盒 / 闭合体积 (1.6e-03)
- cone 模式独立验证 (质心后移 -0.0918, 惯量下降, 体积对拍 PASS)
- **MuJoCo 3.16 真机加载** `geometry/glider.mjcf`: 6 body/5 joint/10.2 kg, 惯量逐位一致;
  3s 自由落体 z = -44.17 m ≈ ½gt² (解析), qacc=9.81 纯重力, 无 NaN
- `lookup_aero.py` 自测 6/6 (网格回读/插值/出域 clamp+warning/力矩符号/CSV 闭环)

## 扫气管线 (2026-10-21 建)

| 文件 | 作用 |
|---|---|
| `case_template/` | OpenFOAM v12 case 模板 (blockMesh 远场 + snappy 弹体 + forces 采样) |
| `make_case.sh <V> <α> [β] [dest]` | 实例化一个工况 (自动算来流矢量/湍流量/CofR) |
| `run_case.sh <case> [nproc]` | blockMesh → snappyHexMesh → checkMesh → decomposePar → foamRun 并行 |
| `post_process.py <case>` | forces 时均 → 风轴 CL/CD/Cm/CY/Cl/Cn → 追加 aero_table.csv |
| `run_sweep.sh <root> [nproc]` | 全参数网格扫气 (断点可续, 已有 results.json 跳过) |

```bash
# 单工况
./make_case.sh 25 4 0 ~/openfoam/airframe-sweep/run_V25_a4
./run_case.sh   ~/openfoam/airframe-sweep/run_V25_a4 8
python3 post_process.py ~/openfoam/airframe-sweep/run_V25_a4 --json r.json

# 全表: 按《飞镖闭环仿真方案讨论》的安全阈值 (α/β ±15°, V 15-25)
SWEEP_V="15 20 25 30" SWEEP_ALPHA="-15 -10 -5 0 5 10 15" SWEEP_BETA="-15 -10 0 10 15" \
  ./run_sweep.sh ~/openfoam/airframe-sweep/sweep 8
```

**算量预算** (单工况 7 分钟 / 32.5 万格 / 8 进程):

| 阶段 | 网格 | 工况数 | 机时 |
|---|---|---|---|
| 阶段 1: 气动基线 (δ=0) | V 5 × α 7 × β 5 | 175 | ~20 h |
| 阶段 2: 舵效 (选点扫 de/da/dr) | 选 5 个 (α,β) 点 × de 9 × da 3 | 135 | ~16 h |
| 阶段 3: 加密/复核 | 按敏感区补 | ~50 | ~6 h |

阶段 2 只扫舵效不需要全笛卡尔积: 三线性插值在舵偏维可假定近似线性, 9 点足够定位
效率与非线性拐点。**总预算 ~40 机时**, 台式机夜间分几天可跑完。

**约定**: 来流矢量 = −V(cosαcosβ, sinβ, sinαcosβ) (空气相对弹体速度的方向);
力矩参考点 = CofR = 全系统质心 (airframe_params.json `system.com`);
风轴: 阻力沿来流, 升力 = 垂直于来流的弹体系"上"分量 (α>0 → CL>0, F_z<0)。

### 网格策略与已知限制 (定量表前必须处理)

- **基础网格 0.3m > 弹径 0.15m** — 表面会完全落在格子内部、与网格边零相交, snappy 不加密。
  必须靠 `refinementRegions` 的 `airframeBox` (level 4 = 18.75mm) 先把近体区提上来。
  这是 snappy 的经典静默失败: 日志显示 "Number of intersected edges : 0" + 格数不变。
- **薄舵 3mm 与网格尺度矛盾**: 校验档舵面 level 5 (9.4mm) 远大于舵厚, 舵面基本被"糊"进流体,
  力贡献不可信。定量表前需二选一: ①局部细化到 level 7-8 (2.3/1.2mm, 格数暴涨) 或
  ②舵面按零厚度 baffle 处理 (`faceType baffle`), 或用加厚舵做敏感性修正 — **待冻结会定**。
- 校验档 = 近体 level 4/5、无边界层 (`addLayers false`)、k-ω SST 壁面函数; 定量档再开层。
- 12 核 WSL2 / 7GB 内存: 32.5 万格 8 进程约 0.5 h 内收敛 (见 devlog)。

## 校验点结果 (2026-10-21, V=25 m/s, α=4°, β=0, δ=0)

跑法: `make_case.sh 25 4 0` → `run_case.sh ... 8` → 800 步 / 32.5 万格 / 8 进程 / 约 7 分钟。

| 量 | 值 | 物理检查 |
|---|---|---|
| CL | **+0.2773** | α>0 → 正升力 ✓ |
| CD | **0.7851** | 平头圆柱按迎面积 S_ref=πR², 0.8 量级合理 ✓ |
| Cm | **−0.5789** | 负 = 低头 = 静稳定 (Cmα ≈ −8.3 /rad) ✓ |
| CY / Cl / Cn | −0.0014 / +0.0021 / +0.0099 | 对称构型应≈0 ✓ |
| 末段力振荡 | 0.000 | 力已 4 位稳定 |
| 残差 (t=800) | Ux 1.4e-4 / p 3.9e-4 | 未到 1e-5 但力稳定; 定量档需 1500-2000 步 |

**这批数字只用于链路与符号校验, 不进 aero_table.csv** — 舵面在 level 5 (9.4mm) 下
远粗于 3mm 舵厚, 升力/稳定性由舵面主导, 定量不可信。见下节网格策略。

## 数据集资产登记

- **v0 旧镖体气动数据集**: 曼波已于本项目对接前**自行跑过一轮飞镖气动数据集**
  (2026-10-16 口述补录; 数据位置/格式/工况范围待登记)。因**镖体几何此后发生变更**,
  v0 数据对新镖体作废, 需按新镖体重跑 — 对接可用的第一版表仍以 v1 重扫为准。
- **重跑策略 ("改镖体=重跑"固化为管线约束)**: 几何参数 (`gen_airframe` cfg) → STL →
  snappy case → 扫气 → `aero_table.csv` 全链参数驱动, **换镖体只改配置不改代码**;
  case 模板设计把"换镖体"当一等公民 (镖体变量只进 meshDict/扫气脚本配置, 禁止散落硬编码)。
- 若 v0 为散文件格式 (逐工况目录/表格), 重跑时顺手统一到 spec §4.1 长表口径,
  不做旧格式适配层。
- 登记待补 (等曼波): v0 数据位置 / 旧镖体几何参数 / 工况范围 / 可复用结论
  (如 CD 量级、失速特性 — 校验 v1 重扫时可比对量级)。

## 下一步 (按依赖顺序)

1. **Phase 0 冻结会议** (`mujoco_alignment_questions.md` 六节逐条回复): 变更范围 (MuJoCo 只渲染 vs 承载 6DOF)、S_ref/L_ref/符号约定、β 与舵偏扫气范围 — **先于扫气, 否则白扫**
2. 扫气 case 模板: 复用 openfoam/ 风洞管线经验 (WSL2 Ubuntu-24.04, v12 incompressibleFluid + k-ω SST), 弹体用 `geometry/*.stl` (snappyHexMesh), forces 采样挂全弹面
3. 校验点 V=25, α=4°, δ=0: 查量级 (CL~2π·rad(α) 量级) + Cmα<0 静稳定性
4. 全表扫气 → `aero_table.csv` (spec §4.1 长表) → 与 `lookup_aero.py` 联测
5. 占位替换: `aero/placeholder.py` → `lookup_aero.py` (注意 Bp↔B 系转换, 签名已对齐)
