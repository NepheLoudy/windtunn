function render_axes_arbitration
% 转轴仲裁图 2026-10-30: fin_1+fin_4 舵根特写, 三候选轴叠加
% A(青)=assembly 现值  B(绿)=STL-Hough 独立识别  C(红虚)=旧 find_hinges
root = fileparts(mfilename('fullpath'));
f1 = stlread(fullfile(root,'cad/v1/cfd_parallel/fin_1.stl'));
asm = jsondecode(fileread(fullfile(root,'cad/v1/cfd_parallel/airframe_assembly.json')));
hough = jsondecode(fileread(fullfile(root,'bore_axis_independent.json')));
olds = jsondecode(fileread(fullfile(root,'cad/v1/hinges.json')));

fig = figure('Visible','off','Position',[30 30 1500 700]);

% ---- 左: 全局视角 (看清 fin_1 位置) ----
subplot(1,2,1); hold on;
patch('Faces',f1.ConnectivityList,'Vertices',f1.Points,...
    'FaceColor',[.35 .75 .45],'FaceAlpha',0.5,'EdgeColor',[.3 .35 .4],'EdgeAlpha',0.3);
axis equal; grid on; view(120,18);
axis([-0.13 -0.05 -0.01 0.06 -0.01 0.06]);
title('fin_1 全局 (青=现轴 绿=Hough 红=旧)');

% ---- 右: 舵根特写 (三轴) ----
subplot(1,2,2); hold on;
patch('Faces',f1.ConnectivityList,'Vertices',f1.Points,...
    'FaceColor',[.35 .75 .45],'FaceAlpha',0.45,'EdgeColor',[.3 .35 .4],'EdgeAlpha',0.35);
L = 0.014;
% A: assembly 现值 (hinge_line 两端点)
s1 = asm.control_surfaces(1);
pA = [s1.hinge_line(1,:); s1.hinge_line(2,:)];
plot3(pA(:,1),pA(:,2),pA(:,3),'c-','LineWidth',4);
% B: Hough 独立识别 (center_B + axis 方向, fin_1 轴向)
h1 = hough.fin_1;
cB = h1.center_B;
aB = [0, 1/sqrt(2), 1/sqrt(2)];
plot3(cB(1)+[-L L]*aB(1), cB(2)+[-L L]*aB(2), cB(3)+[-L L]*aB(3),'g-','LineWidth',3);
plot3(cB(1),cB(2),cB(3),'go','MarkerFaceColor','g','MarkerSize',5);
% C: 旧 find_hinges (part 24, STEP 系 mm → B)
o1 = olds(1);
c0 = [o1.center_mm(3)-105.5, o1.center_mm(2)-0.2, o1.center_mm(1)+0.1]/1000;
a0 = [o1.axis(3), o1.axis(2), o1.axis(1)]; a0 = a0/norm(a0);
plot3(c0(1)+[-L L]*a0(1), c0(2)+[-L L]*a0(2), c0(3)+[-L L]*a0(3),'r--','LineWidth',2.5);
axis equal; grid on; view(-135,25);
axis([-0.095 -0.078 0.005 0.045 0.005 0.045]);
title('舵根特写: 青=现assembly轴 绿=Hough独立识别 红虚=旧轴');
xlabel('x_B [m]'); ylabel('y_B [m]'); zlabel('z_B [m]');

sgtitle('转轴仲裁 (fin_1): 哪条线穿过舵根圆柱孔中心?');
out = fullfile(root,'cad/v1/axes_arbitration.png');
exportgraphics(fig, out, 'Resolution', 140);
fprintf('saved %s\n', out);
