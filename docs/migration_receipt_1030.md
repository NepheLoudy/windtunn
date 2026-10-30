# NAS 迁移回执 — 风洞/制导闭环项目存量数据

> 回执编号: MIG-20261030-001 | 完成时刻: 2026-10-30 08:21 (验证) / 清本机 08:23
> 传输: rsync over ssh (192.168.31.153:2222, key 免密) | vault: `/mnt/nas_data/公用/windtunnel-vault/`
> 验证语义: 文件数 + 字节总数 双端整数比对 (NAS 侧 20T LVM, 数据校验由 ext4 承担)

## 1. 逐项回执 (7/7 PASS)

| # | vault 相对路径 | 源路径 (本机) | 文件数 | 字节 | 判定 |
|---|---|---:|---:|---:|---|
| 1 | runs/windtunnel3d-vtk | WindTunnel3D/fluidx3d/vtk | 73 | 74,877,027,250 | ✅ PASS |
| 2 | archive/windtunnel3d-vtk_prev | WindTunnel3D/fluidx3d/vtk_prev | 98 | 4,632,250,935 | ✅ PASS |
| 3 | archive/windtunnel3d-vtk_oldmix | WindTunnel3D/fluidx3d/vtk_oldmix | 24 | 2,382,870,619 | ✅ PASS |
| 4 | archive/fansim3d-vtk_prev | FanSim3D/fluidx3d/vtk_prev | 74 | 15,957,590,266 | ✅ PASS |
| 5 | archive/fansim3d-vtk_smoke | FanSim3D/fluidx3d/vtk_smoke | 18 | 639,960,474 | ✅ PASS |
| 6 | archive/renders-of | renders/of | 87 | 10,495,279,526 | ✅ PASS |
| 7 | archive/flow3d_result.mat | WindTunnel3D/flow3d_result.mat | 1 | 305,571,468 | ✅ PASS |
| | **合计** | | **375** | **102,430,845,032 (95.4 GiB)** | **7/7** |

## 2. 本机清理回执 (热交换授权条款: 验证通过免授权自动清)

| 源 | 释放 |
|---|---:|
| WindTunnel3D/fluidx3d/vtk | 71,409 MB |
| WindTunnel3D/fluidx3d/vtk_prev | 4,418 MB |
| WindTunnel3D/fluidx3d/vtk_oldmix | 2,273 MB |
| FanSim3D/fluidx3d/vtk_prev | 15,219 MB |
| FanSim3D/fluidx3d/vtk_smoke | 611 MB |
| renders/of | 10,010 MB |
| WindTunnel3D/flow3d_result.mat | 292 MB |
| **合计释放** | **≈ 104.2 GB** |

- D: 盘现状: 305G 可用 (迁移前 161G)
- C: 盘另于同日早间由 WSL 迁移手术回血 168G (37G → 205G)
- 另删: vtk_old_inline 43G (P0 前损坏快照, 曼波点头) / 迷路 tar 8.3G / sweep_full_blue 716M

## 3. 过程瑕疵记录 (如实)

| 瑕疵 | 处置 |
|---|---|
| v1 验证器 awk 科学计数法误报 5 项 MISMATCH | v2 验证器 printf %.0f 整数比对 → 实际全部 PASS |
| v1 对单文件项误加尾斜杠 → NAS 端生成同名目录桩 (4096B) | 桩删除 + 文件重传 PASS |
| `.migrated_to_nas` 标记污染源目录计数 (+1 文件) | 验证器排除标记文件; 标记保留做幂等 |
| 收尾清理脚本按设计 ABORT (v1 日志存在 MISMATCH) | v2 回执全 PASS 后按热交换条款手工执行清理 |

**结论: 数据已完整驻留 NAS vault, 本机原件已按验证回执清除。此后快照转储走热交换流水线
(auto_snapshot_sync / nas_push), 交换只发生在算力平台 (qianli) 与 NAS 之间。**
