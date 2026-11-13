# -*- coding: utf-8 -*-
"""F4 强迫振荡动导数提取器 (qianli 5070 六例) — 归一到 spec §4.5.1 damp dict 口径。

输入: forces_osc_{p,y,r}_{f1,f2}_v4asm.csv ( FluidX3D src/setup.cpp v4asm forced-oscillation
probe, 11-10 真实装配几何重扫: GEOM=cfd_v4parts, read_stl_assembly 按装配空间逐件体素化,
不再 recenter/rescale — 团块 bug 修复后的数据; 每 100 步采样一行: t,fx,fy,fz,tx,ty,tz;
t 单位 LBM step, 力矩单位 LBM lu^5/step^2, rho_lu=1 )。
输出: damp_defaults.json ( Clp/Cmq/Cnr 主值 + 两频率原始值/SNR/置信标注 + 口径备注 ),
供 lookup_aero.aero_forces(damp=None) 热加载。
交叉验证: wt_jobs/tmp/f4_v4asm_lockin.json 主线锁相读数 (osc_batch.sh 内联 lockin.py,
幅度口径 amp_zoh_adj 应与本脚本逐位一致, __main__ 尾部自动对拍)。

=========================== 单位制换算推导 ( src/setup.cpp v4asm, qianli 远端
md5=0d715ffc 定版 11-10 00:59:54, 六例扫描 11-10 08:05~18:35 均在其后 ) ===========================

LBM 侧锚点 (行号指 src/setup.cpp v4asm):
  L81-82 V_lbm = getenv V_LBM ?: 0.05f -- 来流速率 [lu/step] (osc_batch.sh 未传 V_LBM -> 默认 0.05)
  L94   cpm = Nx/0.2386f         -- cells per meter, Nx=440, 弹长 0.2386 m
                                    -> lu_per_m = 440/0.2386 = 1844.0
  L127  lbm.rho[n] = 1.0f        -- 格子密度无量纲 (LBM 常规), 即 rho_lu = 1.0
  L140  SAMPLE = OSC_AXIS?100:500 -- 力采样块长 [step] (OSC 时 100)
  L146-172 OSC 入口刷新时序       -- 见下 ZOH 推导 (机制与旧版 v3 一致: L155 ph =
                                     OSC_OMEGA*(t+SAMPLE) 刷下一块, L172 CSV 时间戳 = t+SAMPLE)

物换算系数 (FluidX3D 标准 lu/step/ρ=1 -> SI):
  lu_m  = 1/lu_per_m [m]           dt = V_lbm*lu_m/V_phys [s]
  F_phys = F_lu * rho_phys * lu_m^4 / dt^2     M_phys = M_lu * rho_phys * lu_m^5 / dt^2
  omega_phys = omega_lu/dt         V_phys = V_lbm*lu_m/dt

动导数无量纲性 => LBM 单位内归一 = 物理单位归一 (严格等价, 代入上面换算后
lu_m/dt/rho_phys 全部相消, 推导见本文件自测第 2 项数值对拍):
  Cmq = M_ac / ( qbar_lu * S_lu * L_lu * (theta_dot_amp * L_lu/(2*V_lbm)) )
  qbar_lu = 0.5*rho_lu*V_lbm^2
  S_lu = S_REF[m^2]*lu_per_m^2,  L_lu = L_REF[m]*lu_per_m
S_REF/L_REF 取 aero_table.csv 头 (与 lookup_aero 力矩归一同基准) -> 提取值直接进
lookup_aero 的 damp dict, 口径闭合。本脚本从不开壁炉拍脑袋: 所有换算常数的源头
就是上面四行 setup.cpp。

=========================== ZOH (零阶保持) 完整校正 ===========================

setup.cpp L146-172 时序: 块 [t, t+SAMPLE) 的入口速度 = sin(ω*(t))  (上一轮迭代末
在时间戳 t 处刷的, L155 ph = OSC_OMEGA*(t+SAMPLE) 刷的是下一块), CSV 行时间戳 = t+SAMPLE
= 下一块的块首 -> 驱动信号是「块首采样 ZOH」, 基波传递 = sinc(ωT/2) * exp(-iωT/2):
  幅度衰减 K = sin(ωT/2)/(ωT/2)   (f1: 0.9355, f2: 0.9959)
  相位延迟 φ = ωT/2               (f1: 36.0°, f2: 9.0°)

wt_jobs/tmp/osc_f4/lockin.py 只除了 sinc (幅度), 相位没转 -- 对总幅度无影响, 但对
As(静刚度)/Ac(阻尼)分解是致命的: f1 时 φ=36°, 静刚度分量会以 sin(36°)=0.59 的系数
泄漏进 Ac, 符号都可能翻转。本脚本做完整逆变换:
  As = ( As_m*cosφ - Ac_m*sinφ ) / K
  Ac = ( As_m*sinφ + Ac_m*cosφ ) / K
As = 与姿态角同相分量 (准定常静刚度, Cmα·Δα), Ac = 与角速度同相分量 (阻尼, Cmq·θ̇)。

=========================== 物理判读 (11-09 审查定口径; 11-11 v4asm 重扫判读更新) ===========================

1. 俯仰激励 (p 批): ty 主响应 (v4asm amp 137.8/96.4 = 团块版 57.9/27.5 的 2.4~3.5 倍,
   真实弹体信号质量飞跃); Ac/θ̇ -> Cmq, As/Δα -> Cmα_dyn (对照静表 +0.60/rad 交叉校验)。
2. 偏航激励 (y 批): tx 巨响应 (306~411, SNR 120~155) = X 构型滚转-偏航手性耦合动态面
   (与 11-03 T2 fy sign(α)sign(β) 同源, α=5° 固定下 β 摆动激发; 团块版亦见, 物理稳健)
   -- 提取 Cnr 只用 tz 主通道 (y_f1 的 ty SNR 1.15 太弱不可用, 与上轮判读一致)。
3. 滚转激励 (r 批): 注入 = 来流矢量绕 x 旋转 (准定常等效口径, 非镖体真实滚转)。
   tx 响应可用 (amp 35.9/27.0, SNR 22/14), 但该值 ≠ 标准风洞滚转速降 Clp, 仅作同频
   等效阻尼估计 (交付声明必带)。
4. 俯仰激励 tx/tz 也动了 = X 构型强耦合, 提取一律主通道优先。
5. 符号: 旋转阻尼物理先验为负 (弹体能量流向流体); 入口->镖体对流延迟 (~4400 step)
   使 As/Ac 正交分解的相位不可标定 (psi_f1 mod 2pi ~288°, psi_f2 ~72°, 见
   extract_derivatives docstring), 故符号不取自 Ac 分解而取物理先验, 幅度口径交付。

依赖: numpy + 标准库。py -3 extract_damp.py [--no-fetch] 运行。
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

# ---------------- setup.cpp 锚定常数 (行号见 docstring) ----------------
V_LBM = 0.05                  # L41 (+ osc_batch.sh 未传 V_LBM)
NX = 440                      # osc_batch.sh NX=440
DART_LEN_M = 0.2386           # L53
LU_PER_M = NX / DART_LEN_M    # L53 cpm = 1844.0
RHO_LU = 1.0                  # L80
SAMPLE = 100                  # L93
AMP_DEG = 2.0                 # osc_batch.sh OSC_AMP=2.0
T_SKIP = 200000.0             # osc_batch.sh lock-in 窗口 (跳初始瞬态)
STEPS = 1200000               # osc_batch.sh STEPS
SSH_TARGET = "qianli@100.90.63.31"
# v4asm 重扫文件名 (osc_batch.sh: TAG="_osc_{axis}_{freq}_v4asm" -> out/forces${TAG}.csv);
# 团块版旧 CSV (forces_osc_*.csv, 无后缀) 留在同 cache 目录作隔离对照, 不覆盖
SSH_PATH = "~/fluidx3d_v3/FluidX3D-master/bin/out/forces_osc_%s_v4asm.csv"
CACHE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "..", "..", "wt_jobs", "tmp", "osc_f4", "cache"))

# 静表交叉校验参考值 (spec §4.5.1: 11-08 T0 蓝表 370 行实测)
CM_ALPHA_TABLE = 0.60         # /rad, 线性区
CN_BETA_TABLE = -0.43         # /rad

# 六例定义 (osc_batch.sh L18-23; omega 单位 rad/step)
CH_NAMES = ("fx", "fy", "fz", "tx", "ty", "tz")
CASES = [
    ("p_f1", "pitch", 0.012566, "ty"),   # 俯仰(攻角摆)   500 steps/周期
    ("p_f2", "pitch", 0.0031416, "ty"),  #               2000 steps/周期
    ("y_f1", "yaw", 0.012566, "tz"),     # 偏航(侧滑摆)   主通道 tz (Cnr); tx 是手性耦合面
    ("y_f2", "yaw", 0.0031416, "tz"),
    ("r_f1", "roll", 0.012566, "tx"),    # 滚转(来流绕x旋) 准定常等效口径, 见口径备注
    ("r_f2", "roll", 0.0031416, "tx"),
]
AXIS_CH = {"pitch": ("ty", "Cmq", "Cm_alpha_dyn", CM_ALPHA_TABLE),
           "yaw": ("tz", "Cnr", "Cn_beta_dyn", CN_BETA_TABLE),
           "roll": ("tx", "Clp", "Cl_beta_eff_dyn", None)}


# ---------------- 数据获取: 本地缓存优先, 否则 wsl ssh cat ----------------

def fetch_csv(tag, cache_dir=CACHE_DIR, no_fetch=False):
    """返回 forces CSV 本地路径。缓存命中直接用; 否则经 wsl ssh 从 qianli 拉取。

    注: MSYS2_ARG_CONV_EXCL='*' 只是 Git Bash 手敲 wsl.exe 时的路径转义防线;
    本函数 subprocess 用 list 参数不经 shell, 无 MSYS2 路径转换问题。
    """
    fname = "forces_osc_%s_v4asm.csv" % tag
    local = os.path.join(cache_dir, fname)
    if os.path.exists(local) and os.path.getsize(local) > 1000:
        return local
    if no_fetch:
        raise FileNotFoundError("缓存缺失且 --no-fetch: %s" % local)
    os.makedirs(cache_dir, exist_ok=True)
    cmd = ["wsl.exe", "-u", "root", "-e", "ssh", SSH_TARGET, "cat " + SSH_PATH % tag]
    res = subprocess.run(cmd, capture_output=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError("ssh 拉取失败 %s: %s" % (tag, res.stderr.decode("utf-8", "replace")))
    text = res.stdout.decode("ascii")
    if len(text.splitlines()) < 1000:
        raise RuntimeError("ssh 返回行数异常 (%s): %d 行" % (tag, len(text.splitlines())))
    with open(local, "w", encoding="ascii") as f:
        f.write(text)
    print("fetched %s -> %s (%d lines)" % (tag, local, len(text.splitlines())))
    return local


def read_forces(path, t_skip=T_SKIP):
    """读 CSV -> (t[N], data[6,N]), 过滤 t > t_skip。"""
    arr = np.loadtxt(path, delimiter=",", skiprows=1)
    arr = arr[arr[:, 0] > t_skip]
    return arr[:, 0], arr[:, 1:].T


# ---------------- 锁相回归 + ZOH 完整校正 ----------------

def lockin(t, y, omega):
    """y(t) ~ DC + As*sin(ωt) + Ac*cos(ωt) 最小二乘 (3 参数法方程, lockin.py 同基)。

    返回 dict: dc/As/Ac/amp/phase_deg/res_rms/snr (snr = amp/res_rms, 同 lockin.py 口径)。
    """
    s, c = np.sin(omega * t), np.cos(omega * t)
    A = np.stack([np.ones_like(t), s, c], 1)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    dc, As, Ac = coef
    resid = y - A @ coef
    rrms = float(np.sqrt(np.mean(resid ** 2)))
    amp = float(math.hypot(As, Ac))
    return {"dc": float(dc), "As_raw": float(As), "Ac_raw": float(Ac), "amp_raw": amp,
            "phase_deg": float(math.degrees(math.atan2(Ac, As))),
            "res_rms": rrms, "snr": amp / rrms if rrms > 0 else float("inf")}


def zoh_undistort(lk, omega, sample=SAMPLE):
    """ZOH 逆变换: 除 K=sinc(ωT/2) + 反旋转 φ=ωT/2 (推导见 docstring)。

    就地写入 As/Ac (校正后) 与 amp_zoh_adj (校正后幅度, = 任务卡口径, 可与
    11-09 六例锁相读数表直接对拍)。
    """
    x = omega * sample / 2.0
    K = math.sin(x) / x if x > 0 else 1.0
    phi = x
    As_m, Ac_m = lk["As_raw"], lk["Ac_raw"]
    lk["As"] = (As_m * math.cos(phi) - Ac_m * math.sin(phi)) / K
    lk["Ac"] = (As_m * math.sin(phi) + Ac_m * math.cos(phi)) / K
    lk["amp_zoh_adj"] = math.hypot(lk["As"], lk["Ac"])   # == amp_raw/K (旋转保范数)
    lk["zoh_K"], lk["zoh_phi_deg"] = K, math.degrees(phi)
    return lk


# ---------------- 归一化 (LBM 无量纲口径, 与 lookup_aero damp 同构) ----------------

def norm_consts():
    """从 aero_table.csv 头读 S_REF/L_REF (直接读 CSV 头, 避免循环 import)。"""
    tbl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aero_table.csv")
    meta = {}
    with open(tbl, encoding="utf-8-sig") as f:
        for line in f:
            if not line.startswith("#"):
                break
            for tok in line.lstrip("#").split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    meta[k] = v
    S_REF, L_REF = float(meta["S_REF"]), float(meta["L_REF"])
    S_lu, L_lu = S_REF * LU_PER_M ** 2, L_REF * LU_PER_M
    qbar = 0.5 * RHO_LU * V_LBM ** 2
    return {"S_REF": S_REF, "L_REF": L_REF, "S_lu": S_lu, "L_lu": L_lu,
            "qbar_lu": qbar, "qSL": qbar * S_lu * L_lu,
            "qSL2V_w": qbar * S_lu * L_lu * L_lu / (2.0 * V_LBM)}  # qSL2V_w: 每 (rad/step) 的力矩系数


def extract_derivatives(detail, nc):
    """从单例锁相结果提取动导数 (主通道优先, 物理判读 1-4)。

    主口径 (任务卡 11-09 审查定, amp 口径):
        C_eq = -amp_zoh_adj / (qSL2V_w * theta_dot_amp),  theta_dot_amp = AMP_rad*omega
      负号 = 旋转阻尼物理先验 (能量从弹体流向流体)。幅度口径不受传播相位影响 (见下)。
      该值为**同频等效阻尼** (响应幅度含静刚度贡献 + 高频衰减, |C_eq| >= |准定常 Cmq|)。

    为何不用 Ac/θ̇ (标准正交分解口径): 入口面激励 -> 镖体存在对流传播延迟
        tau_conv ~ d/V_lbm ~ 219 lu / 0.05 lu/step ~ 4380 step
        psi = omega*tau_conv: f1 mod 2pi ~ 271°, f2 ~ 68°
    未知相位 psi 把静刚度泄漏进 Ac (泄漏 ~ As*sin(psi), |As|>>|Ac|), Ac 符号不可判定
    (六例实测: p 批 Ac 两频率异号 +44/-16.7, Cmα/Cnβ 双锚不一致 -- 与 psi 混杂一致)。
    幅度 |amp| 对 psi 旋转不变 -> 唯一稳健观测量。As/Ac 分解保留在 diagnostic 键。

    diagnostic (As/Ac 口径, 传播相位污染, 仅作参考):
        *_ac_quadrature = Ac/(qSL2V_w*theta_dot_amp)  -- 相位污染的阻尼分量
        *_as_static     = As/(qSL*AMP_rad)            -- 相位污染的等效静刚度
    """
    tag, axis, omega, main_ch = detail["tag"], detail["axis"], detail["omega"], detail["main_ch"]
    ch, dkey, skey, table_ref = AXIS_CH[axis]
    assert ch == main_ch
    amp_rad = math.radians(AMP_DEG)
    theta_dot_amp = amp_rad * omega
    lk = detail["channels"][ch]
    out = {
        "theta_dot_amp_rad_per_step": theta_dot_amp,
        dkey: -lk["amp_zoh_adj"] / nc["qSL2V_w"] / theta_dot_amp,
        dkey + "_ac_quadrature": lk["Ac"] / nc["qSL2V_w"] / theta_dot_amp,
        skey: lk["amp_zoh_adj"] / nc["qSL"] / amp_rad,   # 幅度口径等效静刚度 (衰减因子用)
        skey + "_as_component": lk["As"] / nc["qSL"] / amp_rad,
    }
    if table_ref is not None:
        out[skey + "_table_ref"] = table_ref
        out[skey + "_atten_vs_table"] = out[skey] / table_ref
    return out


def response_diagnostics(results):
    """跨例响应诊断: 传播相位混杂证据 + 高缩减频率衰减 (写进 JSON 供审查)。"""
    cm = [(r["tag"], r["derived"]["Cm_alpha_dyn"], r["derived"]["Cm_alpha_dyn_as_component"])
          for r in results if r["axis"] == "pitch"]
    cn = [(r["tag"], r["derived"]["Cn_beta_dyn"], r["derived"]["Cn_beta_dyn_as_component"])
          for r in results if r["axis"] == "yaw"]
    d_conv = NX / 2.0   # 入口 x=Nx-1 到镖体~中心的估计距离 [lu]
    tau = d_conv / V_LBM
    return {
        "propagation_delay_est_steps": tau,
        "psi_mod2pi_deg": {"f1": math.degrees((0.012566 * tau) % (2 * math.pi)),
                           "f2": math.degrees((0.0031416 * tau) % (2 * math.pi))},
        "reduced_freq_k": {"f1": 0.012566 * (NX / DART_LEN_M) * 0.15 / (2 * V_LBM),
                           "f2": 0.0031416 * (NX / DART_LEN_M) * 0.15 / (2 * V_LBM)},
        "cm_alpha_eq_vs_table": {t: round(v, 4) for t, v, _ in cm},
        "cn_beta_eq_vs_table": {t: round(v, 4) for t, v, _ in cn},
        "note": "入口->镖体对流延迟使 As/Ac 相位分解不可标定 (psi 估计见上, 对流速度"
                "不确定性 -> psi 不确定 ±20°+); 幅度口径不受影响。等效静刚度仅为静表 "
                "6~13% = 缩减频率 k=8.7/34.8 高频区的响应衰减 (非定常流跟不上摆动)。"
                "As/Ac 分解六例呈两频率异号/双锚不一致, 与 psi 混杂预期一致 -> 弃用。",
    }


def conf_tag(vals, snrs):
    """置信标注: 两频率原始值 + SNR 定档。物理先验 (阻尼为负) 由调用方叠加。"""
    same_sign = all(math.copysign(1, v) == math.copysign(1, vals[0]) for v in vals)
    if same_sign and min(snrs) >= 30:
        base = "high"
    elif same_sign and min(snrs) >= 10:
        base = "medium"
    else:
        base = "low"
    if not same_sign:
        base = "low+两频率异号"
    return base


def extrapolate_omega0(v_f1, v_f2, omega_f1=0.012566, omega_f2=0.0031416):
    """两点线性外插 ω→0 (准定常极限, 最接近标准动导数定义口径)。
    ω1=4ω2 -> C0 = (4*C_f2 - C_f1)/3; 外插放大噪声, 主值回落逻辑见 collect()。"""
    return (v_f1 * omega_f2 - v_f2 * omega_f1) / (omega_f2 - omega_f1)


# ---------------- 主流程 ----------------

def run_extraction(no_fetch=False):
    nc = norm_consts()
    results = []
    for tag, axis, omega, main_ch in CASES:
        path = fetch_csv(tag, no_fetch=no_fetch)
        t, data = read_forces(path)
        detail = {"tag": tag, "axis": axis, "omega": omega, "main_ch": main_ch,
                  "n_rows": int(t.size), "t_skip": T_SKIP, "channels": {}}
        for i, name in enumerate(CH_NAMES):
            lk = zoh_undistort(lockin(t, data[i], omega), omega)
            detail["channels"][name] = lk
        detail["derived"] = extract_derivatives(detail, nc)
        results.append(detail)
    return nc, results


def collect(no_fetch=False):
    """六例 -> damp_defaults.json 结构。主值 = f2 低频点直取 (见 caveats)。"""
    nc, results = run_extraction(no_fetch=no_fetch)
    out = {"derivatives": {}, "cases": [], "diagnostics": response_diagnostics(results),
           "meta": norm_meta(nc)}
    for axis, dkey, skey in (("pitch", "Cmq", "Cm_alpha_dyn"),
                             ("yaw", "Cnr", "Cn_beta_dyn"),
                             ("roll", "Clp", "Cl_beta_eff_dyn")):
        rs = [r for r in results if r["axis"] == axis]
        rs.sort(key=lambda r: r["omega"])                       # [f2(低频), f1(高频)]
        v_lo, v_hi = rs[0]["derived"][dkey], rs[1]["derived"][dkey]
        snrs = [r["channels"][AXIS_CH[axis][0]]["snr"] for r in rs]
        v0 = extrapolate_omega0(v_hi, v_lo)                     # (f1, f2) 高频在前; 备查
        conf = conf_tag([v_lo, v_hi], snrs)
        phys = "负号 = 旋转阻尼物理先验 (amp 口径无符号信息, 符号按先验赋负)" if v_lo < 0 else \
               "正号异常 (amp 口径应恒负 -- 代码 bug, 拒绝交付)"
        assert v_lo < 0, "amp 口径符号逻辑错误"
        out["derivatives"][dkey] = {
            "value": v_lo,
            "source": "f2 低频点 (ω=0.00314 rad/step, k≈8.7) 直取; amp/θ̇ 同频等效口径",
            "confidence": conf,
            "f2_low_freq": v_lo, "f1_high_freq": v_hi,
            "omega0_extrap_unref": v0, "snr": {"f2": snrs[0], "f1": snrs[1]},
            "ac_quadrature_diag": {r["tag"]: r["derived"].get(dkey + "_ac_quadrature") for r in rs},
            "equiv_static_amp": {r["tag"]: r["derived"].get(skey) for r in rs},
            "physics_check": phys,
        }
    out["cases"] = results
    out["meta"]["caveats"] = [
        "主口径 = amp_zoh_adj/θ̇_amp (任务卡 11-09 审查定): 入口激励->镖体对流延迟 "
        "(~4400 step, psi_f1 mod 2pi ~288° / psi_f2 ~72°, 不确定 ±20°+) 使 As/Ac 正交分解"
        "不可标定 (六例 Ac 两频率异号、Cmα/Cnβ 双锚不一致与 psi 混杂一致), 幅度对 psi 不变",
        "符号 = 旋转阻尼物理先验 (负); amp 口径无符号信息, Ac 分解符号不可判定 (同上)",
        "该值为**同频等效阻尼** (响应含静刚度贡献 + 高频衰减): k≈8.7(f2)/34.8(f1) 远超"
        "准定常域 k<<1, |C_eq| 是准定常 |Cmq| 的**下界**偏移不确定, 用于 lookup_aero damp "
        "补偿时按保守 (偏小) 阻尼处理; v4asm 等效静刚度/静表值幅度比见 cases[*].derived."
        "*_atten_vs_table (团块版 6~13%, v4asm 信号增强后上移)",
        "r 批 (Clp) 口径: 激励 = 来流矢量绕 x 旋转 (准定常等效), 非镖体真实滚转 -- "
        "该值不等于标准风洞滚转速降 Clp, 仅作同频等效阻尼估计 (F4 交付声明必带)",
        "y 批 (Cnr): tx 通道存在 X 构型滚转-偏航手性耦合巨响应 (v4asm amp 306~411, "
        "SNR 120~155, 团块版亦见 = 物理稳健; 与 11-03 T2 fy sign(α)sign(β) 同源, α=5° "
        "固定下 β 摆动激发); Cnr 只取 tz 主通道 (y_f1 的 ty SNR 1.15 太弱不可用)",
        "p 批 tx/tz 亦有响应 (X 构型强耦合), 全部提取主通道优先; 六通道完整分解见 cases",
        "归一基准 S_REF/L_REF 与 aero_table.csv 头一致 (S_REF=包围盒横径外接圆面积, "
        "保守偏大 -> 系数系统性偏小), 与 lookup_aero.aero_forces 的 damp 项口径闭合",
        "数据集 = F4 v4asm 真实装配几何重扫 (11-10 GPU 六例, GEOM=cfd_v4parts, read_stl_"
        "assembly 逐件装配空间体素化, 团块 bug 修复); 团块版对照隔离档案 "
        "damp_defaults.json.quarantined_gpu_geom_1109 (GPU 几何管线缺陷, 30 件穿插成团, "
        "amp 仅为 v4asm 的 1/2.4~1/3.5), 扫描参数与团块版全同 (仅几何源差异)",
    ]
    return out


def norm_meta(nc):
    return {
        "units": "LBM lattice (lu, step, rho_lu=1); 无量纲系数换算严格等价物理口径",
        "dataset": "F4 v4asm 真实装配几何重扫 (2026-11-10, GEOM=cfd_v4parts); 团块版隔离对照 "
                   "damp_defaults.json.quarantined_gpu_geom_1109",
        "setup_cpp_anchors": {"V_lbm(L81-82)": V_LBM, "cpm(L94)": LU_PER_M, "rho_lu(L127)": RHO_LU,
                              "SAMPLE(L140)": SAMPLE, "AMP_deg(osc_batch)": AMP_DEG,
                              "T_skip(osc_batch)": T_SKIP},
        "S_REF_m2": nc["S_REF"], "L_REF_m": nc["L_REF"], "S_lu": nc["S_lu"], "L_lu": nc["L_lu"],
        "qbar_lu": nc["qbar_lu"], "qSL2V_w": nc["qSL2V_w"],
        "zoh": "K=sinc(ωT/2) 幅度 + φ=ωT/2 相位反旋转 (setup.cpp L146-172 块首 ZOH); "
               "amp_zoh_adj 与 lockin.py 口径一致 (仅幅度)",
        "generated_by": "guidance_sim/aero/extract_damp.py",
    }


def write_json(out, path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "damp_defaults.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return path


# ---------------- 自测 (内嵌合成样本, 两频率; 不依赖网络/真数据) ----------------

def _selftest():
    rng = np.random.default_rng(440)
    nc = norm_consts()
    print("归一常数: S_lu=%.1f L_lu=%.1f qbar=%.5f qSL2V_w=%.1f (lu_per_m=%.1f)"
          % (nc["S_lu"], nc["L_lu"], nc["qbar_lu"], nc["qSL2V_w"], LU_PER_M))

    # 1) ZOH 逆变换解析对拍: 已知真值 As/Ac -> 正演测量值 -> 恢复
    for omega in (0.012566, 0.0031416):
        x = omega * SAMPLE / 2.0
        K, phi = (math.sin(x) / x if x > 0 else 1.0), x
        As_t, Ac_t = 300.0, -40.0
        As_m = K * (As_t * math.cos(phi) + Ac_t * math.sin(phi))
        Ac_m = K * (-As_t * math.sin(phi) + Ac_t * math.cos(phi))
        lk = {"As_raw": As_m, "Ac_raw": Ac_m}
        zoh_undistort(lk, omega)
        assert abs(lk["As"] - As_t) < 1e-9 and abs(lk["Ac"] - Ac_t) < 1e-9, (omega, lk)
    print("自测1 ZOH 幅度+相位逆变换解析对拍    PASS")

    # 2) 单位制换算对拍: LBM 归一 vs 物理换算路径 (docstring 推导的数值验证)
    V_phys, rho_phys = 25.0, 1.225
    lu_m = 1.0 / LU_PER_M
    dt = V_LBM * lu_m / V_phys
    M_lu, omega_lu = 57.937, 4.386e-4            # 假想 Ac=57.937, θ̇_amp
    S_p, L_p = nc["S_REF"], nc["L_REF"]
    cmq_lbm = M_lu / (nc["qSL2V_w"] * omega_lu)  # LBM 直归
    M_phys = M_lu * rho_phys * lu_m ** 5 / dt ** 2
    qSL2V_phys = 0.5 * rho_phys * V_phys * V_phys * S_p * L_p * L_p / (2 * V_phys)
    cmq_phys = M_phys / (qSL2V_phys * (omega_lu / dt))
    assert abs(cmq_lbm - cmq_phys) / abs(cmq_phys) < 1e-9, (cmq_lbm, cmq_phys)
    print("自测2 LBM 归一 = 物理换算路径 (1e-9)   PASS")

    # 3) 端到端: 合成两频率样本 (真 Cmq/Cmα) -> 锁相+ZOH+归一 -> 恢复真值
    Cmq_t, Cma_t = -2.5, 0.60                    # 贴近真实量级的假想真值
    amp_rad = math.radians(AMP_DEG)
    for omega in (0.012566, 0.0031416):
        t = np.arange(SAMPLE, STEPS + 1, SAMPLE, float)
        s, c = np.sin(omega * t), np.cos(omega * t)
        As_t = nc["qSL"] * Cma_t * amp_rad
        Ac_t = nc["qSL2V_w"] * Cmq_t * amp_rad * omega
        x = omega * SAMPLE / 2.0
        K, phi = (math.sin(x) / x if x > 0 else 1.0), x
        y = 1e4 + K * ((As_t * math.cos(phi) + Ac_t * math.sin(phi)) * s
                       + (-As_t * math.sin(phi) + Ac_t * math.cos(phi)) * c)
        y += rng.normal(0, 0.02 * abs(As_t), t.size)
        y = y[t > T_SKIP]
        tt = t[t > T_SKIP]
        lk = zoh_undistort(lockin(tt, y, omega), omega)
        cma_hat = lk["As"] / nc["qSL"] / amp_rad
        cmq_hat = lk["Ac"] / nc["qSL2V_w"] / (amp_rad * omega)
        # 主口径 (amp, 任务卡): 真值 amp = hypot(As_t, Ac_t) -> 合成数据的 amp 口径预期
        cmq_amp = -lk["amp_zoh_adj"] / nc["qSL2V_w"] / (amp_rad * omega)
        cmq_amp_true = -math.hypot(As_t, Ac_t) / nc["qSL2V_w"] / (amp_rad * omega)
        assert abs(cma_hat - Cma_t) < 0.05 * abs(Cma_t), (omega, cma_hat)
        assert abs(cmq_hat - Cmq_t) < 0.10 * abs(Cmq_t), (omega, cmq_hat)
        assert abs(cmq_amp - cmq_amp_true) < 0.01 * abs(cmq_amp_true), (omega, cmq_amp)
        print("  omega=%.5f: Cmα %.4f->%.4f  Cmq(Ac) %.3f->%.3f  Cmq(amp) %.4f->%.4f  snr=%.1f"
              % (omega, Cma_t, cma_hat, Cmq_t, cmq_hat, cmq_amp_true, cmq_amp, lk["snr"]))
    print("自测3 端到端合成恢复 (两频率)         PASS")

    # 4) 外插: 常数导数 (无频率依赖) 两点外插应还原
    v = extrapolate_omega0(-3.0, -3.0)
    assert abs(v - (-3.0)) < 1e-12
    # 线性趋势 C(ω)=1-100ω -> C0=1
    c1, c2 = 1 - 100 * 0.012566, 1 - 100 * 0.0031416
    assert abs(extrapolate_omega0(c1, c2) - 1.0) < 1e-9
    print("自测4 ω→0 两点外插                   PASS")


if __name__ == "__main__":
    no_fetch = "--no-fetch" in sys.argv
    _selftest()
    print("\n=== 真数据提取 (qianli 六例) ===")
    out = collect(no_fetch=no_fetch)
    path = write_json(out)
    print("JSON -> %s" % path)
    for k in ("Cmq", "Cnr", "Clp"):
        d = out["derivatives"][k]
        print("%s = %+.4f  [%s | %s]\n    f2=%+.4f f1=%+.4f w0(ref)=%+.4f snr=%.1f/%.1f | %s"
              % (k, d["value"], d["confidence"], d["source"],
                 d["f2_low_freq"], d["f1_high_freq"], d["omega0_extrap_unref"],
                 d["snr"]["f2"], d["snr"]["f1"], d["physics_check"]))
    # 主线锁相读数交叉对拍 (wt_jobs/tmp/f4_v4asm_lockin.json, osc_batch.sh 内联 lockin.py
    # 幅度口径): CSV 全链结果与主线读数应一致 (主线值四舍五入, 阈值 2%), 全通道非 null 项
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "wt_jobs", "tmp", "f4_v4asm_lockin.json"),
              encoding="utf-8") as f:
        mainline = json.load(f)["cases"]
    print("\namp_zoh_adj 交叉对拍 (vs 主线 f4_v4asm_lockin.json):")
    ok = True
    n_cmp = 0
    for r in out["cases"]:
        ref = mainline[r["tag"]]                     # 主线 JSON cases 为 {tag: {...}} dict
        assert abs(r["omega"] - ref["omega"]) < 1e-9
        for ch, val in ref["amp_zoh_adj"].items():
            if val is None:
                continue
            got = r["channels"][ch]["amp_zoh_adj"]
            dev = abs(got - val) / val
            ok &= dev < 0.02
            n_cmp += 1
            print("  %s/%s: %.3f vs %.3f (%.1f%%)" % (r["tag"], ch, got, val, 100 * dev))
    print("amp 对拍 %s (%d 点, 阈值 2%%)" % ("PASS" if ok else "FAIL", n_cmp))
    assert ok
    # 量级守门 (任务卡 11-11): v4asm 主值应为团块隔离版同轴 2~3 倍 (信号质量飞跃),
    # >10 倍或符号翻转 = 数据/链路异常, 拒绝交付
    blob = {"Cmq": -0.004366590561990925, "Cnr": -0.00457531454700385,
            "Clp": -0.0021246769703105453}
    print("\nvs 团块隔离版倍数 (守门 2~10x):")
    for k, v_blob in blob.items():
        ratio = out["derivatives"][k]["value"] / v_blob
        print("  %s: %+.5f / %+.5f = %.2fx" % (k, out["derivatives"][k]["value"], v_blob, ratio))
        assert 2.0 <= ratio <= 10.0, "%s 倍数 %.2f 出守门区间 (任务卡: >10 倍停手)" % (k, ratio)
    print("=== extract_damp 自测+提取全部通过 ===")
