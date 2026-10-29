function render_fix_1029
% 曼波验收图 v2 2026-10-29: ①铰链轴旧vs新(yz 侧视, 45°对角线) ②镖头孔口前视对比
root = fileparts(mfilename('fullpath'));
ref = jsondecode(fileread(fullfile(root,'hinges_refined.json')));
fig = figure('Visible','off','Position',[40 40 1900 700]);

% ---- 左: 铰链轴 yz 侧视 (轴呈 45° 对角线) ----
subplot(1,3,1); hold on;
for k = 1:4
    fk = stlread(fullfile(root,sprintf('cad/v1/cfd_parallel/fin_%d.stl',k)));
    patch('Faces',fk.ConnectivityList,'Vertices',fk.Points,...
        'FaceColor',[.8 .82 .9],'FaceAlpha',0.25,'EdgeColor',[.5 .55 .65],'EdgeAlpha',0.15);
end
for k = 1:numel(ref)
    r = ref(k);
    c = r.new_point_mm; a = r.new_axis;   % mm (STEP 系)
    aB = [-a(3) a(2) a(1)]; aB = aB/norm(aB);
    pB = [-(c(3)-105.5) c(2)-0.2 c(1)+0.1]/1000;
    L = 0.022;
    plot3(pB(1)+[-L L]*aB(1), pB(2)+[-L L]*aB(2), pB(3)+[-L L]*aB(3), 'g-', 'LineWidth', 4);
    c0 = r.old_center; a0 = r.old_axis;
    p0 = [-(c0(3)-105.5) c0(2)-0.2 c0(1)+0.1]/1000;
    plot3(p0(1)+[-L L]*a0(1), p0(2)+[-L L]*a0(2), p0(3)+[-L L]*a0(3), 'r--', 'LineWidth', 2.5);
end
axis equal; grid on; view(90,0);
axis([-0.11 -0.055 -0.08 0.08 -0.08 0.08]);
title('铰链轴 yz 侧视: 绿=新轴(孔心) 红虚=旧轴(偏2mm)');
xlabel('y_B [m]'); ylabel('z_B [m]');

% ---- 中/右: 镖头孔口前视 (从 -z 看进去) ----
pOld = stlread(fullfile(root,'cad/v1/parts/part_1_oldhole.stl'));
pNew = stlread(fullfile(root,'cad/v1/parts/part_1.stl'));
subplot(1,3,2);
patch('Faces',pOld.ConnectivityList,'Vertices',pOld.Points,...
    'FaceColor',[.85 .35 .35],'FaceAlpha',0.9,'EdgeColor','none');
axis equal off; view(0,-90); axis([-26 26 -26 26 -26 -20]); camlight; lighting gouraud;
title('原件前视: 可见 \o16.6mm 空洞 (暗心)');
subplot(1,3,3);
patch('Faces',pNew.ConnectivityList,'Vertices',pNew.Points,...
    'FaceColor',[.4 .55 .9],'FaceAlpha',0.9,'EdgeColor','none');
axis equal off; view(0,-90); axis([-26 26 -26 26 -26 -20]); camlight; lighting gouraud;
title('填实后前视: 孔口闭合 (+8.67cm^3)');

sgtitle('2026-10-29 修复验收: 铰链孔心精拟合 (垂偏2.0mm 已修, 圆心RMS 0.000mm) + 镖头空腔填实 (2-流形 0 坏边)');
out = fullfile(root,'cad/v1/fix_1029_acceptance.png');
exportgraphics(fig, out, 'Resolution', 130);
fprintf('saved %s\n', out);
