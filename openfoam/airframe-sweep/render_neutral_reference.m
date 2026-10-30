function render_neutral_reference
% 定中参照图: 正侧视 — 弹轴直线为参照, v3 舵(绿)应与弹轴平行; 折叠位舵(红)对照
root = fileparts(mfilename('fullpath'));
fig = figure('Visible','off','Position',[30 30 1800 760]);

% ---- 正侧视 (沿 -y 看): x 水平, z 铅垂 — 舵面是否平行弹轴一眼可辨 ----
subplot(1,2,1); hold on;
for k = 17:20
    Pk = stlread(fullfile(root, sprintf('cfd_geom_multi/body_%d.stl', k)));
    patch('Faces',Pk.ConnectivityList,'Vertices',Pk.Points,...
        'FaceColor',[.5 .55 .7],'FaceAlpha',0.30,'EdgeColor','none');
end
F = stlread(fullfile(root,'cad/v1/cfd_parallel/fin_1.stl'));
patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
    'FaceColor',[.25 .85 .45],'FaceAlpha',0.9,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.5);
P24 = stlread(fullfile(root,'cad/v1/parts/part_24.stl'));
Pr = P24.Points;
Pr = [(COM3()-Pr(:,3)) (Pr(:,2)-COM2()) (Pr(:,1)+COM1())]/1000;
patch('Faces',P24.ConnectivityList,'Vertices',Pr,...
    'FaceColor',[.95 .25 .25],'FaceAlpha',0.45,'EdgeColor','none');
% 弹轴参照线 (y=z=0, x -0.15..0.15)
plot3([-0.15 0.15],[0 0],[0 0],'k-.','LineWidth',1.5);
% 铰链轴 (解析)
asm = jsondecode(fileread(fullfile(root,'cad/v1/cfd_parallel/airframe_assembly.json')));
s1 = asm.control_surfaces(1);
p = s1.hinge_line(1,:); q = s1.hinge_line(2,:);
plot3([p(1) q(1)],[p(2) q(2)],[p(3) q(3)],'m-','LineWidth',3);
axis equal; grid on; view(0, 0);
axis([-0.14 0.02 -0.06 0.06]);
title('正侧视 (沿 -y 看): 绿=v3舵(δ=0) 红透=折叠位 黑点划=弹轴');
xlabel('x_B [m]'); ylabel('z_B [m]');
function v = COM3(), v = 105.5; end
function v = COM2(), v = 0.2; end
function v = COM1(), v = 0.1; end

% ---- 右: 后视 (沿 +x 看): 四舵 X 对称 ----
subplot(1,2,2); hold on;
for k = 1:4
    F = stlread(fullfile(root, sprintf('cad/v1/cfd_parallel/fin_%d.stl', k)));
    patch('Faces',F.ConnectivityList,'Vertices',F.Points,...
        'FaceColor',[.25 .85 .45],'FaceAlpha',0.8,'EdgeColor',[.1 .3 .15],'EdgeAlpha',0.5);
    s = asm.control_surfaces(k);
    p = s.hinge_line(1,:); q = s.hinge_line(2,:);
    plot3([p(1) q(1)],[p(2) q(2)],[p(3) q(3)],'m-','LineWidth',2.5);
end
axis equal; grid on; view(-90, 0);
axis([-0.095 -0.080 -0.055 0.055 -0.055 0.055]);
title('后视: 四舵 X 对称 + 品红铰链轴');
xlabel('y_B [m]'); zlabel('z_B [m]');

sgtitle('定中参照: δ=0 舵面应平行于弹轴 (与黑点划线平行), 折叠位(红)为45°斜置对照');
out = fullfile(root,'cad/v1/neutral_reference.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
end
