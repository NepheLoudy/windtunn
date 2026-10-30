function render_rear_view_v3
% 后视图验收: 从尾部看四舵 X 对称中置 + 品红轴线 + body 突起
root = fileparts(mfilename('fullpath'));
asm = jsondecode(fileread(fullfile(root,'cad/v1/cfd_parallel/airframe_assembly.json')));
fig = figure('Visible','off','Position',[40 40 1500 720]);

subplot(1,2,1); hold on;
for k = 1:4
    Pk = stlread(fullfile(root, sprintf('cfd_geom_multi/body_%d.stl', 16+k)));
    patch('Faces',Pk.ConnectivityList,'Vertices',Pk.Points,...
        'FaceColor',[.5 .55 .7],'FaceAlpha',0.35,'EdgeColor',[.4 .45 .55],'EdgeAlpha',0.15);
end
for k = 1:4
    F = stlread(fullfile(root, sprintf('cad/v1/cfd_parallel/fin_%d.stl', k)));
    patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
        'FaceColor',[.25 .85 .45],'FaceAlpha',0.85,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.4);
    s = asm.control_surfaces(k);
    p = s.hinge_line(1,:); q = s.hinge_line(2,:);
    plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'm-', 'LineWidth', 3);
end
axis equal; grid on; view(-90, 0);
axis([-0.095 -0.082 -0.06 0.06 -0.06 0.06]);
title('后视 (沿 +x 看向头部): 四舵 X 对称中置 + 品红轴线');
xlabel('y_B'); ylabel('z_B'); zlabel('x_B');

subplot(1,2,2); hold on;
for k = 1:4
    F = stlread(fullfile(root, sprintf('cad/v1/cfd_parallel/fin_%d.stl', k)));
    patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
        'FaceColor',[.25 .85 .45],'FaceAlpha',0.75,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.5);
end
axis equal off; view(-90, 0);
axis([-0.095 -0.082 -0.055 0.055 -0.055 0.055]);
title('四舵 only — 中置对称检查');
camlight; lighting gouraud;

sgtitle('v3 后视验收: 四舵 X 对称中置, 品红 = 解析铰链轴 (r=2.000mm)');
out = fullfile(root,'cad/v1/rear_view_v3.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
end
