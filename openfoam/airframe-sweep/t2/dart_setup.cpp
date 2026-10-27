// ============================================================================
// 镖体绕流 LBM 瞬态求解 — FluidX3D T2 线 (算力节点 RTX 5070)
// 使命: 大攻角端点 (|α|≥12.5°) 非对称涡的瞬态统计 — 根治 FVM 稳态的侧向分支不确定
// 几何: cfd/ body.stl + fin_1..4.stl (B 系米制, 质心原点)
// 需要: defines.hpp 开 FORCE_FIELD; 编译 make Linux -j20
// 运行: bin/FluidX3D  → out/forces.csv (每 500 步: t, F_lu, M_lu 绕质心)
// ============================================================================
#include "src/info.hpp"
#include "src/lbm.hpp"
#include "src/setup.hpp"
#include <cstdio>
#include <sys/stat.h>

int main(int argc, char* argv[]) {
	const std::string OUT = get_exe_path()+"out/";
	mkdir(OUT.c_str(), S_IRWXU);

	// ---------------- 网格与物理 (格子单位) ----------------
	// 220 格 = 0.2386 m (弹长) → dx ≈ 1.085 mm
	const uint  Nx = 220, Ny = 120, Nz = 120;
	const float nu_lbm = 0.01f;
	const float V_lbm  = 0.05f;

	LBM lbm(Nx, Ny, Nz, nu_lbm, 13);

	// ---------------- 镖体体素化 ----------------
	const float3 center = float3(0.5f*Nx, 0.5f*Ny, 0.5f*Nz);
	const float  cells_per_m = Nx/0.2386f;
	lbm.voxelize_stl(get_exe_path()+"cfd/body.stl", center, cells_per_m, TYPE_S);
	for (const char* f : {"fin_1.stl","fin_2.stl","fin_3.stl","fin_4.stl"})
		lbm.voxelize_stl(get_exe_path()+std::string("cfd/")+f, center, cells_per_m, TYPE_S);

	// ---------------- 来流 (B 系: x 前弹轴, y 右, z 下) ----------------
	// 扫描变量: alpha=12.5° (大攻角端点专项首点), beta=0
	const float alpha_deg = 12.5f, beta_deg = 0.0f, V_phys = 25.0f;
	const float A = alpha_deg*3.14159265f/180.0f, B = beta_deg*3.14159265f/180.0f;
	const float3 U = float3(-V_lbm*cos(A)*cos(B), -V_lbm*sin(B), -V_lbm*sin(A)*cos(B));
	lbm.require_boundary_conditions();
	lbm.set_velocity(U, TYPE_G);

	// ---------------- 瞬态运行 + 力/力矩采样 ----------------
	// 力/力矩: FORCE_FIELD 宏下 lbm.object_force()/object_torque() (格子单位)
	// 质心 = 镖体几何中心 (网格中心), 绕 B 系 y 轴力矩 = Cm 原始量
	const uint STEPS = 300000, SAMPLE = 500;
	const float3 com = center;   // STL 以质心对齐网格中心
	FILE* f = fopen((OUT+"forces.csv").c_str(), "w");
	fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");
	fclose(f);

	print_info(lbm);
	for (uint t=0u; t<STEPS; t+=SAMPLE) {
		lbm.run(SAMPLE);
		lbm.update_force_field();
		const float3 F = lbm.object_force();
		const float3 T = lbm.object_torque(com);
		FILE* g = fopen((OUT+"forces.csv").c_str(), "a");
		fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n",
			t+SAMPLE, F.x, F.y, F.z, T.x, T.y, T.z);
		fclose(g);
	}
	print_info(lbm);
	return 0;
}
