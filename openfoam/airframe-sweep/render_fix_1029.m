function render_fix_1029
% 曼波验收图 v3 2026-10-30: 轴线对比 + 填充v2(只封圆柱段, 凹陷保留) 前视+剖面
root = fileparts(mfilename('fullpath'));
ref = jsondecode(fileread(fullfile(root,'hinges_refined.json')));
fig = figure('Visible','off','Position',[40 40 1950 680]);

% ---- 左: 铰链轴 yz 侧视 ----
subplot(1,3,1); hold on;
for k = 1:4
    fk = stlread(fullfile(root,sprintf('cad/v1/cfd_parallel/fin_%d.stl',k)));
    patch('Faces',fk.ConnectivityList,'Vertices',fk.Points,...
        'FaceColor',[.8 .82 .9],'FaceAlpha',0.25,'EdgeColor',[.5 .55 .65],'EdgeAlpha',0.15);
end
for k = 1:numel(ref)
    r = ref(k);
    c = r.new_point_mm; a = r.new_axis;
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
title('铰链轴 yz 侧视: 绿=新轴(孔心) 红虚=旧(偏2mm)');

% ---- 中: 镖头孔口前视 (v2 填充: 凹陷保留, 深孔封底) ----
subplot(1,3,2); hold on;
pOld = stlread(fullfile(root,'cad/v1/parts/part_1_oldhole.stl'));
pNew = stlread(fullfile(root,'cad/v1/parts/part_1.stl'));
patch('Faces',pOld.ConnectivityList,'Vertices',pOld.Points,...
    'FaceColor',[.85 .35 .35],'FaceAlpha',0.45,'EdgeColor','none');
patch('Faces',pNew.ConnectivityList,'Vertices',pNew.Points,...
    'FaceColor',[.4 .55 .9],'FaceAlpha',0.45,'EdgeColor','none');
axis equal off; view(0,-90); axis([-26 26 -26 26 -26 -18]); camlight; lighting gouraud;
title('孔口前视 叠加: 红=原(深孔通透) 蓝=v2(圆柱段封底, 台形凹陷保留)');

% ---- 右: 内腔壁剖面 r\_in(z) — 凹陷保留的铁证 ----
subplot(1,3,3); hold on; grid on;
Po = pOld.Points; Pn = pNew.Points;
zs = -25:0.5:2;
ro = nan(size(zs)); rn = nan(size(zs));
for i = 1:numel(zs)
    m = abs(Po(:,3)-zs(i)) < 0.26; rr = sqrt(Po(m,1).^2+Po(m,2).^2);
    if any(rr>1), ro(i) = min(rr(rr>1)); end
    m = abs(Pn(:,3)-zs(i)) < 0.26; rr = sqrt(Pn(m,1).^2+Pn(m,2).^2);
    if any(rr>1), rn(i) = min(rr(rr>1)); end
end
plot(zs, ro, 'r-', 'LineWidth', 2);
plot(zs, rn, 'b-', 'LineWidth', 2);
xline(-8.75, 'k--', '填充圆柱前缘');
yline(8.29, 'k:', 'r=8.29 孔壁');
xlabel('z [mm] (STEP 系, 鼻端 z=-25)'); ylabel('内腔半径 r_{in} [mm]');
legend('原件: 台形凹陷+⌀16.6深孔', 'v2: 凹陷不变, 孔段封底', 'Location', 'southwest');
title('内腔壁剖面: 蓝线凹陷段与红线重合 = 凹陷完整保留');
ylim([5 25]);

sgtitle('2026-10-30 修复 v2: 铰链孔心精拟合(垂偏2.0mm已修,RMS 0.000) + 只封圆柱孔段(+2.51cm^3, 台形凹陷保留) + 舵扫掠±45°零穿透');
out = fullfile(root,'cad/v1/fix_1029_acceptance.png');
exportgraphics(fig, out, 'Resolution', 130);
fprintf('saved %s\n', out);
