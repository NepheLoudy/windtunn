// ============================================================================
// 镖体绕流 LBM 瞬态求解 — FluidX3D T2 线 (算力节点 RTX 5070)
// 使命: 大攻角端点 (|α|≥12.5°) 非对称涡的瞬态统计 — 根治 FVM 稳态的侧向分支不确定
// 几何: cfd/ body.stl + fin_1..4.stl (B 系米制, 质心原点, 见 cad/v1/cfd/)
// 运行: bin/FluidX3D  (无 X11 headless 编译, 输出 VTK/CSV 到 out/)
// 编译: make Linux -j20   (需 ocl-icd-opencl-dev; nvidia.icd 已注册 RTX 5070)
// ============================================================================
#include "src/info.hpp"
#include "src/lbm.hpp"
#include "src/setup.hpp"

int main(int argc, char* argv[]) {
	const std::string OUT = get_exe_path()+"out/";
	mkdir(OUT.c_str(), S_IRWXU);

	// ---------------- 物理与网格参数 ----------------
	// 真实: 弹长 0.2386 m, 来流 V=25 m/s, 空气 ν=1.5e-5 m²/s
	// LBM 单位: dx = 弹长/200 格 (Δx≈1.19 mm) → Nx×Ny×Nz = 220×120×120 ≈ 317 万格
	//           τ 由 ν_lbm = ν_phys × dx²/dt² 换算, FluidX3D 以 nu (lu/s) 输入
	// 参考叶轮经验: τ≈0.53 稳定下限; 此处 ν_lbm 目标 ~0.01 lu/s (对应 Ma≈0.073, 低马赫安全)
	const uint  Nx = 220;
	const uint  Ny = 120;
	const uint  Nz = 120;
	const float nu_lbm = 0.01f;               // 格子单位运动黏度
	const float V_lbm  = 0.05f;               // 格子单位来流速度 (Ma≈0.087)

	LBM lbm(Nx, Ny, Nz, nu_lbm, 13);

	// ---------------- 几何: 体素化镖体 STL ----------------
	// cfd/ 的 body+fin STL 为 B 系米制、质心原点 — 与 LBM 格子原点直接对齐
	// 格子中心域: x∈[-0.13,+0.13], LBM 网格中心 = (Nx/2, Ny/2, Nz/2) 格
	const float3 center = float3(0.5f*Nx, 0.5f*Ny, 0.5f*Nz);
	const float  dx     = Nx/220.0f;          // lu/phys 比例: 220 格 = 0.2386 m → dx≈1.085mm
	// 体素化弹身 (无旋转, 米制 STL, size=每米格数)
	lbm.voxelize_stl(get_exe_path()+"cfd/body.stl", center, 1.0f/dx, TYPE_S);
	// 四片舵面 (零舵偏位形; 舵偏扫描后续通过旋转 STL 或组合 flag 实现)
	for (const char* f : {"fin_1.stl","fin_2.stl","fin_3.stl","fin_4.stl"}) {
		lbm.voxelize_stl(get_exe_path()+std::string("cfd/")+f, center, 1.0f/dx, TYPE_S);
	}

	// ---------------- 边界条件与初始场 ----------------
	// 来流: 沿 -x_B? — B 系 x 为弹轴朝前, 来流相对镖体沿 -x → U=(-V,0,0) (无攻角基线)
	// 攻角/侧滑扫描: 旋转来流矢量 U=(-V cosα cosβ, -V sinβ, -V sinα cosβ) (B 系)
	const float alpha_deg = 12.5f;             // ← 扫描变量 (大攻角端点专项首点)
	const float beta_deg  = 0.0f;
	const float V_phys    = 25.0f;
	const float A = alpha_deg*3.14159265f/180.0f, B = beta_deg*3.14159265f/180.0f;
	const float3 U = float3(-V_lbm*cos(A)*cos(B), -V_lbm*sin(B), -V_lbm*sin(A)*cos(B));
	lbm.require_boundary_conditions();
	lbm.set_velocity(U, TYPE_G);               // 全场初始化 + 边界 (G=移动壁面式来流)

	// ---------------- 运行 ----------------
	const uint STEPS = 300000;                 // LBM 步数: 涡脱落周期 >> FVM 瞬态需求
	const uint STABLE_STEP = lbm.get_rate();   // 自动步频
	print_info(lbm);
	lbm.run(STEPS);

	// ---------------- 力采样输出 (每 500 步追加 CSV) ----------------
	// B 系力 → 系数: CL=-Fz_lbm/(0.5ρV²S) 换算见后处理; 此处输出格子单位原始力
	for (uint t=0u; t<=STEPS; t+=500u) {
		const float3 F = lbm.get_forces();     // 格子单位合力 (流体作用于镖体)
		FILE* f = fopen((OUT+"forces.csv").c_str(), "a");
		fprintf(f, "%u,%.6g,%.6g,%.6g\n", t, F.x, F.y, F.z);
		fclose(f);
		if (t < STEPS) lbm.run(500u);
	}
	print_info(lbm);
	return 0;
}
