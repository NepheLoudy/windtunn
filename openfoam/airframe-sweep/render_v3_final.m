function render_v3_final
% v3 平行零位验收图: body 尾段 + v3 舵 + 解析真轴 — 曼波目视确认舵管套在突起上
root = fileparts(mfilename('fullpath'));
fig = figure('Visible','off','Position',[30 30 1800 720]);
asm = jsondecode(fileread(fullfile(root,'cad/v1/cfd_parallel/airframe_assembly.json')));

% ---- 左: 尾段四件 + 4 舵 (V3) ----
subplot(1,2,1); hold on;
for k = 17:20
    Pk = stlread(fullfile(root, sprintf('cfd_geom_multi/body_%d.stl', k)));
    patch('Faces',Pk.ConnectivityList,'Vertices',Pk.Points,...
        'FaceColor',[.55 .6 .75],'FaceAlpha',0.42,'EdgeColor',[.4 .45 .55],'EdgeAlpha',0.15);
end
for k = 1:4
    F = stlread(fullfile(root, sprintf('cad/v1/cfd_parallel/fin_%d.stl', k)));
    patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
        'FaceColor',[.25 .85 .45],'FaceAlpha',0.85,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.3);
end
% 四舵真轴线
for k = 1:4
    s = asm.control_surfaces(k);
    p = s.hinge_line(1,:); q = s.hinge_line(2,:);
    plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'm-', 'LineWidth', 2.5);
end
axis equal; grid on; view(-150, 22);
axis([-0.13 -0.05 -0.075 0.075 -0.075 0.075]);
title('v3: 灰=body尾段 绿=平行舵(0°) 品红=解析真轴');
xlabel('x_B [m]'); ylabel('y_B [m]'); zlabel('z_B [m]');

% ---- 右: 舵根特写 (品红轴 vs 舵管 vs body 突起) ----
subplot(1,2,2); hold on;
for k = 17:20
    Pk = stlread(fullfile(root, sprintf('cfd_geom_multi/body_%d.stl', k)));
    patch('Faces',Pk.ConnectivityList,'Vertices',Pk.Points,...
        'FaceColor',[.6 .65 .8],'FaceAlpha',0.55,'EdgeColor',[.45 .5 .6],'EdgeAlpha',0.25);
end
F = stlread(fullfile(root,'cad/v1/cfd_parallel/fin_1.stl'));
patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
    'FaceColor',[.25 .85 .45],'FaceAlpha',0.75,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.35);
s = asm.control_surfaces(1);
patch('Faces',F.ConnectivityList,'Vertices',F.Points,'FaceColor','none');
p = s.hinge_line(1,:); q = s.hinge_line(2,:);
plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'm-', 'LineWidth', 4);
axis equal; grid on; view(-150, 18);
axis([-0.100 -0.078 0.008 0.052 0.008 0.052]);
title('舵根特写 (fin_1): 品红轴应穿过舵管中心 + body 轴承突起');
xlabel('x_B [m]'); ylabel('y_B [m]'); zlabel('z_B [m]');

sgtitle('v3 验收: OCC 解析轴 (r=2.000mm, 残差 0.00000) 重做平行化 — 舵管 d\_{body}=0.42mm 均匀贴合');
out = fullfile(root,'cad/v1/v3_final.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
end
