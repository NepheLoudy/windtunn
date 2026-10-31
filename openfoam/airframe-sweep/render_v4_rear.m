function render_v4_rear
% v4 后视验收: 真铰链轴 (双耳孔心连线) — 品红线端点=耳孔心, body 销同轴
root = fileparts(mfilename('fullpath'));
fig = figure('Visible', 'off', 'Position', [40 40 1500 720]);
try, fig.Theme = 'light'; catch, end
asm = jsondecode(fileread(fullfile(root, 'cad/v1/cfd_parallel/airframe_assembly.json')));

% ---- 左: 正后视剖面带 (x 收窄到铰链平面) ----
subplot(1, 2, 1); hold on;
for k = 17:23
    if k == 24, continue; end
    pk = fullfile(root, sprintf('cad/v1/cfd_geom_multi/body_%d.stl', k));
    if exist(pk, 'file')
        Pk = stlread(pk);
        patch('Faces', Pk.ConnectivityList, 'Vertices', Pk.Points, ...
            'FaceColor', [.5 .55 .7], 'FaceAlpha', 0.30, 'EdgeColor', 'none');
    end
end
for k = 1:4
    F = stlread(fullfile(root, sprintf('cad/v1/cfd_parallel/fin_%d.stl', k)));
    patch('Faces', F.ConnectivityList, 'Vertices', F.Points, ...
        'FaceColor', [.25 .85 .45], 'FaceAlpha', 0.85, 'EdgeColor', [.1 .3 .15], 'EdgeAlpha', 0.4);
    s = asm.control_surfaces(k);
    p = s.hinge_line(1, :); q = s.hinge_line(2, :);
    plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'm-', 'LineWidth', 3);
    plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'mo', 'MarkerFaceColor', 'm', 'MarkerSize', 5);
end
axis equal; grid on; view(-90, 0);
axis([-0.095 -0.080 -0.055 0.055 -0.055 0.055]);
title('后视剖面: 四舵 X 立 + 品红=双耳孔心连线 (端点=耳孔心)');
xlabel('x_B m'); ylabel('y_B m'); zlabel('z_B m');

% ---- 右: fin_1 侧后特写 ----
subplot(1, 2, 2); hold on;
for k = 17:23
    pk = fullfile(root, sprintf('cad/v1/cfd_geom_multi/body_%d.stl', k));
    if exist(pk, 'file')
        Pk = stlread(pk);
        patch('Faces', Pk.ConnectivityList, 'Vertices', Pk.Points, ...
            'FaceColor', [.6 .65 .8], 'FaceAlpha', 0.45, 'EdgeColor', [.45 .5 .6], 'EdgeAlpha', 0.25);
    end
end
F = stlread(fullfile(root, 'cad/v1/cfd_parallel/fin_1.stl'));
patch('Faces', F.ConnectivityList, 'Vertices', F.Points, ...
    'FaceColor', [.25 .85 .45], 'FaceAlpha', 0.8, 'EdgeColor', [.1 .3 .15], 'EdgeAlpha', 0.4);
s = asm.control_surfaces(1);
p = s.hinge_line(1, :); q = s.hinge_line(2, :);
plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'm-', 'LineWidth', 4);
plot3([p(1) q(1)], [p(2) q(2)], [p(3) q(3)], 'mo', 'MarkerFaceColor', 'm', 'MarkerSize', 8);
axis equal; grid on; view(160, 25);
axis([-0.105 -0.070 0.000 0.055 0.000 0.055]);
title('fin_1 特写: 品红端点落在双耳孔心 (r1.9/r1.15), body 销同轴');
xlabel('x_B m'); ylabel('y_B m'); zlabel('z_B m');

sgtitle('v4 真铰链轴验收: 双耳孔心连线 x=-87.6mm (v3 曾误用导引套筒轴, 平行偏移 1.45mm)');
out = fullfile(root, 'cad/v1/v4_rear_acceptance.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
end
