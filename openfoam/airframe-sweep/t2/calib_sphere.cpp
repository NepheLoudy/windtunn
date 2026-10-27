// ============================================================================
// T2 标定实验: 圆球绕流 (Re=1000, 理论 Cd≈0.47±0.03) — 验证力采样+单位链的 bias
// 同镖体管线: TYPE_E 六面边界 + FORCE_FIELD 采样 + 相同单位链换算
// 若球 Cd 也 ~5 → 采样/换算链有系统性 bias; 若 Cd≈0.5 → bias 在镖体 STL 体素化
// ============================================================================
#include "src/info.hpp"
#include "src/lbm.hpp"
#include "src/setup.hpp"
#include <cstdio>
#include <sys/stat.h>

int main(int argc, char* argv[]) {
	const std::string OUT = get_exe_path()+"out/";
	mkdir(OUT.c_str(), S_IRWXU);

	// 球径 D=40 格, 域 120^3 (球占 1/3), Re=1000: nu = u*D/Re
	const uint  N = 120;
	const float u_lbm  = 0.05f;
	const float D_lbm  = 40.0f;
	const float Re     = 1000.0f;
	const float nu_lbm = u_lbm*D_lbm/Re;   // = 0.002 (tau≈0.5006 临界, 但球例官方同域可用)

	LBM lbm(N, N, N, nu_lbm);
	const float3 center = float3(0.5f*N, 0.5f*N, 0.5f*N);

	// 来流沿 -x (与镖体工况同向), 边界 TYPE_E
	parallel_for(lbm.get_N(), [&](ulong n) { uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);
		if(lbm.flags[n]!=TYPE_S) { lbm.u.x[n]=-u_lbm; lbm.u.y[n]=0.0f; lbm.u.z[n]=0.0f; lbm.rho[n]=1.0f; }
		if(sphere(x, y, z, center, 0.5f*D_lbm)) lbm.flags[n] = TYPE_S|TYPE_X;
		if(x==0u||x==N-1u||y==0u||y==N-1u||z==0u||z==N-1u) lbm.flags[n] = TYPE_E;
	});

	const uint STEPS = 60000u, SAMPLE = 200u;   // Re=1000 球 60k 步足够稳态
	FILE* f = fopen((OUT+"sphere_forces.csv").c_str(), "w");
	fprintf(f, "t,fx,fy,fz\n");
	fclose(f);
	for (uint t=0u; t<STEPS; t+=SAMPLE) {
		lbm.run(SAMPLE);
		lbm.update_force_field();
		const float3 F = lbm.object_force(TYPE_S|TYPE_X);
		FILE* g = fopen((OUT+"sphere_forces.csv").c_str(), "a");
		fprintf(g, "%u,%.6g,%.6g,%.6g\n", t+SAMPLE, F.x, F.y, F.z);
		fclose(g);
	}
	// 时均 Cd (官方换算链: unit_m=D_lbm 格↔1 m 球径; 单位链自洽即可算 Cd=2F/(rho u² A))
	return 0;
}
