function render_part24_study
% part_24 舵件结构研究 — 三视图 + 根部特写 (搞清"空心圆柱"到底长什么样)
root = fileparts(mfilename('fullpath'));
P = stlread(fullfile(root,'cad/v1/parts/part_24.stl'));
C = P.Points;
lo = min(C,[],1); hi = max(C,[],1);
fprintf('part_24 bbox mm: [%.1f %.1f] [%.1f %.1f] [%.1f %.1f]\n', lo, hi);

fig = figure('Visible','off','Position',[30 30 1800 900]);
views = {0,-90,'正视 (沿 -z)'; 0,90,'侧视 A'; 90,0,'侧视 B (沿 -x)'; 30,30,'iso'};
for v = 1:4
    subplot(1,4,v); hold on;
    patch('Faces',P.ConnectivityList,'Vertices',P.Points,...
        'FaceColor',[.5 .8 .6],'FaceAlpha',0.9,'EdgeColor',[.2 .3 .25],'EdgeAlpha',0.25);
    axis equal off; camlight; lighting gouraud;
    view(views{v,2},views{v,1});
    title(views{v,3});
end
% bbox 标注
sgtitle(sprintf('part_24 舵件 (%.0f×%.0f×%.0f mm) — 结构研究', hi(1)-lo(1), hi(2)-lo(2), hi(3)-lo(3)));
out = fullfile(root,'cad/v1/part24_study.png');
exportgraphics(fig, out, 'Resolution', 130);
fprintf('saved %s\n', out);
