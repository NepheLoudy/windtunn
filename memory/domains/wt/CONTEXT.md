<!-- updated: 2026-11-03T20:16:11+0800 (dt) -->

# wt 域工作态快照 — 风洞套件工程域

## 现状（2026-11-03）
- 双仿真线健康：镖体 T0 蓝表 142/364（qianli CPU，2.05 工况/h，ETA 11/5 深夜-11/6 凌晨）+ LBM T2 收官 201 例零错误，T3 队列已发车（长时序/对拍/β 细扫描）。
- T2 四级收敛 Nx² 翻案定案：fx/Nx² ±2%，量级标尺成立；长时序首例证明 α=12.5° 是确定性定常吸引子（1.2M 步零分支切换）。
- 观察台（wt_jobs/www/dashboard.html）：3D 只渲染镖体 + 静态来流箭头 + 相机自转；**风洞流场在 web 端整段缺席**。

## 已验证结论
- 流场数据只在 MATLAB 端（FluidX3D vtk/raw，explore_gpu.m 消费）与 qianli solver 主机；无任何 VTK→web 转换器；httpd.py 只有静态文件 + /api/mass_props。
- 风洞本体几何仅 MATLAB（tunnel_body.stl / build_tunnel_model.m），web 端没有。
- Nx² 晶格标度律（p=−2.001）：跨分辨率比 LBM 力必须先归一化。

## 待办
- 观察台"动态立体受风工况"渲染方案（2026-11-03 曼波提出）——见 docs/project_review_1103.md §七。
- t2_report.py 升级吃 t2_queue_summary.csv；T0 出全 → 合并 master 工具。
