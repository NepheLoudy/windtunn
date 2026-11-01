// setup.cpp — T2 dart LBM transient ( FluidX3D qianli 5070 )
// 11-01 v2 minimal: 上游示例已删(远端 ASCII locale 写中文注释曾截断本文件),
// 只保留 dart 实验。坑防线: ①逐零件体素化(多壳射线奇偶 bug) ②TYPE_X 补标(力求和口径 bug)
// ③体素质心观测 ④SEED 扰动(分支统计)。env: GEOM_DIR STEPS TAG ALPHA BETA NX NU V_LBM SEED
#include "info.hpp"
#include "lbm.hpp"
#include "setup.hpp"
#include <cstdio>
#include <cstdlib>
#include <dirent.h>
#include <sys/stat.h>

void main_setup() { // dart LBM transient (T2) v2
	const char* geom_env = getenv("GEOM_DIR");
	const std::string GEOM = geom_env ? std::string(geom_env) : std::string("cfd_v4parts/");
	const char* steps_env = getenv("STEPS");
	const uint STEPS = steps_env ? (uint)atoi(steps_env) : 300000u;
	const char* tag_env = getenv("TAG");
	const std::string TAG = tag_env ? std::string(tag_env) : std::string("");
	const char* a_env = getenv("ALPHA");
	const char* b_env = getenv("BETA");
	const float alpha_deg = a_env ? (float)atof(a_env) : 12.5f;
	const float beta_deg = b_env ? (float)atof(b_env) : 0.0f;
	const char* nx_env = getenv("NX");
	const uint Nx = nx_env ? (uint)atoi(nx_env) : 220u;
	const uint Ny = (uint)((float)Nx*120.0f/220.0f + 0.5f);
	const uint Nz = Ny;
	const char* nu_env = getenv("NU");
	const float nu_lbm = nu_env ? (float)atof(nu_env) : 0.01f;
	const char* v_env = getenv("V_LBM");
	const float V_lbm = v_env ? (float)atof(v_env) : 0.05f;
	const char* seed_env = getenv("SEED");
	const ulong seed = seed_env ? (ulong)strtoull(seed_env, NULL, 10) : 0ull;
	const std::string OUT = get_exe_path()+"out/";
	mkdir(OUT.c_str(), S_IRWXU);
	LBM lbm(Nx, Ny, Nz, nu_lbm);
	const float3 center = float3(0.5f*Nx, 0.5f*Ny, 0.5f*Nz);
	const float  cpm = Nx/0.2386f;
	DIR* dir = opendir((get_exe_path()+GEOM).c_str());
	uint n_body_parts = 0u, n_fins = 0u;
	if (dir) {
		struct dirent* e;
		while ((e = readdir(dir))) {
			std::string name(e->d_name);
			if (name.rfind("body_", 0) == 0 && name.size() > 4 && name.substr(name.size()-4) == ".stl") {
				lbm.voxelize_stl(get_exe_path()+GEOM+name, center, cpm, TYPE_S); n_body_parts++;
			} else if (name.rfind("fin_", 0) == 0 && name.size() > 4 && name.substr(name.size()-4) == ".stl") {
				lbm.voxelize_stl(get_exe_path()+GEOM+name, center, cpm, TYPE_S); n_fins++;
			}
		}
		closedir(dir);
	}
	parallel_for(lbm.get_N(), [&](ulong n) {
		if(lbm.flags[n]==TYPE_S) lbm.flags[n] = TYPE_S|TYPE_X; // force summation exact match
	});
	const float3 solid_com = lbm.object_center_of_mass(TYPE_S|TYPE_X);
	printf("==== PHASE0 v2 GEOM=%s parts=%u fins=%u steps=%u NX=%u nu=%.4f V=%.4f alpha=%.2f beta=%.2f seed=%llu\n",
		GEOM.c_str(), n_body_parts, n_fins, STEPS, Nx, nu_lbm, V_lbm, alpha_deg, beta_deg, (unsigned long long)seed);
	printf("==== SOLID_COM %.3f %.3f %.3f (grid %ux%ux%u) ====\n", solid_com.x, solid_com.y, solid_com.z, Nx, Ny, Nz);
	const float A = alpha_deg*3.14159265f/180.0f, B2 = beta_deg*3.14159265f/180.0f;
	const float3 U = float3(-V_lbm*cos(A)*cos(B2), -V_lbm*sin(B2), -V_lbm*sin(A)*cos(B2));
	parallel_for(lbm.get_N(), [&](ulong n) { uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);
		if(lbm.flags[n]!=TYPE_S) { lbm.u.x[n]=U.x; lbm.u.y[n]=U.y; lbm.u.z[n]=U.z; lbm.rho[n]=1.0f; }
		if(x==0u||x==Nx-1u||y==0u||y==Ny-1u||z==0u||z==Nz-1u) lbm.flags[n] = TYPE_E;
	});
	if (seed) {
		parallel_for(lbm.get_N(), [&](ulong n) {
			if((lbm.flags[n]&TYPE_S) == 0) {
				const float g1 = (float)((n*2654435761u ^ (seed*97531u+13u)) & 0xFFFF)/32768.0f - 1.0f;
				const float g2 = (float)((n*1597334677u ^ (seed*40503u+71u)) & 0xFFFF)/32768.0f - 1.0f;
				const float g3 = (float)((n*374761393u ^ (seed*66826u+5u)) & 0xFFFF)/32768.0f - 1.0f;
				lbm.u.x[n] *= 1.0f + 0.03f*g1; lbm.u.y[n] *= 1.0f + 0.03f*g2; lbm.u.z[n] *= 1.0f + 0.03f*g3;
			}
		});
	}
	const uint SAMPLE = 500u;
	const float3 com = center;
	FILE* f = fopen((OUT+"forces"+TAG+".csv").c_str(), "w");
	fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");
	fclose(f);

	for (uint t=0u; t<STEPS; t+=SAMPLE) {
		lbm.run(SAMPLE);
		lbm.update_force_field();
		const float3 F = lbm.object_force(TYPE_S|TYPE_X);
		const float3 T = lbm.object_torque(com, TYPE_S|TYPE_X);
		FILE* g = fopen((OUT+"forces"+TAG+".csv").c_str(), "a");
		fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n", t+SAMPLE, F.x, F.y, F.z, T.x, T.y, T.z);
		fclose(g);
	}
}
