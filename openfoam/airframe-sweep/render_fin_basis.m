function render_fin_basis
% 尾部舵区特写: 红四舵=旧装配角(T0/T1基准) vs 蓝四舵=平行基准(δ=0)
root = fileparts(mfilename('fullpath'));
body = stlread(fullfile(root,'cad/v1/cfd/body.stl'));

fig = figure('Visible','off','Position',[30 30 1700 850]);
for vi = 1:3
    subplot(1,3,vi); hold on;
    patch('Faces',body.ConnectivityList,'Vertices',body.Points,...
        'FaceColor',[.75 .75 .78],'FaceAlpha',0.35,'EdgeColor',[.5 .5 .5],...
        'EdgeAlpha',0.25,'LineWidth',0.2);
    for k = 1:4
        fOld = stlread(fullfile(root,sprintf('cad/v1/cfd/fin_%d.stl',k)));
        fPar = stlread(fullfile(root,sprintf('cad/v1/cfd_parallel/fin_%d.stl',k)));
        patch('Faces',fPar.ConnectivityList,'Vertices',fPar.Points,...
            'FaceColor',[.2 .35 .95],'FaceAlpha',0.55,'EdgeColor','none');
        patch('Faces',fOld.ConnectivityList,'Vertices',fOld.Points,...
            'FaceColor',[.9 .1 .1],'FaceAlpha',0.85,'EdgeColor','k','LineWidth',0.2);
    end
    axis equal; grid on; axis([-0.13 -0.06 -0.07 0.07 -0.07 0.07]);
    switch vi
        case 1, view(35,25); title('iso 尾部特写');
        case 2, view(0,0);   title('侧视 (x-y, z 向上画)'); xlabel('x [m]'); ylabel('y [m]');
        case 3, view(90,0);  title('后视 (沿 -x 看向头部)'); axis([-0.13 -0.06 -0.07 0.07 -0.09 0.09]);
    end
end
sgtitle('尾部四舵: 红=旧装配角(入T0/T1表)  蓝=平行基准(曼波定 δ=0,画在下层)  灰=body');
out = fullfile(root,'cad/v1/fin_basis_compare.png');
exportgraphics(fig, out, 'Resolution', 130);
fprintf('saved %s\n', out);
