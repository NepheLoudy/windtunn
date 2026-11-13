<!-- updated: 2026-11-08T22:23:40+0800 (dt) -->

# wt 域工作态快照 — 风洞套件工程域

## 现状（2026-11-08）
- **T0 扩格批：370/546（V20-25 目标网格 269 done，ETA ~11-13 深夜-11-14）**。11-08 手术后引擎健康：新 runner OUT_CSV=t0_table（environ 实证）、SWEEP_V=20-25、chain/reaper/harvest 三防在岗。表落地链已修复。
- T2 GPU 229 例收官、T3 队列完成（对拍 <2% 已入档）。
- 观察台流线管线**终版语义**（11-06 曼波裁定落地）：
  - 数据源 = qianli 收割 daemon（引擎出活瞬间 reconstructPar -latestTime → foamToVTK → sl_v3 积分 → json），rsync 增量拉到 wt_jobs/www/poses/（现 43 个真收敛场）。
  - pickPose = **最近可用收敛姿态 + readout 徽标明示姿态差**（>1.26° 显示 "姿态差 x°"，不冒充精确）；精确命中时徽标 "真实 CFD 场 case_xxx"。
  - 渲染 = Tube（CatmullRom→TubeGeometry）顶点色 aeroJet **单线渐变**（perRing=6 环序采样，11-06 根治旧除数错的全线单色假象）；体内点径向投影连续贴体层；密度 MAXL=400 抽稀；surf 饱和率门控（>80% 纯红=坏代自动弃用，等 sl_v3 jet 修复后新收割代恢复）。
- 均匀场数据已判死：11-05 03:xx b11 批 51 文件（整 V20 系+V21_a-15_b-10）是 t=0 初始场积分（没 reconstructPar），双端归档（本地 poses_archive/uniform_b11_residual/ + qianli ~/sweep_t0v2/streamlines_uniform_archive/）。
- **静稳定性实测翻案+五雷全修（11-06 晚，曼波"都修"）**：T0 快照 202 行回归 → Cm_α=+0.360/rad、Cn_β=−0.434/rad **双轴强静不稳**（推翻 11-01 体检 −0.103 小样本估计与折叠舵锚定 +0.0026）；dev_spec/delivery/fidelity 三文档修订 rg 零残留；post_process.py S_REF/L_REF 静默兜底（1.71x 事故残留）→ 缺键 RuntimeError 守卫，qianli 489 case 缺键=0 热同步完成；表合成语义判定定稿（联合位形总系数，查表即真值）。
- **观察台 3D 渲染抢救（11-06 晚，曼波"很烂看看怎么抢救"）**：33 条体检（3🔴+9🟠+20🟡）→ P0 六修 + P1 四修 + 顺手三修；harness 35 pass+浏览器实测全绿。**ssh_cat base64 化**（wsl.exe GBK 编码桥中文必乱）。**P2 拆分已落地（11-08 工位交付待回归）**：dashboard.html 1242→597 行 + wt3d_core/flow/readout 三文件 + Tube 合并几何（draw call 400→2）+ 触摸/惯性/ResizeObserver + 版本锁定 + 追加 4 项修复（mesh 重试清理/流线自动补/paintSurfaceSpeed 改名/恢复时序抢跑根治）。
- **表落地链断裂+手术（11-08，曼波"验收仿真进度"揭出）**：11-05 01:41 内联启动缺 OUT_CSV → 168 行 V21-24 + 44 行旧网格重跑落错表（aero_table.csv 默认路径）；runner 判重集启动时冻结 → 必然再浪费 158 例重跑。手术：杀 chain→杀 runner→清残骸→recover_table 回填 168 行（顺修其 positional case 潜伏雷）→全 env 重启（environ 实证 OUT_CSV=t0_table）。**隔离裁决：搁浅表 44 例重跑批系统性异常（CD 中位比 1.82+Cm 反号+GAMG 崩溃栈，口径/几何 v4 双排除，剩余嫌疑 ET=1500 硬编码漂移）→ audit-only 不进主表，13 例 V25 真新工况同批隔离（新 runner 自动正规重跑）**。qianli run_sweep_v2.sh 与本地漂移（行号+ET=1500 硬编码 vs 600/1000/1500 分档）——运行中不可改，T0 出全后同步 canonical。

## 已验证结论
- **验收铁律**：交付前必须浏览器实测（本环节曾三连翻车：语法炸/数据混/徽标误报）；IAB 后台 document.hidden 冻结 rAF，用页面调试口 __renderOnce 单帧截图验收。
- **数据质检方法**：近体环带 (r<0.10) 速度谱——真收敛场 min<15 有减速层、max>27 有加速；均匀场残骸全谱 v≈V 零梯度。hasLayer 已改全线扫描+加载缓存（旧版只扫中间线假阴性）。
- V 域 [20,25] 跨 V <1%（流线显示层 V 钝感）；aeroJet 四段非线性色标 v<10 深青→29 橙红。
- **静稳导数实测（11-08 370 行复核+异源交叉复核，取代 11-06 口径）**：CL_α=+2.408/rad（R²=0.998）、**Cm_α 分段 +0.60/rad（|α|≤5° 线性区 R²=0.996）→+0.21/rad（5~10°，α≈−5° 有 3× 拐折；RL 小扰动线性化用 0.60，单值 +0.35 是混合平均）**、Cn_β=−0.434/rad（R²=0.993）、CY_β=−2.311/rad；镜像判据全过；β=±15 失速回落。**斜率锚只覆盖负 α 半侧**（正 α 侧随扫气补齐复核）。全部相对占位 com(0,0,0)，实机称重后 recompute_cm 零重跑刷新。
- **表合成语义（11-06 定稿）**：aero_table 存 (V,α,β,δ) 联合位形总系数——姿态项与舵效项的合成发生在 CFD 全场求解，查表插值即闭环真值（spec「Cmδ 由表差分」铁证）；"下一瞬间"由 MuJoCo 积分；动导数不在表内（damp 外挂待标定，准定常 k≈0.06 成立）。
- **域事件 ID 续号铁律（11-10 撞号事故）**：**续号前必须先 tail events.jsonl 看最大号**——曼波多会话并行同机写作时，本会话上次最大号≠当前最大号（048 已被昨日并行会话占用，本会话盲续撞号，已改号 049 修复）。
- Nx² 晶格标度律（p=−2.001）不变；长时序 α12.5° 定常吸引子定案。
- MSYS 调 wsl/scp/robocopy 必须 MSYS2_ARG_CONV_EXCL='*'；多层引经 wsl.exe 传 ssh 命令易碎——复杂远程操作一律落脚本 scp 上去跑。

## 待办
- **V20 层重跑裁决（待曼波）**：V20 收敛场随旧批 processor 清理丢失，重收割需重跑 91 例（引擎 ETA 拉长）；V21_a-15_b-10 同失。
- V20_a-2.5_b0 收割后消失存疑（磁盘 230G 充裕，非配额；daemon done 表已标，暂弃）。
- 收割覆盖随引擎扩展（现 α -15~-2.5，滑块高 α 姿态走姿态差徽标）。
- ③ Cp 压力 LUT（foamToVTK 加导 p 场，表面色对齐压力语义）+ ② 生成端 rake/RK4/SDF（牛图残余项）。
- A 方案舵效层：δ 分档 audit 插队件（T0 出全前写好），曼波"非向心力矩"需求等 δ 数据。
- **舵效层2/3 未跑**（delivery L66 口径）——层2 单舵 ±10/±20°×4舵、层3 耦合校验到位前 RL 只能飞"舵全零"。
- rho=1.225 静默兜底两处低危待裁决（post_process L113 / recompute_cm L68，同款守卫化可选）。
- MuJoCo 力注入约定待两边对齐会冻结（mujoco_alignment_questions.md §2）；recompute_cm 等实机称重。
- **观察台 P2 拆分在跑（11-08 重启）**：上轮会话工位跨天未交付（wt3d_*.js 磁盘无），已重派 dev-worker（三文件拆分 core/flow/readout + Tube 合并 400→10 draw call + 触摸/惯性 + 版本锁定 + 追加 5 项修复：mesh 重试链清理/流线自动补/paintPressure 改名/ResizeObserver 根治恢复时序 resize 抢跑）。**落地后必须主会话浏览器全量回归**（状态持久化/多角度导帧/流线粒子分层/箭头可见性）。
- **仪表台=随用随开改制（曼波 11-07 定，非故障）**：WT_dashboard 任务经 `j2_task_disabled.flag` 闸门有意禁用，入口=`j2_open.bat`（幂等：8123 未监听→隐藏拉起 httpd `--idle-exit 30`→开浏览器），页面关闭 30min 后服务自清。11-08 我手工拉起的无参长驻实例是异类（闲置退出机制没装），04:41 被外部终止属预期生命周期。
- 阶段一审查发现（11-08 verifier，已折进 P2）：mesh 重试链 initAeroFX 重跑不清理旧对象[中危·预存]/流线"自动补"无实现[低危]/paintPressure 命名残留[低危]/pagehide+beforeunload 双钩冗余[信息·无害]。
