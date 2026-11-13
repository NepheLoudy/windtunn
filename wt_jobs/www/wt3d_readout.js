'use strict';
/* wt3d_readout.js — 读出层 (P2 拆分, 自 dashboard.html 内联块迁出)
   加载序: three.min.js → wt3d_core.js → wt3d_flow.js → 本文件 → HTML 内联装配块。
   依赖方向: readout → core (T3.dart) + flow (AERO/aeroJet/jetColor/flowVel/initFlowParticles/
   loadPoseFor/fetchAeroBlue/tNow0/rebuildStreamlines) — 双向依赖均在加载序上。
   暴露: aeroBilinear / initAeroFX / paintSurfaceSpeed / updateAero (全局函数, HTML 装配块与
   flow 的 loadPoseFor·fetchAeroBlue 在运行时回调)。 */
function aeroBilinear(a,b){
  // 双线性: α 最近两剖面 + β 最近两行; 蓝表 δ=0。
  // α 超出已扫域: 回退一档线性外推 (攻角线性区外推物理合理, RL 侧 lookup_aero 另有
  //   严格 clamp+warning 兜底) — 11-04 修: 原版 i 推到末档 a1===a0 → wa=0 钉死边缘值,
  //   α=+8° 显示 α=-2.5° 的 CL (正攻角全部错值)。
  // β 侧向: 大侧滑外推危险 (CY sin 径), 保持 clamp。
  const rs=AERO.rows;if(!rs||!rs.length)return null;
  const alphas=[...new Set(rs.map(r=>r.a))].sort((x,y)=>x-y);
  const n=alphas.length;
  let i=0;while(i<n-1&&a>alphas[i+1])i++;
  if(i>=n-1)i=n-2; if(i<0)i=0;                 // 域外→用边缘两档线性外推
  const a0=alphas[i],a1=alphas[i+1];
  const wa=a1===a0?0:(a-a0)/(a1-a0);
  const pick=av=>{const sub=rs.filter(r=>r.a===av).sort((x,y)=>x.b-y.b);
    if(!sub.length)return null;
    let j=0;while(j<sub.length-1&&b>sub[j+1].b)j++;
    const r0=sub[j],r1=sub[Math.min(j+1,sub.length-1)];
    const wb=r1.b===r0.b?0:(b-r0.b)/(r1.b-r0.b);
    const out={};for(const k of ['CL','CD','Cm','CY','Cl','Cn'])out[k]=r0[k]+(r1[k]-r0[k])*wb;
    return out;};
  const p0=pick(a0),p1=a1===a0?p0:pick(a1);
  if(!p0||!p1)return null;
  const out={};for(const k of ['CL','CD','Cm','CY','Cl','Cn'])out[k]=p0[k]+(p1[k]-p0[k])*wa;
  const outside=a<alphas[0]||a>alphas[n-1];
  out.mode=outside?'域外外推':(a===a0&&rs.some(r=>r.a===a&&r.b===b)?'表内点':'插值点');
  return out;
}
function initAeroFX(scene,dart){
  // P2 追加 scope-1: mesh 重试链防重复叠加 — initAeroFX 会随 __loadMesh 重试重跑,
  // 先显式清理旧三箭头 (line/cone geometry+material+label 纹理) 与旧粒子层 (segs),
  // 不能用 started 守卫 (重试确需重跑)。aeroTick 对 AERO.flow/arrows 均有空判, 清理窗口安全。
  if(AERO.arrows){for(const k of ['L','D','Y']){const a=AERO.arrows[k];
    if(!a)continue;
    scene.remove(a);
    if(a.line){a.line.geometry&&a.line.geometry.dispose();a.line.material&&a.line.material.dispose();}
    if(a.cone){a.cone.geometry&&a.cone.geometry.dispose();a.cone.material&&a.cone.material.dispose();}
    if(a.label){a.label.material.map&&a.label.material.map.dispose();a.label.material.dispose();}
  }}
  AERO.arrows=null;
  if(AERO.flow&&AERO.flow.segs){scene.remove(AERO.flow.segs);
    AERO.flow.segs.geometry.dispose();AERO.flow.segs.material.dispose();}
  AERO.flow=null;
  // ① 流线系统: 起点上游客盘 → RK2 追迹 → LineSegments (顶点色=局部速度 jet)
  AERO.scene=scene; AERO.orbit={pts:null,t:0};
  // ② 力矢量三箭头 (起点沿方向外移出机身防遮挡; depthTest 关 — X 光穿透, 机身永不见)
  //   11-06 P1-8c: 每箭头带字母标签 sprite (L/D/Y) — 远看可辨识, 数值仍看 readout
  const mkLabel=(txt,col)=>{
    const cv=document.createElement('canvas');cv.width=64;cv.height=64;
    const g2=cv.getContext('2d');g2.font='bold 42px Consolas,monospace';g2.textAlign='center';g2.textBaseline='middle';
    g2.fillStyle=col;g2.shadowColor=col;g2.shadowBlur=10;g2.fillText(txt,32,34);
    const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv),depthTest:false,transparent:true}));
    sp.scale.set(.036,.036,1);sp.renderOrder=996;return sp;};
  const mkArr=(c,txt)=>{const a=new THREE.ArrowHelper(new THREE.Vector3(0,1,0),new THREE.Vector3(0,0,0),.1,c,.045,.024);
    a.visible=false;a.line.material.depthTest=false;a.cone.material.depthTest=false;
    // 11-06 P4 修齐: renderOrder 不从父对象继承 — line/cone 逐子对象设 997 且入透明队列 (opacity 1 视觉不变),
    // 保证画在流线 Tube (透明, renderOrder 5/10) 与机身之后 — 任意角度 X 光穿透可见
    // (原仅靠不透明队列内材质 id 创建序排后, 是隐性顺序; 近体管 alpha .85 会遮箭头)
    a.line.material.transparent=a.cone.material.transparent=true;
    a.line.renderOrder=a.cone.renderOrder=997;
    a.label=mkLabel(txt,'#'+c.toString(16).padStart(6,'0'));a.label.position.set(0,.13,0);a.add(a.label);
    scene.add(a);return a;};
  AERO.arrows={L:mkArr(0x3ecf7a,'L'),D:mkArr(0xff6655,'D'),Y:mkArr(0xffd23e,'Y')};
  initFlowParticles(scene); // ⑤ 来流粒子背景层 (势流场采样, 独立于流线数据源 — 两模式都在)
  {const A=-15*Math.PI/180;AERO.U=new THREE.Vector3(-Math.cos(A),0,-Math.sin(A));} // 默认来流 (首个 updateAero 前粒子可动)
  fetch('streamlines_index.json?_='+Date.now()).then(r=>r.ok?r.json():Promise.reject(r.status))
    .then(idx=>{
      AERO.poseIdx=idx;                       // {poses:[{file,alpha,beta,V}...]}
      const ins0=document.querySelectorAll('#sliders input[type=range]');
      return loadPoseFor(+ins0[4].value, +ins0[5].value);
    })
    .catch(e=>{ // index 失败才回退单姿态 (pose fetch 慢≠失败 — 15MB 需 >30s, 不抢跑)
      if(String(e).includes('no-pose'))return;   // 无姿态索引时才走回退
      console.warn('pose fetch slow/fail, keep current:', String(e).slice(0,60));
    });
  fetchAeroBlue(); // 蓝表首拉 (此后 30s 轮询由顶部 setInterval 驱动)
}
function paintSurfaceSpeed(U){ // ③ 表面速度色阶 (P2 追加 scope-3: paintPressure 更名 — 函数体取的是速度; jet: 驻点青→侧面红; 节流 250ms)
  if(AERO.real&&AERO.real.surf&&AERO.surfReal)return; // 11-06 P0-1: 真实 CFD 表面色已挂 → 势流近似色不得覆盖 (回退色只在无真实场时用)
  const now=performance.now();if(now-AERO.lastPaint<250)return;AERO.lastPaint=now;
  const mesh=T3.dart&&T3.dart.children.find(c=>c.isMesh);if(!mesh||!mesh.geometry)return;
  const g=mesh.geometry,ps=g.attributes.position,cnt=ps.count;
  if(!g.attributes.color)g.setAttribute('color',new THREE.BufferAttribute(new Float32Array(cnt*3),3));
  const col=g.attributes.color.array;
  const out={wakeAmp:0,wakeDir:{x:0,y:0,z:0},x:0,y:0,z:0},tN=tNow0();
  for(let i=0;i<cnt;i++){
    const sp=flowVel(ps.getX(i),ps.getY(i),ps.getZ(i),U,tN,out);
    const c=jetColor(Math.max(0,Math.min(1,(sp-.45)/.85)));
    col[i*3]=c[0];col[i*3+1]=c[1];col[i*3+2]=c[2];
  }
  g.attributes.color.needsUpdate=true;
  if(!mesh.material.vertexColors){mesh.material.vertexColors=true;mesh.material.color.set(0xffffff);mesh.material.needsUpdate=true;}
}
function updateAero(){ // α/β 滑块与 aero_blue 就绪时统一入口
  const ai=document.querySelector('#sliders input[step="1"][min="-15"]');
  if(!ai)return;
  const ins=document.querySelectorAll('#sliders input[type=range]');
  const a=+ins[4].value,b=+ins[5].value; // 第 5/6 个滑块=α/β (前 4 是 δ)
  const A=a*Math.PI/180,B2=b*Math.PI/180;
  const U=new THREE.Vector3(-Math.cos(A)*Math.cos(B2),-Math.sin(B2),-Math.sin(A)*Math.cos(B2));
  AERO.U=U; // 来流方向缓存 (粒子层 aeroTick 采样用)
  if(window.__applyFlow)window.__applyFlow(a,b);
  paintSurfaceSpeed(U);
  { // 流线重建: 真实场模式每次都走 (内含首建守卫+姿态旋转, 开销小); 势流模式 400ms 节流
    const now=performance.now();
    if(AERO.real || (AERO.scene&&now-(AERO.lastRebuild||0)>400)){AERO.lastRebuild=now; // 11-06: scene 未建 (UI 恢复早期 dispatch input) 不进势流重建
      try{rebuildStreamlines(U,tNow0());}catch(e){AERO.slErr=String(e).slice(0,200);console.error('rebuild ERR:',e);}}
  }
  const c=aeroBilinear(a,b);
  const el=$('aeroread');
  if(!AERO.rows){return;}
  if(!c){el.textContent='气动查表: 表空';return;}
  // ④ 力矢量: 稳定轴基 (drag=+U 方向, lift=场景上向在垂直来流面投影, side=lift×drag)
  //   坑(11-04): 标量×向量必须 addScaledVector — `n*vec` 在 JS 是 number×object=NaN,
  //   曾致 L/Y 箭头 position=NaN 消失 (D 幸存因不经过此式)
  const drag=U.clone().normalize();
  const up0=new THREE.Vector3(0,1,0);
  const lift=up0.clone().addScaledVector(drag,-up0.dot(drag)).normalize();
  const side=new THREE.Vector3().crossVectors(lift,drag);
  const L=.12;
  if(AERO.arrows){ // 11-06 顺手修: mesh 未加载 (initAeroFX 未跑) 时滑块联动静默跳过力矢量
  const set=(arr,key,dir)=>{const v=c[key],ar=AERO.arrows[key==='CL'?'L':key==='CD'?'D':'Y'];
    // 显示阈值 0.02 (11-04 曼波指认: β=0 时 CY 网格偏置 ~0.01-0.02 被画成明显侧力箭头 —
    //   A3 锚同源: |CY(β=0)|<0.03 = 网格不完全对称的已知偏置, 非真实侧力, 不渲染);
    //   长度超线性压扁: |v|^0.7 — 小值区不让箭头撑出误导比例
    const av=Math.abs(v);
    ar.visible=av>0.02;
    const len=.06+Math.pow(Math.min(av,1.5),0.7)*.15, sgn=v>=0?1:-1; // 11-06 P1-8c: 下限抬到 .06 + 与 |F| 成比例
    // 锥头随长度比例化 (11-06 验收调参: 固定 .045 锥头对短箭头占 35% 显笨重 — 封顶 30%)
    ar.setLength(len,Math.min(.038,len*.3),Math.min(.02,len*.16));
    // 11-06 P1-8a/8b 物理修正: 箭头=力作用在弹体上的方向 (删 11-05 negate — 上表面吸力=CL 正沿 -z_s 即向上,
    //   CL>0 升力箭头必须朝上, 与 readout 自洽); 尾部放力方向侧表面外 0.135 (弹体斜投影半径 ~0.127,
    //   原 0.11 时 CD 尖端 x≈+0.06 落在 ±0.115 体内) — 全方向不穿体
    ar.position.copy(dir).multiplyScalar(sgn*.135);
    ar.setDirection(dir.clone().multiplyScalar(sgn));
    if(ar.label)ar.label.position.set(0,len+.03,0);};
  set(c,'CL',lift);set(c,'CD',drag);set(c,'CY',side);   // 稳定轴基: lift=up 在垂流面投影, side=lift×drag
  }
  el.innerHTML='V∈[20,25] (跨V&lt;1%) α='+a+'° β='+b+'° → <b style="color:#3ecf7a">CL='+c.CL.toFixed(3)+'</b> <b style="color:#e05555">CD='+c.CD.toFixed(3)+'</b> <b style="color:#e8b13e">CY='+c.CY.toFixed(3)+'</b> · Cm='+c.Cm.toFixed(3)+' Cl='+c.Cl.toFixed(3)+' Cn='+c.Cn.toFixed(3)+' · CY 含网格偏置(β=0 时 |CY|&lt;0.03 非真实侧力) · <b>'+c.mode+'</b> · <b style="color:#5ad0e0">流线源: '+(AERO.real?(AERO.hasLayer()?(AERO.poseDist>1.26?'⚠ 姿态差 '+AERO.poseDist.toFixed(1)+'° (显示 '+AERO.real.alpha+'° 姿态, 滑块姿态待收割)':'真实 CFD 场 '+AERO.real.case):'⚠ 均匀场(待收敛) '+AERO.real.case):'势流近似')+'</b> (δ 查表未含, 蓝表 δ=0)';
}
