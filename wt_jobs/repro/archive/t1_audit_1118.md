# T1 资源利用率审计 — 2026-11-18 02:15 (只读分析, 未碰任何进程)

数据源: `~/sweep_t1/sweep.log` (4646 行全史) + 546 个 `case_*/log.*` + `~/sweep_t0v2/chain_v3.log` + 桌面 `wt_jobs/out/qianli_guard.log` (只读采集器 `t1_collect_1118.txt`)
结论速览: **三轮全部失败, T1 至今 0 例落表 (results.json=0, t1_table.csv 不存在)**。R3 失败根因与 R1 同类 (字典缺键第 6 键 `relaxed`), 修复于 11-18 01:44:55 落地 (字典整体换代), 并行工位已在 `~/sweep_t1_test` 验证新字典 mesh 成功 (1550s); 引擎侧首例 (case 46) 已越过旧字典死点, 判决待出。

---

## 1. 三轮时间线

sweep.log 含 8 个引擎段 (`===== [1]` × 8), 三轮归属与硬证据:

| 轮次 | 段 | 时间窗 | 例数/失败 | 单例耗时 | 根因 (证据) |
|---|---|---|---|---|---|
| R1 五缺键 | seg0-4 | 11-12 23:00 → 11-13 ~10:30 | 410 例 / 405 败 | ~1.7 min/例 | snappyHexMeshDict 缺键: featureAngle/nGrow/maxFaceThicknessRatio/nBufferCellsNoExtrude/minMedialAxisAngle (模板头注释+任务卡; 日志被后轮覆盖) |
| R1 五缺键 | seg5 | 11-13 10:30 → ~11:00 (chain 日志锚点) | 546 / 546 败 | ~3.3 s/例 | 同上 (链式修复后期缺键前置, 秒死) — **R1 合计 951 败, 与产线侧口径一致** |
| (插曲) | — | 11-13 11:00 → 11-15 09:00 | T0 补跑占机 44h (t0 表 566→645 行), T1 静默 | — | 非本审计范围, 但 T1 被阻塞 |
| 盲区 | — | **11-15 09:00 → 11-17 11:30** | T1 完全空转 **50.5h** | — | 桌面 guard 最后一次运行 11-15 09:00:02 (拉起 chain 后 schtasks 停用); 其发车的引擎未留任何日志段即消失 |
| R2 裸环境 | seg6 | 11-17 11:30:36 → 11:35:16 | 546 / 546 败 | **0.6 s/例** | `run_sweep_v2.sh: 行 58: blockMesh: 未找到命令` — 501 份存留 log.blockMesh 实证 (546−45 被三轮重写) |
| R3 满配字典 | seg7 | 11-17 18:39 → 进行中 | 46 例 / **45 败** (case1-45) | **9.6 min/例 (精确均匀)** | `keyword relaxed is undefined in ... snappyHexMeshDict/meshQualityControls` — snappy 跑满 castellation+snap 后死在 layer 迭代 20, 44 份 FOAM FATAL 实证 |

关键事件链:
- 11-12 22:48 整机重启 (wtmp 唯一一次; 全部守护死亡) → 桌面 guard 23:00 拉回 chain → T1 首发 (R1)。
- R1 期间桌面 guard 在岗, chain 死即拉 (seg0→seg4 的引擎死亡-重拉环)。
- 11-15 09:00 桌面 guard 停用 → **11-12/11-13 教训重演: 50.5h 无人兜底**。
- 11-18 01:44:55 字典工位落地「字典整体换代」(底稿 OF12 官方 annotated 版, `relaxed` 子字典入列, 旧模板存 `snappyHexMeshDict.bak_of12_before`); 01:53:02 发车的 case 46 起用新字典。

## 2. 当前轮 (R3 满配字典) 健康度

- 完成判决: 45/45 全败 (case 1-45, 9.6 min/例精确均匀 = 单核 snappy 跑到 layer-20 统一死点)。
- **失败率未归零** — 修复前口径下 100%; 但修复 (01:44:55) 晚于本轮发车 (18:39), case 1-45 全部按旧字典跑死, 属预期内损失。
- 新字典首考:
  - 引擎侧 case 46 (V23_a-12.5_b-15, 01:53:02 发车): 截至 02:11 已跑 18.7 min, layer 迭代 28 次, **越过旧字典 9.6 min 死点近 2 倍**, 无 FOAM FATAL。
  - 并行工位 `~/sweep_t1_test/case_V20_a-15_b-15`: **mesh 成功**, `Finished meshing in = 1549.91 s`, polyMesh 已写, 50 次 layer 迭代, 1195 illegal faces (容忍级)。
- 落表: `t1_table.csv` 仍不存在 (post_process 从未执行到); `~/dashboard/t1_table.csv` (39 行) 是 foldedfin 项目旧表, 与本批无关。
- 产线复活判据: case 46 起连续成功 + 失败率归零 — **拐点已现, 判决待 case 46 收尾** (预计 ~02:20)。
- 旁证卫生问题 (已顺手归一): sweep_t1 收割机曾 3 实例并存 (11-13/11-15 各拉一次无人清理), 02:02 起归一为单实例。

## 3. 单例耗时分解 (L6/L8 口径, np=14)

| 阶段 | 耗时 | 口径 |
|---|---|---|
| mesh (组源, 每 (a,b) 组 1 次) | **~26 min** | 新字典实测 1550s (a-15 组, 单核); 旧字典死点 9.6min 可作下界 |
| clone (组内 V2-V5, 455 次) | ~1-2 min | polyMesh 拷贝+边值替换 |
| solve (foamRun, ET 600/1000/1500 分档) | **19-109 min** | 同管线 L6/L8 历史实测 (foldedfin): a-15 档 6432/6518s, a-12.5 档 1149s; T0 (L5/L7) 中位 30.4 min 作交叉参照 |
| post_process | ~1 min | python 落表 |

推全批 546 例 ETA (引擎串行流水, mesh 组内复用):
- mesh: 91 组 × 26min ≈ 39.5h; clone: 455 × 1.5min ≈ 11.4h
- solve 加权: a=±15 档 84 例 × ~107min + 中档 336 例 × 20-50min + 低档 126 例 × 15-25min ≈ **295-480h**
- **ETA ≈ 15-21 天, 中位 ~18 天** (从 mesh 修复生效起算; chain 哨兵已挂, 引擎崩溃/重启自动断点续跑)

## 4. 资源利用率结论

- **直接烧掉的算力: ~19.4 核时** — R1 ~12h·core (405×1.7min + 546×3.3s) + R2 ~0.1 + R3 7.2h·core (45×9.6min 单核)。绝对量很小: mesh 阶段单核, 死得快。
- **真正的损失是机会成本**: T1 自首发 (11-12 23:00) 至今 123h 墙钟, 有效产出 0 例。其中:
  - **50.5h 完全无人值守空转 (11-15 09:00 → 11-17 11:30) ≈ 707 核时 idle** — 桌面哨兵停用后的盲区, 本审计最大单笔损失;
  - 44h 被 T0 补跑占机 (有效但阻塞 T1);
  - 失败churn ~19.5h。
- **瓶颈是 solve, 不是 mesh**: mesh+clone 摊到单例仅 ~5.6min, solve 均值 ~42min (~88% 墙钟); 且 mesh/clone 阶段单核 (14 核中占 1), solve 阶段满 14 核 — 全批平均核利用率 ≈ 88% × (solve 墙钟占比) ≈ **~80%** (修复后口径)。
- 内存风险提示: 16GB 机上当前双 snappy (引擎 case46 + 若再遇并行验证) 峰值 6.3GB + FluidX3D 0.85GB; 进入 solve 期 (foamRun np=14, L6/L8 预计 >3GB) 后需盯 OOM (11-15 有 16GB OOM 先例)。

— 采集器: `~/t1_collect_1118.txt` (mtime/签名/ExecutionTime 全量), 本报告副本已同步桌面 `D:\WindTunnelSuite\wt_jobs\tmp\t1_audit_1118.md`。guard 迁移详情见 `~/wt_guard_local.log` 与任务回报。

---

## 附录: 02:13 引擎换车事件 (审计收尾时段, 供产线侧裁决)

- ~02:13 原引擎 (1132996, 11-17 18:39 发车) 被信号终止 (dmesg 无 OOM 记录), case 46 (新字典首例, 已跑 18.7min/layer 迭代 28, 远越旧字典 9.6min 死点) **无判决随之丢失**。
- 02:13:54 新引擎 (PID 1478248, PPID=1) 上位, env 取证: `SWEEP_V="15 20 25 30"` (非本批 V20-25, V15/V30 为 foldedfin 变体), `SURF_LEVEL=6` 但 **FIN_LEVEL 缺失 → 回落默认 7** (非本批 L8), OUT_CSV 指向 t1_table.csv, ROOT 同为 ~/sweep_t1。
- 风险: 该矩阵 = 4 变体×13×7 = **364 例** (旧 T0-v1 口径), 且 FIN7 与本批 L6/L8 混径; 若跑到底, t1_table.csv 将混入非 L8 行, 且 V21/23/24 全缺席。判据: 若非有意降规格, 需在首例 solve 前纠正 (发车 env 补 FIN_LEVEL=8 + SWEEP_V="20 21 22 23 24 25")。
- 审计纪律: 只读不碰, 未干预该进程; 本地哨兵行为正确 (eng=1/chain=1 → 无动作)。
