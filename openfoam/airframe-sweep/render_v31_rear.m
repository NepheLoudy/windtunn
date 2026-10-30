function render_v31_rear
% v3.1 后视验收: 舵面立起平行弹轴 (定中) + 品红轴线 + body 突起
root = fileparts(mfilename('fullpath'));
fig = figure('Visible','off','Position',[40 40 1500 720]);
asm = jsondecode(fileread(fullfile(root,'cad/v1/cfd_parallel/airframe_assembly.json')));

subplot(1,2,1); hold on;
for k = 17:20
    Pk = stlread(fullfile(root, sprintf('cfd_geom_multi/body_%d.stl', k)));
    patch('Faces',Pk.ConnectivityList,'Vertices',Pk.Points,...
        'FaceColor',[.5 .55 .7],'FaceAlpha',0.3,'EdgeColor','none');
end
for k = 1:4
    F = stlread(fullfile(root, sprintf('cad/v1/cfd_parallel/fin_%d.stl', k)));
    patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
        'FaceColor',[.25 .85 .45],'FaceAlpha',0.85,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.4);
    s = asm.control_surfaces(k);
    p = s.hinge_line(1,:); q = s.hinge_line(2,:);
    plot3([p(1) q(1)],[p(2) q(2)],[p(3) q(3)],'m-','LineWidth',3);
end
axis equal; grid on; view(-90, 0);
axis([-0.095 -0.082 -0.055 0.055 -0.055 0.055]);
title('后视: 舵面立起 (平行弹轴=定中) + 品红轴');
xlabel('y_B'); zlabel('z_B');

subplot(1,2,2); hold on;
for k = 17:20
    Pk = stlread(fullfile(root, sprintf('cfd_geom_multi/body_%d.stl', k)));
    patch('Faces',Pk.ConnectivityList,'Vertices',Pk.Points,...
        'FaceColor',[.6 .65 .8],'FaceAlpha',0.45,'EdgeColor',[.45 .5 .6],'EdgeAlpha',0.25);
end
F = stlread(fullfile(root,'cad/v1/cfd_parallel/fin_1.stl'));
patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
    'FaceColor',[.25 .85 .45],'FaceAlpha',0.8,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.4);
s = asm.control_surfaces(1);
p = s.hinge_line(1,:); q = s.hinge_line(2,:);
plot3([p(1) q(1)],[p(2) q(2)],[p(3) q(3)],'m-','LineWidth',4);
axis equal; grid on; view(160, 25);
axis([-0.11 -0.075 0.005 0.05 0.005 0.05]);
title('fin_1 侧后特写: 舵管套在 body 突起, 板面顺流');
xlabel('x_B'); ylabel('y_B'); zlabel('z_B');

sgtitle('v3.1 验收: 旋转方向修正 (+→−44.94°) — 板面平行弹轴 |n_x|=0.074, 轴套贴合 0.42mm');
out = fullfile(root,'cad/v1/v31_rear.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
end
