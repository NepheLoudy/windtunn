# 任务包架构协议（sweep_packs）

> 2026-11-19 定稿。四机协同的正式运转协议；取代 compute_node_protocol.md §2/§3 的两机 run_sweep 口径（那份已标历史方案）。

## 1. 概念

- **包（pack）**：一组 (α,β) 姿态 × V 域的工况集合，定义在 `openfoam/airframe-sweep/sweep_packs/packs/PNN.json`。17 包 / 85 组 / 935 例覆盖域 V=[10..20]、α=±30（失速带 2.5° 加密）、β=±5。
- **分片（shard）**：一台机器领走的包子集，`PNNsK.json`，带 `"parent":"PNN"` 字段。分片 groups 并集 = 父包 groups，零重零漏。当前活跃：P01 → P01s1(qianli)/P01s2(NUC1)/P01s3(NUC2)/P01s4(desktop)，合计 55 例。
- **组（group）**：一个 (α,β) 组合下全 V 扫描，网格复用 + 热启动链只在组内有效——分片必须保持组完整性，不许把同一组拆到两台机器。

## 2. 发车（一台机器认领一个分片）

```bash
cd <repo>/openfoam/airframe-sweep/sweep_packs
bash run_pack.sh <PACK_ID> [WORK_ROOT]   # 默认 WORK_ROOT=$HOME/sweep_pack_work
```

run_pack 内置三道自检（不过不发车）：
1. env 三件套：blockMesh/snappyHexMesh/foamRun 在 PATH（显式 source OpenFOAM bashrc）
2. 包定义 JSON 存在且可解析（逐项 python -c 取参——shell 层无 eval，argv 直传，python 侧对键路径求值）
3. 几何真源 `cad/v1/cfd_geom_multi_parallel/`（30 STL，已入 git）

托管方式（按机器）：
- NUC（Windows）：schtasks `WSL_<PACK>` onstart + 立即触发，bat 链式（P01s3→P06）
- desktop WSL：`setsid nohup`，`.wslconfig` 的 `vmIdleTimeout` 必须停用（60s 空闲关机会杀几十小时的 CFD）
- qianli（原生 Linux）：`setsid nohup`

## 3. 断点续跑与判重（三层防线）

1. **case 级**：`results.json` 存在 → 跳过（run_sweep_v2.sh）
2. **表级**：OUT_CSV 已有键 → 跳过（DONE_SET，键归一 printf %g——β=±2.5 曾因 `${B%.*}` 截断失配，已修）
3. **合并级**：merge_master.py 六键判重（V,α,β,de,da,dr），重复键默认**拒合（rc=4）**，确认要合才 `--allow-dups`

重启机器后重跑同分片 = 自动跳过已完成例，只补缺失例。**不要 rm 分片目录除非确认表已收走。**

## 4. 收表与验证

```bash
# 各机表汇到 wt_jobs/collect/P01sN_table.csv 后:
bash sweep_packs/collect.sh <OUT_CSV> <WORK_ROOT...>   # source=包ID, 调 merge_master
py -3 openfoam/airframe-sweep/verify_tables.py <tables...> \
    --legacy guidance_sim/aero/aero_table.csv --shards sweep_packs/packs
```

verify_tables 六道关：表头 meta 一致 → 表内键唯一 → 跨机键零重叠 → 行归属分片 → 物理合理性（CD∈(0,2)、|CL|<3、NaN）→ 与老表对拍（CL/CD 相对差>15% 告警）。

状态语义（run_pack 写 status.json）：`done`=rows≥cases 且零组失败；`partial`=有产出或有组失败（**禁直接消费**——含"全部组失败"的情形，组失败有失败计数不归 failed）；`failed`=0 行且零组失败（未跑起来就退）。board.sh 分片接管父包计数，合计 935 不含父包双计。

## 5. 看板与值班

- `board.sh`：包状态总览（本机）
- `fleet_monitor.sh`（30 分钟 schtasks FleetMonitor）：四机扫描 → `wt_jobs/fleet_status.log`，异常标 `>>>FAIL/>>>MESHFAIL/>>>SIGFPE/>>>ZERO`
- `morning_report.sh`（每日 04:00 schtasks MorningReport）：`wt_jobs/MORNING_REPORT_<date>.md` = 四机状态+拉表+跨机验证+收工建议
- ZCode 值班巡检：每小时 Cron 唤醒，55 例齐→自动 collect+verify+写 P01_FINAL_汇报→自动停

## 6. 新机器接入

按 `docs/new_node_onboarding.md` 全流程；几何真源已入 git（30 STL），clone 即得。领包前跑 `bash sweep_packs/board.sh` 看哪个包/分片 pending，避免双领（run_pack 不做锁，双领只会浪费机时——merge 判重兜底正确性）。

## 7. 看门狗防线（2026-11-20 新增）

**WSL VM 崩溃 ≠ Windows 重启**：onstart 触发器覆盖不到 VM 级崩溃（实测 4 次：NUC2×2/NUC1×1/desktop×1，产线最长静默 12h）。

- `WSL_watchdog`（schtasks 每 10 分钟）：查 WSL 内 pack_queue 进程，缺失即拉起 `pack_queue.sh <原参数>`——幂等，判重保证不重算
- desktop: `WSL_queue_desktop`（onstart）+ 手动触发
- 看门狗脚本 `wsl_watchdog.sh` 在各机 D:\，参数 = 队列参数原串

## 8. 已知约束（2026-11-19）

- NP=5 为全机统一配置；NUC1/qianli 有算力富余（利用率 31%/25%），下一批包按机器配 NP
- endTime 按 **FIN_LEVEL≥8** 抬到 3000 步（residualControl 1e-5 判停；11-19 从 SURF≥6 收窄——曾把 FIN=7 的 T0.5 档误伤进 3000 步口径，每例 190min vs 38min）；组内后续 V 热启动大幅缩短
- qianli 缺 `merge_master.py`（10-26 老仓库）——它不承担合并，无风险；四机脚本 md5 对拍已 12/12 一致
