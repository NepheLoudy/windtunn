// ============================================================================
// 镖体绕流 LBM 瞬态求解 — FluidX3D T2 线 (算力节点 RTX 5070)
// 使命: 大攻角端点 (|α|≥12.5°) 非对称涡的瞬态统计 — 根治 FVM 稳态的侧向分支不确定
// 几何: <geom_dir>/ body.stl + fin_1..4.stl (B 系米制, 质心原点)
// 用法: bin/FluidX3D [geom_dir] [steps] [tag]
//   geom_dir 默认 "cfd/" (带尾斜杠); steps 默认 300000; tag 用于输出文件名区分变体
//   → out/forces<tag>.csv (每 500 步: t, F_lu, M_lu 绕质心)
// Phase 0 诊断矩阵 (11-01): 一次编译, 四几何变体冒烟 — TYPE_S 体素计数 + 首力
// ============================================================================
#include "src/info.hpp"
#include "src/lbm.hpp"
#include "src/setup.hpp"
#include <cstdio>
#include <cstdlib>
#include <sys/stat.h>

int main(int argc, char* argv[]) {
	const std::string GEOM = (argc>1)? argv[1] : "cfd/";
	const uint STEPS = (argc>2)? (uint)atoi(argv[2]) : 300000u;
	const std::string TAG = (argc>3)? argv[3] : "";
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
	lbm.voxelize_stl(get_exe_path()+GEOM+"body.stl", center, cells_per_m, TYPE_S);
	for (const char* f : {"fin_1.stl","fin_2.stl","fin_3.stl","fin_4.stl"})
		lbm.voxelize_stl(get_exe_path()+GEOM+f, center, cells_per_m, TYPE_S);

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
	const uint SAMPLE = 500;
	const float3 com = center;   // STL 以质心对齐网格中心
	printf("==== PHASE0 %s steps=%u ====\n", GEOM.c_str(), STEPS);
	print_info(lbm);   // 体素类型计数表 — Phase 0 的关键观测
	FILE* f = fopen((OUT+"forces"+TAG+".csv").c_str(), "w");
	fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");
	fclose(f);

	for (uint t=0u; t<STEPS; t+=SAMPLE) {
		lbm.run(SAMPLE);
		lbm.update_force_field();
		const float3 F = lbm.object_force();
		const float3 T = lbm.object_torque(com);
		FILE* g = fopen((OUT+"forces"+TAG+".csv").c_str(), "a");
		fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n",
			t+SAMPLE, F.x, F.y, F.z, T.x, T.y, T.z);
		fclose(g);
		if (t==0u) { printf("---- first force ----\n"); print_info(lbm); }
	}
	print_info(lbm);
	return 0;
}
