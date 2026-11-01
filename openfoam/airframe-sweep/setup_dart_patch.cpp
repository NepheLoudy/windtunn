void main_setup() { // dart LBM transient (T2); required extensions: FORCE_FIELD
	// Phase 0 修复 (11-01): 26 件 CONCAT 多壳 body 击穿 voxelize_stl 射线奇偶性 (折叠 era
	// 单壳 body 有力 0.245lu, 10-30 换 concat 后全零) — 解法 = 逐零件体素化 (每件单壳,
	// 与舵面同款)。几何目录/步数/输出标签走环境变量, 一次编译跑诊断矩阵:
	//   GEOM_DIR=cfd_v4parts/ STEPS=2000 TAG=_v4parts bin/FluidX3D
	const char* geom_env = getenv("GEOM_DIR");
	const std::string GEOM = geom_env ? std::string(geom_env) : std::string("cfd_v4parts/");
	const char* steps_env = getenv("STEPS");
	const uint STEPS = steps_env ? (uint)atoi(steps_env) : 300000u;
	const char* tag_env = getenv("TAG");
	const std::string TAG = tag_env ? std::string(tag_env) : std::string("");
	const std::string OUT = get_exe_path()+"out/";
	mkdir(OUT.c_str(), S_IRWXU);
	const uint  Nx = 220u, Ny = 120u, Nz = 120u;
	const float nu_lbm = 0.01f, V_lbm = 0.05f;
	LBM lbm(Nx, Ny, Nz, nu_lbm);
	const float3 center = float3(0.5f*Nx, 0.5f*Ny, 0.5f*Nz);
	const float  cpm = Nx/0.2386f;
	// 逐零件体素化: body_*.stl (26 件, 每件单闭合壳) + fin_*.stl (v4 真轴舵)
	DIR* dir = opendir(get_exe_path().c_str()+GEOM);
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
	printf("==== PHASE0 GEOM=%s parts=%u fins=%u steps=%u ====\n", GEOM.c_str(), n_body_parts, n_fins, STEPS);
	const float alpha_deg = 12.5f, beta_deg = 0.0f;
	const float A = alpha_deg*3.14159265f/180.0f, B2 = beta_deg*3.14159265f/180.0f;
	const float3 U = float3(-V_lbm*cos(A)*cos(B2), -V_lbm*sin(B2), -V_lbm*sin(A)*cos(B2));
	parallel_for(lbm.get_N(), [&](ulong n) { uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);
		if(lbm.flags[n]!=TYPE_S) { lbm.u.x[n]=U.x; lbm.u.y[n]=U.y; lbm.u.z[n]=U.z; lbm.rho[n]=1.0f; }
		if(x==0u||x==Nx-1u||y==0u||y==Ny-1u||z==0u||z==Nz-1u) lbm.flags[n] = TYPE_E;
	});
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
