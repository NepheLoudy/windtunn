'use strict';
/* wt3d_core.js — 3D 基建层 (P2 拆分, 自 dashboard.html 内联块迁出)
   加载序: three.min.js → wt3d_core.js → wt3d_flow.js → wt3d_readout.js → HTML 内联装配块。
   依赖方向: core 不依赖 flow/readout 的加载期符号; 以下为运行时挂钩 (函数体延迟求值,
   调用发生在 loadData().then 异步之后, 加载序保证符号已存在):
     - aeroTick()        ← wt3d_flow.js   (rAF loop 每帧推进粒子/流光)
     - st()/draw2d()     ← dashboard.html (自检灯 DOM / 2D 降级画布)
     - window.__loadMesh ← dashboard.html 装配块 (mesh 拉取+PCA+fins, 内部再挂 readout.initAeroFX)
   暴露: T3 (场景状态句柄, flow/readout 经此取 scene/dart/resize), init3d(), window.WT_DEBUG。 */
let T3={ready:false,groups:[],ver:null};

/* ---------- 全局调试通道收敛 (P2): WT_DEBUG 字段 <-> 旧 window.__* 双向转发 ----------
   真源保持在 window.__* (旧代码读写路径零变化), WT_DEBUG 是收敛视图; alias 不断链。 */
window.WT_DEBUG={};
['cam','applyCam','loadMesh','applyFlow','renderOnce','aeroVisible','meshVer','pause_raf'].forEach(function(k){var g='__'+k;
  Object.defineProperty(window.WT_DEBUG,k,{configurable:true,get:function(){return window[g];},set:function(v){window[g]=v;}});});
Object.defineProperty(window.WT_DEBUG,'T3',{configurable:true,value:T3}); // 附加直查: 场景状态

const WT3D_TESTED=['128']; // P2: three 版本锁定白名单 (r128 = 本仓 three.min.js 实测版)

function init3d(){
  if(T3.started)return;T3.started=true;
  const holder=$('view3d');
  if(window.__three_fail||!window.THREE){
    st('st_gl','未用(2D)','warn');
    holder.innerHTML='<canvas id="c2d" width="520" height="380" style="width:100%"></canvas>';
    T3.d2=true;draw2d();return;
  }
  try{
    holder.style.position='relative'; // P2: contextlost 提示条的包含块 (canvas 布局不变)
    const renderer=new THREE.WebGLRenderer({antialias:true}); // 11-06 P0-5: preserveDrawingBuffer 无用途已删
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2)); // 高分屏清晰化 (上限 2 防 4K 过载)
    if(WT3D_TESTED.indexOf(''+THREE.REVISION)===-1){ // P2 版本锁校验: 未测版 warn 不阻断渲染
      st('st_gl','r'+THREE.REVISION+' (未测版)','warn');
      console.warn('[wt3d] three r'+THREE.REVISION+' 不在测试白名单 '+JSON.stringify(WT3D_TESTED)+' — 渲染继续, 视觉未验证');
    }else st('st_gl','OK','ok');
    renderer.setSize(520,400);renderer.setClearColor(0x0d1220); // 初始回退尺寸 — p5 未激活时 clientWidth=0, resize3d 在 tab 激活时修正
    holder.appendChild(renderer.domElement);
    renderer.domElement.style.touchAction='none'; // P2 触摸: 单指拖转/双指捏合不被浏览器手势截胡
    const scene=new THREE.Scene();
    // 11-06 P1-9 灯光: 环境光下调 + HemisphereLight 天/地亮度差 + 主光随来流 → 顶点色仍是主视觉, 灯只加明暗造型
    scene.add(new THREE.AmbientLight(0xffffff,.55));
    scene.add(new THREE.HemisphereLight(0x9db4e8,0x141a28,.5));
    const dl=new THREE.DirectionalLight(0xffffff,.7);dl.position.set(2,3,4);scene.add(dl);T3.keyLight=dl; // 主光: setFlow 时挪到上游上方 (随来流)
    const dl2=new THREE.DirectionalLight(0xffffff,.35);dl2.position.set(-3,-2,-4);scene.add(dl2); // 对向补光: 消灭背光黑舵
    const cam=new THREE.PerspectiveCamera(40,520/400,.01,10);
    T3.resize=function(){ // 11-06 P0-4: canvas 尺寸自适应 (原硬编码 520×400; 防御: >0 才应用)
      const w=holder.clientWidth,h=holder.clientHeight;
      if(w>0&&h>0){renderer.setSize(w,h);cam.aspect=w/h;cam.updateProjectionMatrix();}
    };
    const camSt={theta:2.35,phi:.32,R:.42,drag:false,px:0,py:0};
    function applyCam(){cam.position.set(
      camSt.R*Math.cos(camSt.phi)*Math.cos(camSt.theta),
      camSt.R*Math.sin(camSt.phi),
      camSt.R*Math.cos(camSt.phi)*Math.sin(camSt.theta));
      cam.lookAt(0,0,0);}
    applyCam();
    const grid=new THREE.GridHelper(.3,15,0x223055,0x1a2440);grid.position.y=-.07;scene.add(grid);
    const flow=new THREE.Group();
    const FL=.12;
    const shaft=new THREE.Mesh(new THREE.CylinderGeometry(.0025,.0025,FL),new THREE.MeshBasicMaterial({color:0x38bdc8}));
    shaft.rotation.z=Math.PI/2;shaft.position.x=FL/2;flow.add(shaft);
    const head=new THREE.Mesh(new THREE.ConeGeometry(.006,.02),new THREE.MeshBasicMaterial({color:0x38bdc8}));
    head.rotation.z=-Math.PI/2;head.position.x=FL-.008;flow.add(head);
    scene.add(flow);
    function setFlow(alphaDeg,betaDeg){
      const A=alphaDeg*Math.PI/180,B2=betaDeg*Math.PI/180;
      const U=new THREE.Vector3(-Math.cos(A)*Math.cos(B2),-Math.sin(B2),-Math.sin(A)*Math.cos(B2));
      flow.position.copy(U.clone().multiplyScalar(-.17));
      flow.quaternion.setFromUnitVectors(new THREE.Vector3(1,0,0),U.normalize());
      if(T3.keyLight)T3.keyLight.position.copy(U).multiplyScalar(-1.8).add(new THREE.Vector3(.3,1.8,.6)); // 主光挪上游上方 (随来流, 弱造型)
    }
    setFlow(-15,0);window.__applyFlow=setFlow;  // 默认 α=-15 (与滑块初值一致, a-15_b0 v3 精确匹配)
    const dart=new THREE.Group();scene.add(dart);
    T3.dart=dart;T3.scene=scene;
    // mesh 一次性加载 (版本变了由 loadData 触发整页刷新), 失败可重试 — 10-31 UI 迭代:
    // 旧版把 13.9MB mesh fetch 放在 90s 轮询里且无 catch, 静默失败=场景空转 (曼波: "3D 没有显示")
    // P2 拆分: __loadMesh 本体在 dashboard.html 装配块 (其内部依赖 readout.initAeroFX / UI 的 applyDeltas)
    window.__loadMesh();
    /* ---------- P2 触摸补全: active pointers Map + 双指捏合 + pointercancel + 惯性阻尼 ---------- */
    let lastInteract=0; // 11-06 P1-10a: 拖拽/滚轮后暂停自转 8s 再恢复 (时间戳比较)
    const ptrs=new Map();let pinchD=0,thetaV=0,phiV=0,lastMoveT=0;
    const pdist=()=>{const it=[...ptrs.values()];return Math.hypot(it[0].x-it[1].x,it[0].y-it[1].y);};
    renderer.domElement.addEventListener('pointerdown',e=>{
      ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(ptrs.size===1){camSt.drag=true;thetaV=phiV=0;camSt.px=e.clientX;camSt.py=e.clientY;}
      else if(ptrs.size===2){camSt.drag=false;pinchD=pdist();} // 二指落下转捏合, 退出拖转
      lastInteract=performance.now();});
    const endPtr=e=>{ptrs.delete(e.pointerId);if(ptrs.size<2)pinchD=0;
      if(ptrs.size===0){camSt.drag=false;if(performance.now()-lastMoveT>120)thetaV=phiV=0;}}; // 停顿后松手不滑行
    window.addEventListener('pointerup',endPtr);
    window.addEventListener('pointercancel',endPtr); // P2: 触摸中断清 drag 状态 (防"卡拖拽")
    window.addEventListener('pointermove',e=>{
      if(ptrs.has(e.pointerId))ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(ptrs.size>=2){ // 双指捏合缩放: 张开拉近/并拢拉远 (与滚轮同 clamp .2-.9)
        const d=pdist();
        if(pinchD>0){camSt.R=Math.max(.2,Math.min(.9,camSt.R-(d-pinchD)*.0005));applyCam();lastInteract=performance.now();}
        pinchD=d;return;}
      if(!camSt.drag)return;lastInteract=performance.now();lastMoveT=performance.now();
      // 拖向=视觉跟随 (曼波 11-01: 原方向反了, 两轴符号翻转; 11-04: 垂直轴(phi)再翻回 —
      // phi-=dy 时拖下变仰视, 与"拖下→看俯视"相反; theta 轴正确保持不变)
      camSt.theta+=(e.clientX-camSt.px)*.01;camSt.phi=Math.max(-1.4,Math.min(1.4,camSt.phi+(e.clientY-camSt.py)*.008));
      thetaV=(e.clientX-camSt.px)*.01;phiV=(e.clientY-camSt.py)*.008; // 速度采样 (惯性用, 与拖转同系数)
      camSt.px=e.clientX;camSt.py=e.clientY;applyCam();});
    window.__cam=camSt;window.__applyCam=applyCam; // 11-06: 暴露给 UI 状态恢复 (reload 后回放相机角度, 只动相机不碰 setFlow)
    renderer.domElement.addEventListener('wheel',e=>{e.preventDefault();lastInteract=performance.now();
      camSt.R=Math.max(.2,Math.min(.9,camSt.R+e.deltaY*.0004));applyCam();},{passive:false});
    let rszT=null; // 11-06 P0-4c: 窗口尺寸变化 → resize3d (防抖 200ms)
    window.addEventListener('resize',()=>{clearTimeout(rszT);rszT=setTimeout(()=>T3.resize&&T3.resize(),200);});
    if(typeof ResizeObserver==='function'){ // P2 追加 scope-4: 监听 canvas 父容器尺寸 — 根治 sessionStorage
      // 恢复/tab 切换的布局时序抢跑 (reload 恢复 tab 后 T3.resize() 在布局稳定前执行, canvas 386px 应 979);
      // 布局稳定瞬间观察器即触发 (T3.resize 内含 >0 守卫, 幂等 — 与 window resize 双保险)
      // 11-08 二次审查实修: 匿名实例初始同步触发后即被 GC (实测真布局变化不再回调,
      // canvas 钉死 989 while holder 913) — 必须挂 T3 长命引用保活
      T3.ro=new ResizeObserver(()=>{if(T3.resize)T3.resize();});
      T3.ro.observe(holder);
    }
    /* ---------- P2: WebGL 上下文丢失/恢复 — lost 显示提示条, restored 自动恢复渲染 ---------- */
    T3.ctxLost=false;
    renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();T3.ctxLost=true;
      const bn=document.createElement('div');bn.id='wt_ctxlost';
      bn.textContent='WebGL 上下文丢失 — 正在等待系统恢复 (恢复后自动继续渲染)…';
      bn.style.cssText='position:absolute;left:0;top:0;right:0;padding:8px;background:rgba(224,85,85,.92);color:#fff;font-size:13px;text-align:center;z-index:5';
      holder.appendChild(bn);},false);
    renderer.domElement.addEventListener('webglcontextrestored',()=>{T3.ctxLost=false;
      const bn=holder.querySelector('#wt_ctxlost');if(bn)holder.removeChild(bn);},false);
    (function loop(){requestAnimationFrame(loop);
      if(window.__pause_raf||T3.ctxLost)return;
      if(!camSt.drag&&!T3.d2){
        if(Math.abs(thetaV)>1e-4||Math.abs(phiV)>1e-4){ // P2 惯性: 甩动后按速度衰减滑行 (0.85/帧)
          camSt.theta+=thetaV;camSt.phi=Math.max(-1.4,Math.min(1.4,camSt.phi+phiV));
          thetaV*=.85;phiV*=.85;applyCam();
        }else if(performance.now()-lastInteract>8000){camSt.theta+=.0016;applyCam();} // 空闲自动缓旋 (交互后 8s 内不抢镜)
      }
      aeroTick(); // 受风渲染: 粒子推进 (p5 不可见时内部自跳过)
      renderer.render(scene,cam)})();
    document.addEventListener('visibilitychange',()=>{window.__pause_raf=document.hidden;});
    window.__renderOnce=()=>{renderer.render(scene,cam);}; // 调试口: 窗口遮挡 rAF 冻结时手动单帧 (11-04)
  }catch(e){st('st_gl','err: '+String(e).slice(0,40),'bad');T3.d2=true;holder.innerHTML='<canvas id="c2d" width="520" height="380" style="width:100%"></canvas>';draw2d();}
}
