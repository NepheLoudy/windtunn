function render_assembly_pair
% 装配位组合图: body 尾段件 (17-20) + part_24 折叠舵 + 舵孔候选轴 — 曼波指认转轴突起
root = fileparts(mfilename('fullpath'));
COM = [-0.1, 0.2, 105.5];
toB = @(P) [(COM(3)-P(:,3)), P(:,2)-COM(2), P(:,1)+COM(1)]/1000;

fig = figure('Visible','off','Position',[30 30 1700 750]);

% ---- 左: 尾段四件 + 舵 (装配位, B 系) ----
subplot(1,2,1); hold on;
for k = 17:20
    Pk = stlread(fullfile(root, sprintf('cad/v1/parts/body_%d.stl', k)));
    Pb = toB(Pk.Points);
    patch('Faces',Pk.ConnectivityList,'Vertices',Pb,...
        'FaceColor',[.55 .6 .75],'FaceAlpha',0.5,'EdgeColor',[.4 .45 .55],'EdgeAlpha',0.2);
end
P24 = stlread(fullfile(root,'cad/v1/parts/part_24.stl'));
P24b = toB(P24.Points);
patch('Faces',P24.ConnectivityList,'Vertices',P24b,...
    'FaceColor',[.95 .3 .3],'FaceAlpha',0.85,'EdgeColor','k','LineWidth',0.2);
axis equal; grid on; view(-140,20);
axis([-0.13 -0.05 -0.07 0.07 -0.07 0.07]);
title('装配位: 灰=body尾段4件 红=part\_24折叠舵');
xlabel('x_B [m]'); ylabel('y_B [m]'); zlabel('z_B [m]');

% ---- 右: 舵根+突起特写 (候选轴线: 旧find_hinges) ----
subplot(1,2,2); hold on;
patch('Faces',P24.ConnectivityList,'Vertices',P24b,...
    'FaceColor',[.95 .3 .3],'FaceAlpha',0.7,'EdgeColor',[.3 .1 .1],'EdgeAlpha',0.4);
olds = jsondecode(fileread(fullfile(root,'cad/v1/hinges.json')));
o1 = olds(1);
c0 = [(COM(3)-o1.center_mm(3)), o1.center_mm(2)-COM(2), o1.center_mm(1)+COM(1)]/1000;
a0 = [o1.axis(3), o1.axis(2), o1.axis(1)]; a0 = a0/norm(a0);
L = 0.018;
plot3(c0(1)+[-L L]*a0(1), c0(2)+[-L L]*a0(2), c0(3)+[-L L]*a0(3), 'g-', 'LineWidth', 3);
axis equal; grid on; view(-140,20);
axis([-0.105 -0.075 0.005 0.055 -0.005 0.055]);
title('舵根特写: 红=舵体 绿=旧候选轴 (穿质心=错)');
xlabel('x_B [m]'); ylabel('y_B [m]'); zlabel('z_B [m]');

sgtitle('转轴突起指认图: 镖体上的轴承凸台在哪? 舵根圆柱与它如何配合?');
out = fullfile(root,'cad/v1/assembly_pair.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
