'use strict';
/* wt3d_flow.js — 流场数据源与粒子层 (P2 拆分, 自 dashboard.html 内联块迁出)
   加载序: three.min.js → wt3d_core.js → 本文件 → wt3d_readout.js → HTML 内联装配块。
   依赖方向: flow → core (T3.scene/T3.dart 场景句柄, 加载序保证)。
   运行时反挂 (函数体延迟求值, 非加载期依赖; 调用发生在用户交互/轮询回调, 彼时 readout/HTML 已载):
     - updateAero() ← wt3d_readout.js (loadPoseFor/fetchAeroBlue 数据落地后刷新读出/箭头/流线)
     - $(id)        ← dashboard.html   (fetchAeroBlue 降级文案) */
/* ---------- 飞镖工况动态渲染 (11-04, 曼波: 风洞线不做但飞镖工况要) ----------
   组件: ①来流粒子场(绕流偏转示意) ②气动力三箭头(查 T0 蓝表, 箭头本体在 readout) ③表面速度着色(readout)
   ④系数读出行(readout)。数据: aero_blue.json (J1 每 2min 同步蓝表), (α,β) 双线性查表,
   V 维忽略 (跨 V <1% 实测)。舵偏 δ 只转几何, 查表未含 (蓝表 δ=0)。 */
const AERO={rows:null,parts:null,arrows:null,lastPaint:0,blueTag:null,blueSkip:0,U:null,flow:null};
AERO.pickPose=function(a,b){ // 姿态流线选择 — 11-06 终版: 【最近可用收敛姿态 + 徽标标姿态差】
  // 滑块任意角度都有流线可看 (修"调整角度渲染消失"), 显示的是最近已收敛姿态的场;
  // 姿态差 >1.26°(半档) 时 readout 徽标明示 "姿态差 x° (显示 α=a° 姿态, 滑块姿态待收割)" — 不冒充精确。
  // 收割 daemon 随引擎自动补齐姿态覆盖, 覆盖到位后徽标自动回到 "真实 CFD 场"。
  if(!this.poseIdx||!this.poseIdx.poses||!this.poseIdx.poses.length)return null;
  let best=null,bd=1e9;
  for(const p of this.poseIdx.poses){
    // v3 优先: 非 v3 (b11 代贴体段速度失真+尾锥跳离) 加 20 平方度惩罚 (~4.5° 等效) —
    // 姿态精度让位数据品质 (2.5° 内必有 v3 时优先 v3)
    const d=(p.alpha-a)*(p.alpha-a)+(p.beta-b)*(p.beta-b)*0.5+(p.v3?0:20);
    if(d<bd){bd=d;best=p;}
  }
  this.poseDist=Math.sqrt(bd);
  return best;   // 最近可用姿态 (readout 徽标标姿态差; 收敛场覆盖随收割 daemon 扩展)
};
AERO.hasLayer=function(){ // 当前 real 是否收敛场版 (v 有分层) — 均匀场版近体 v 全 20
  // 11-06 修: 旧版只扫中间一条线 → a0_b0 等对称姿态中间线恰在 18~23 带内假阴性"均匀场"。
  // 改为加载时对全部流线近体点 (r<0.12) 全扫一次并缓存 — 减速层 v<15 或加速 v>27 即真实梯度。
  if(!this.real||!this.real.lines)return false;
  if(this.realLayered===undefined){
    let lay=false;
    for(const ln of this.real.lines){
      for(const p of ln){
        if(p[1]*p[1]+p[2]*p[2]<0.0144 && (p[3]<15||p[3]>27)){lay=true;break;}
      }
      if(lay)break;
    }
    this.realLayered=lay;
  }
  return this.realLayered;
};
/* ---------- 势流解析场 (11-04 升级: 曼波要贴体流线效果 — 参考成熟 CFD 后处理) ----------
   均匀来流 + 沿弹轴源分布(细长体排挤, 椭球 R(x)) + 下游尾迹亏损 + 尾涡摆动。
   纯解析可积分 — 流线=RK2 追迹, 色标=局部速度 jet 色表, 无需 CFD 场数据。 */
const AEROBODY={x0:-.115,x1:.115,R:.057,NSEG:24};
const sstep=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
function bodyR(x){ // 镖体真实包络: ⌀46 筒身+X 翼展 0.113 包络+头尾锥 (11-04 真实性修正)
  // 平段→锥段 smoothstep 混合: 原线性过渡 R(x) 导数跳变 → 速度场沿轴向跳色 (头部环状色带, 曼波截图指认)
  const ax=Math.abs(x);
  if(ax>.115) return 0;
  const taper=sstep((ax-.06)/.055);
  return .058*(1-taper)+.012*taper;
}
function flowVel(px,py,pz,U,tNow,out){
  // 细长体横向绕流 (2D 偶极子/轴段): v = U_x·x̂ + U_perp·(1-R²/r²) + 尾迹
  // 真实性 (11-04 曼波: 渲染严格按仿真): r=R 处横向速度→0 = 贴体滑移, 流线不穿体;
  //   旧版源分布对等直圆柱段排挤失效 (dA/dx=0 无源) → 流线被"吸入"体表假象。
  let vx=U.x, vy=U.y, vz=U.z;
  const xc=Math.max(-.1, Math.min(.1, px));
  const R=bodyR(xc);
  if(R>.004){
    const denom=Math.max(py*py+pz*pz, R*R*.96);   // r² 下限≈R²: 表面滑移
    const f=1-(R*R)/denom;
    vy=U.y*f; vz=U.z*f;                            // 横向分量绕流修正, 轴向不变 (2D)
  }
  // 头端驻点: 迎风头锥区轴向渐止 (U.x<0 → 头在 +x; U.x>0 → 头在 -x)
  // 只衰减"会撞端面"的流线 (r_perp<包络); r 包络外的绕体流线放行 (物理: 绕过头部继续)
  {
    const headD=(U.x<0?1:-1)*(.115-px);              // >0 = 头端内侧
    if(headD>0){
      const rr2=Math.hypot(py,pz);
      const Rb=Math.max(bodyR(px),1e-4); // 11-06 顺手修: |px| 出体域时 bodyR=0 → 轴上点 0/0=NaN 污染速度场
      const gate=1-sstep(Math.max(0,(rr2-.4*Rb))/(.6*Rb)); // 轴心 1→表面 0 平滑 (滑行流线不衰减)
      vx*=1-sstep(headD/.055)*gate;
    }
  }
  const s=px*U.x+py*U.y+pz*U.z;                    // 沿流向距离
  const rx=px-U.x*s, ry=py-U.y*s, rz=pz-U.z*s;
  const r=Math.sqrt(rx*rx+ry*ry+rz*rz);            // 垂直来流距离 (尾迹核用)
  if(s>AEROBODY.x1&&out){
    const decay=Math.exp(-(s-AEROBODY.x1)/.4);
    const core=Math.exp(-(r*r)/(0.035*0.035));
    vx-=U.x*.45*core*decay; vy-=U.y*.45*core*decay; vz-=U.z*.45*core*decay;
    const sw=.14*out.wakeAmp*Math.sin(20*s-6*tNow)*core*decay;
    vz+=sw*out.wakeDir.y; vy+=sw*out.wakeDir.x*.3;
  }
  const sp=Math.sqrt(vx*vx+vy*vy+vz*vz);
  out.x=vx;out.y=vy;out.z=vz;return sp;
}
const JET=[[0,[0,.55,1]],[.25,[0,.92,.62]],[.5,[.45,1,.25]],[.72,[1,.92,.1]],[.88,[1,.45,0]],[1,[1,.08,.05]]];
function aeroJet(v){ // 速度→色 (非线性分段 — 11-05 三修: 全程渐变, 主流 21 也有色差)
  let t;
  if(v < 10)      t = 0.02 + (v/10)*0.20;             // 驻点/深边界层 → 深青
  else if(v < 19) t = 0.22 + ((v-10)/9)*0.25;         // 边界层 → 青-绿
  else if(v < 22) t = 0.47 + ((v-19)/3)*0.28;         // 主流 → 绿-黄 (21 也可见色差)
  else            t = 0.75 + Math.min(1,(v-22)/7)*0.25; // 加速 → 橙红
  return jetColor(t);
}
function jetColor(t){ // 速度归一 → 青绿黄红 (对齐参考图色标)
  t=Math.max(0,Math.min(1,t));
  for(let i=1;i<JET.length;i++) if(t<=JET[i][0]){
    const w=(t-JET[i-1][0])/(JET[i][0]-JET[i-1][0]),a=JET[i-1][1],b=JET[i][1];
    return [a[0]+(b[0]-a[0])*w,a[1]+(b[1]-a[1])*w,a[2]+(b[2]-a[2])*w];}
  return JET[JET.length-1][1];
}
function fetchAeroBlue(){ // 11-06 P1-10b: aero_blue 只在有变化时重挂 (Last-Modified/ETag 戳比对); 失败退避跳过下 1/2/3 个 30s 周期 (=30/60/120s 封顶)
  if(AERO.blueSkip>0){AERO.blueSkip--;return;}
  fetch('aero_blue.json?_='+Date.now())
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);
      const tag=r.headers.get('Last-Modified')||r.headers.get('ETag')||null;
      if(tag&&AERO.blueTag===tag)return null; // 戳未变: 不重解析不重挂
      AERO.blueTag=tag;return r.json();})
    .then(j=>{if(!j||!j.rows)return;AERO.rows=j.rows;AERO.blueSkip=0;updateAero();
      // P2 追加 scope-2: 姿态流线"自动补"落地 — 上次 loadPoseFor 失败 (streamsOn=false, 流线已隐藏) 时
      // 借 30s 蓝表轮询点对当前滑块姿态后台重试 (文案"引擎收割后自动补"的兑现); 竞态守卫内建
      // (loadPoseFor 的 _poseSeq+AbortController); 失败静默等下一轮, 不打扰 UI 文案。
      if(AERO.poseIdx&&AERO.streamsOn===false){
        const ins=document.querySelectorAll('#sliders input[type=range]');
        if(ins.length>=6)loadPoseFor(+ins[4].value,+ins[5].value).catch(()=>{});
      }})
    .catch(()=>{AERO.blueSkip=Math.min(3,AERO.blueSkip+1);
      if(!AERO.rows)$('aeroread').textContent='气动查表: aero_blue.json 未就绪 (等 J1 下一轮, 退避重试中)';});
}
let _poseSeq=0,_poseAbortC=null; // 11-06 P0-2: 递增序号 + AbortController — 600ms debounce 不消并发, 慢的 15MB 旧响应后到不得回写旧姿态
function loadPoseFor(a,b){ // 姿态切换: 选最近姿态 → 拉 json → AERO.real 更新
  const best=AERO.pickPose(a,b);
  if(!best)return Promise.reject('no-pose');
  const mySeq=++_poseSeq;
  if(_poseAbortC){try{_poseAbortC.abort();}catch(_){}}   // 新请求作废上一个在途 fetch
  const ac=_poseAbortC=new AbortController();
  return fetch('poses/'+best.file+'?_='+Date.now(),{signal:ac.signal})
    .then(r=>{
      if(mySeq!==_poseSeq)return null;                    // 序号过期: 连 15MB body 都不读
      if(!r.ok)return Promise.reject(r.status);
      return r.json();
    })
    .then(j=>{
      if(j===null||mySeq!==_poseSeq)return null;          // 响应落地前比对 (第一行守卫): 旧响应丢弃
      // 绕转过渡 (11-05 曼波: 转 α/β 时风场整体绕转): 旧来流方向 → 新来流方向 slerp 400ms
      const oldDir=new THREE.Vector3(-1,0,0);
      if(AERO.real){const A0=(AERO.real.alpha||0)*Math.PI/180,B0=(AERO.real.beta||0)*Math.PI/180;
        oldDir.set(-Math.cos(A0)*Math.cos(B0),-Math.sin(B0),-Math.sin(A0)*Math.cos(B0)).normalize();}
      const A1=(j.alpha||0)*Math.PI/180,B1=(j.beta||0)*Math.PI/180;
      const newDir=new THREE.Vector3(-Math.cos(A1)*Math.cos(B1),-Math.sin(B1),-Math.sin(A1)*Math.cos(B1)).normalize();
      const q0=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1,0,0),oldDir);
      const q1=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1,0,0),newDir);
      const qRel=q1.clone().multiply(q0.clone().invert());   // 相对旋转
      // 11-05 简化: 数据立即落 (fetch 完成即换装) — spin 动画守卫链曾在后台卡死致数据不落
      AERO.real=j; AERO.realLinesGeom=null; AERO.realLayered=undefined;  // 分层缓存随换装失效
      updateAero();
      AERO.streamsOn=true;  // 11-06 分层: 真实流线在场 → 粒子退为弱背景 (aeroTick 读; 与流线显隐同源切换)
      return best;
    })
    .catch(e=>{
      if(ac.signal.aborted||mySeq!==_poseSeq)return null;  // abort 静默: 不算错误, 不触发调用方"隐藏流线"回退
      throw e;
    });
}
/* ---------- Tube 流线 4 纯函数 (P2 拆分: 原 rebuildStreamlines 内联段, 逐点逻辑不变) ---------- */
function tubeBodyEnv(x){ // 流线管体表包络 (原 bodyEnv — 与势流 bodyR 几何同源, 边界值略异, 保持原值)
  const ax=Math.abs(x);
  if(ax>0.116)return 0;
  if(ax<0.072)return 0.0580;
  return 0.0580+(0.014-0.0580)*((ax-0.072)/0.044);}
function projectBody(ln){ // ① 投影贴体: 体内点径向投影到体表+0.3mm 保持线连续 (不切碎);
  //    v<1.2 数值死点才裁 — 驻点/尾流慢速点保留 (减速层=单线渐变的物理来源, 11-06 牛图迭代)
  const out=[];
  for(const p of ln){
    const rE=tubeBodyEnv(p[0]);
    const r=Math.hypot(p[1],p[2]);
    if(rE>0.004 && r<rE){            // 体内点→径向投影体表+0.3mm
      const f=rE*1.006/(r||1e-6);
      out.push([p[0],p[1]*f,p[2]*f,p[3]]);
    } else if(p[3]<1.2)continue;
    else out.push(p);
  }
  return out;}
function bridgeGaps(ln){ // ② 断口桥接: gap>0.02 处沿包络面补 1 点桥接弧 (11-05 曼波: 气体受阻后直线弹开不物理)
  const out=[];
  for(let i=0;i<ln.length;i++){
    if(i>0){
      const a=ln[i-1], b=ln[i];
      const gap=Math.hypot(b[0]-a[0],b[1]-a[1],b[2]-a[2]);
      if(gap>0.02){   // 断口: 沿包络补桥接弧
        const mid=(a[0]+b[0])/2;
        const rE=tubeBodyEnv(mid);
        if(rE>0.004){
          const my=(a[1]+b[1])/2, mz=(a[2]+b[2])/2;
          const th=Math.atan2(mz,my);
          const rr=rE*1.02;
          out.push([mid,Math.cos(th)*rr,Math.sin(th)*rr,(a[3]+b[3])/2]);
        }
      }
    }
    out.push(ln[i]);
  }
  return out;}
function chaikinSmooth(ln){ // ③ Chaikin 细分 (折点→圆弧): 每段 1/4-3/4 切角
  const sm=[];
  for(let i=0;i<ln.length-1;i++){
    const a=ln[i], b=ln[i+1];
    if(i===0)sm.push(a);
    sm.push([a[0]*0.75+b[0]*0.25, a[1]*0.75+b[1]*0.25, a[2]*0.75+b[2]*0.25, (a[3]*0.75+b[3]*0.25)]);
    sm.push([a[0]*0.25+b[0]*0.75, a[1]*0.25+b[1]*0.75, a[2]*0.25+b[2]*0.75, (a[3]*0.25+b[3]*0.75)]);
    if(i===ln.length-2)sm.push(b);
  }
  return sm;}
let _tubeMatN=null,_tubeMatF=null; // P2 合并几何: 近/远层共享材质 (重建复用, 不 dispose)
function tubeMats(){
  if(!_tubeMatN)_tubeMatN=new THREE.MeshStandardMaterial({vertexColors:true,metalness:.1,roughness:.55,
    transparent:true,opacity:.85,emissive:0x0a0a12,depthWrite:false}); // 11-06 P0-6: 透明管关深度写, 防互相裁
  if(!_tubeMatF)_tubeMatF=new THREE.MeshStandardMaterial({vertexColors:true,metalness:.1,roughness:.55,
    transparent:true,opacity:.45,emissive:0x0a0a12,depthWrite:false});
  return {n:_tubeMatN,f:_tubeMatF};}
function emitTube(ln,batchN,batchF){ // ④ 建管上色: CatmullRomCurve3→临时 TubeGeometry → 顶点/法线/顶点色/index 偏移并入近/远 batch
  //    (P2 合并版: 顶点已是最终位置 — 原 Mesh 无变换直接 add, concat 即得; 近粗 .00045/远细 .00028)
  const minR=Math.min(...ln.map(p=>Math.hypot(p[1],p[2])));
  const near=minR<0.09;
  const pts3=ln.map(p=>new THREE.Vector3(p[0],p[1],p[2]));
  if(pts3.length<8)return near;
  const curve=new THREE.CatmullRomCurve3(pts3, false, 'catmullrom', 0.5);
  const batch=near?batchN:batchF;   // 层归属挑拣 (minR<0.09 = 近体层, 与原判定同源)
  const rad=near?0.00045:0.00028;   // 11-06 视觉验收: 0.0011 太粗糊团 → 细管
  const SEG=Math.min(120, Math.max(24, pts3.length));   // 曲线细分自适应
  const tg=new THREE.TubeGeometry(curve, SEG, rad, 5, false);
  const pa=tg.attributes.position,na=tg.attributes.normal,ia=tg.index;
  // 顶点色: Tube 顶点按环序映射数据速度 — 每环 (radialSegments+1)=6 顶点同色
  const vcols=new Float32Array(pa.count*3);
  const perRing=6;   // ★ 11-06 渐变根治: 旧 (SEG+1)*5 除数错致 t 压缩 ~120×→全线单色 (曼波实锤"没有单线渐变")
  for(let vi=0;vi<pa.count;vi++){
    const t=Math.min(1,Math.max(0,((vi/perRing)|0))/SEG);
    const v=ln[Math.min(ln.length-1,Math.round(t*(ln.length-1)))][3];
    const c=aeroJet(v);
    vcols[vi*3]=c[0];vcols[vi*3+1]=c[1];vcols[vi*3+2]=c[2];
  }
  const base=batch.voff;
  for(let vi=0;vi<pa.count;vi++){
    batch.pos.push(pa.getX(vi),pa.getY(vi),pa.getZ(vi));
    batch.nrm.push(na.getX(vi),na.getY(vi),na.getZ(vi));
    batch.col.push(vcols[vi*3],vcols[vi*3+1],vcols[vi*3+2]);
  }
  if(ia)for(let ii=0;ii<ia.count;ii++)batch.idx.push(base+ia.getX(ii)); // 索引偏移: 顶点基数平移
  batch.voff=base+pa.count;
  tg.dispose(); // 临时几何 (attributes 已拷入 batch)
  return near;} // 返回层归属: 调用方 glow 流光点判定用 (与原 near 判定同源)
function buildTubeLayer(batch,mat,order){ // batch → 1 个合并 BufferGeometry Mesh (P2: ≤400 管 → 每层 1 draw call)
  if(!batch.voff)return null;
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(batch.pos,3));
  g.setAttribute('normal',new THREE.Float32BufferAttribute(batch.nrm,3));
  g.setAttribute('color',new THREE.Float32BufferAttribute(batch.col,3));
  g.setIndex(batch.idx);
  const m=new THREE.Mesh(g,mat);
  m.renderOrder=order;   // 11-06 P0-6: 远层低近层高, glow 最后 — 确定性透明排序 (层序保留)
  m.frustumCulled=false; // 合并后全域包围, 防重建瞬间包围球过期误剔
  AERO.scene.add(m);
  return m;}
function rebuildStreamlines(U,tNow){ // α/β 变化时重建 (调用方节流)
  if(AERO.real && AERO.real.lines && AERO.real.lines.length){ // ── 真实 CFD 场流线 (qianli foamToVTK→积分→json) — 严格按仿真 ──
    // lines 空 = 积分失败旧版 json → 回退势流 (守卫 11-04)
    // 11-04 二修(曼波指认旋转后穿模): 刚体旋转方案废弃 — 旋转载荷流线+固定 mesh=错位穿模
    // (流线绕的是原姿态镖体, mesh 不转就怼进机身)。正确方案=多姿态数据选择制:
    // 每姿态用【该姿态自己的 case 真实场】积分 (扫气逐姿态跑, 每 case 都有真实场),
    // 后处理批量预计算 poses{} — 滑块切姿态选对应数据, mesh/流线/表面色永远同姿态自洽。
    // 现有 json 单姿态 (α=-2.5): 姿态外滑块 → 透明度降+徽标注「基准姿态」;
    // 多姿态 poses 到位后按最近姿态选择 (delta_early_plan §5 扩展)。
    AERO.realQuat=null;
    if(AERO.sl && AERO.realLinesGeom===AERO.real){ // 已建: 数据未变, 无需重建
      return;
    }
    AERO.realLinesGeom=AERO.real; // 标记已建 (数据源版本)
    (AERO.tubesN||[]).forEach(t=>{AERO.scene.remove(t);t.geometry.dispose();});AERO.tubesN=[]; // P2 合并版: 元素=每层 1 个合并 Mesh (材质共享复用不 dispose)
    (AERO.tubesF||[]).forEach(t=>{AERO.scene.remove(t);t.geometry.dispose();});AERO.tubesF=[];
    if(AERO.sl)  {AERO.scene.remove(AERO.sl);  AERO.sl.geometry&&AERO.sl.geometry.dispose();}
    if(AERO.slNear){AERO.scene.remove(AERO.slNear);AERO.slNear.geometry&&AERO.slNear.geometry.dispose();}
    if(AERO.glow){AERO.scene.remove(AERO.glow);AERO.glow.geometry.dispose();}
    // 速度/距离分层 (11-05 曼波: 近体减速绕转要显性化): 近体层粗亮/外场层细淡
    // P2 合并几何: 近/远各一个 batch → 各并成 1 个 BufferGeometry (draw call 400→~2)
    const batchN={pos:[],nrm:[],col:[],idx:[],voff:0},batchF={pos:[],nrm:[],col:[],idx:[],voff:0};
    const glowArr=[];AERO.glowRef=[];
    // 11-06: Tube 版全量渲染不抽稀 — 365 条 rake 线全部出 (管有体量感不需要稀疏化)
    const MAXL=400, NL=AERO.real.lines.length;
    const stride=NL>MAXL?Math.ceil(NL/MAXL):1;   // b11 老数据 2287 条抽稀到 ~400 (v3 665 条不抽) — 密度治理 (牛图观感)
    let hugN=0;                                   // 贴体线计数 (每次重建重置)
    AERO.real.lines.forEach((ln0,li)=>{
      if(stride>1 && li%stride!==0)return;
      // ① 体表投影替代体内裁除 (11-06 牛图迭代: 裁除把贴体段切碎成炸毛 — 改径向投影到体表+0.3mm
      //    保持线连续, 贴体段沿包络面走; 慢速点保留=减速层可见 (单线渐变的物理来源)
      const ln2=projectBody(ln0);
      if(ln2.length<20)return;
      // 贴体线额外抽稀 (11-06: 投影壳过厚遮镖体 — 贴体线每 3 条取 1, 外场线全保; 曼波"破碎混乱"密度侧治理)
      let hug=false;
      for(const p of ln2){
        if(Math.abs(p[0])>0.115)continue;
        if(Math.hypot(p[1],p[2])-tubeBodyEnv(p[0])<0.006){hug=true;break;}
      }
      if(hug){hugN++;if(hugN%3!==1)return;}
      // ② 断口桥接 + ③ Chaikin 平滑 (11-05 曼波: 气体受阻后直线弹开不物理 —
      //    裁除断口处沿包络面补 3 点桥接弧; 全线 Chaikin 细分把折点变圆滑)
      const bridged=bridgeGaps(ln2);
      const sm=chaikinSmooth(bridged);
      const ln=sm.length>20?sm:bridged;   // 平滑后的线
      // ④ Tube 入层 (P2: 近/远 batch 由 emitTube 内 near 判定挑拣, 返回层归属供 glow 用)
      const near=emitTube(ln,batchN,batchF);
      if(!near && li%6===0) for(let g=0;g<3;g++){glowArr.push(ln[0][0],ln[0][1],ln[0][2]);
        AERO.glowRef.push({pts:ln.map(p=>[p[0],p[1],p[2]]),t:(g/3+li*.07)%1});}
    });
    const mats=tubeMats();
    const mN=buildTubeLayer(batchN,mats.n,10),mF=buildTubeLayer(batchF,mats.f,5);
    AERO.tubesN=mN?[mN]:[];AERO.tubesF=mF?[mF]:[];  // 数组语义保留 (显隐/清理钩子兼容), 元素=合并 Mesh
    // 11-06 Tube 版: posN/posF 线段流废弃 (Tube 直接 add; AERO.sl/slNear 指到 Tube 组以便兼容旧清理钩子)
    AERO.slNear=AERO.tubesN?{geometry:{dispose:()=>AERO.tubesN.forEach(t=>t.geometry.dispose())},visible:true}:null;
    AERO.sl=AERO.tubesF?{geometry:{dispose:()=>AERO.tubesF.forEach(t=>t.geometry.dispose())},visible:true}:null;
    const gg=new THREE.BufferGeometry();
    gg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(glowArr),3));
    AERO.glow=new THREE.Points(gg,new THREE.PointsMaterial({color:0xeaffff,size:.006,transparent:true,opacity:.9,depthWrite:false,map:glowTex(),blending:THREE.AdditiveBlending}));
    AERO.glow.renderOrder=15;AERO.glow.frustumCulled=false; // 最后渲染; 位置每帧动 — 包围盒过期会整组误剔除
    AERO.scene.add(AERO.glow);
    if(AERO.real.surf&&AERO.real.surf.length){ // 表面顶点色=真实场采样 (与前端 mesh 顶点一一对应)
      // 11-06 质检: b11/v3 生成代 surf 色标归一化错 (jet((sp-.45)/.85), sp 单位 m/s → v>1.3 全饱和红,
      //   镖体/翼面大红块)。源场已删无法重算 → 前端饱和率检测自动弃用坏代 (>80% 顶点纯红=垃圾),
      //   镖体保持固体材质; 未来收割代 (sl_v3 jet 已修) 落地后自动恢复启用。
      let sat=0,n=0;
      for(let si=0;si<AERO.real.surf.length;si+=3){n++;
        if(AERO.real.surf[si]>0.9&&AERO.real.surf[si+1]<0.25&&AERO.real.surf[si+2]<0.25)sat++;}
      if(sat/n<0.8){
        const mesh=T3.dart&&T3.dart.children.find(c=>c.isMesh);if(mesh&&mesh.geometry){
          const g=mesh.geometry;
          if(!g.attributes.color)g.setAttribute('color',new THREE.BufferAttribute(new Float32Array(g.attributes.position.count*3),3));
          g.attributes.color.array.set(AERO.real.surf.slice(0,g.attributes.position.count*3));
          g.attributes.color.needsUpdate=true;
          if(!mesh.material.vertexColors){mesh.material.vertexColors=true;mesh.material.color.set(0xffffff);mesh.material.needsUpdate=true;}
        }
        AERO.surfReal=true;
      } else { // 11-06 顺手修: 坏代弃用时重置材质 — 前一姿态顶点色不得残留 (vertexColors 关+中性色还原)
        AERO.surfReal=false;
        const m0=T3.dart&&T3.dart.children.find(c=>c.isMesh);
        if(m0&&m0.material&&m0.material.vertexColors){m0.material.vertexColors=false;m0.material.color.set(0x7a86b8);m0.material.needsUpdate=true;}
      }
    }
    // 表面色姿态边界: 当前 json 只有 α=-2.5 单姿态采样 — 滑块旋转时表面色保持基准姿态
    // (严格按仿真: 不做假重采样; 多姿态预计算 json 就绪后自动切换 — delta_early_plan §5)
    AERO.surfAlphaFixed=true;
    return; // 真实流线: 姿态旋转已应用 (首建在此分支, 力矢量/查表照旧联动)
  }
  (AERO.tubesN||[]).forEach(t=>{AERO.scene.remove(t);t.geometry.dispose();});AERO.tubesN=[];
  (AERO.tubesF||[]).forEach(t=>{AERO.scene.remove(t);t.geometry.dispose();});AERO.tubesF=[];
  if(AERO.sl)  {AERO.scene.remove(AERO.sl);  AERO.sl.geometry&&AERO.sl.geometry.dispose();}
  if(AERO.slNear){AERO.scene.remove(AERO.slNear);AERO.slNear.geometry&&AERO.slNear.geometry.dispose();}
  if(AERO.glow){AERO.scene.remove(AERO.glow);AERO.glow.geometry.dispose();}
  const ins=document.querySelectorAll('#sliders input[type=range]');
  const wakeAmp=.35+Math.abs(+ins[4].value)/15*.9;               // 尾涡摆幅随攻角
  const wd=new THREE.Vector3(0,0,1); if(Math.abs(U.z)>.9) wd.set(0,1,0);
  const e1=new THREE.Vector3(0,1,0).cross(U).normalize(); if(e1.lengthSq()<.5)e1.set(1,0,0);
  const e2=new THREE.Vector3().crossVectors(U,e1);
  const NSEG=110,h=.005,out={wakeAmp,wakeDir:wd,x:0,y:0,z:0};
  // 起点盘: 上游 0.24, 极坐标 9 环 + 轴心 5 点 ≈ 239 条
  const starts=[];
  for(let ring=0;ring<9;ring++){const rr=.008+ring*.0115, nk=Math.max(6,ring*5)+6;
    if(rr<.064) continue;                                  // 剔除体包络内起点 (本应驻点分流, 2D 势流无该解→不画)
    for(let k=0;k<nk;k++){const th=k/nk*6.2832;starts.push([rr*Math.cos(th),rr*Math.sin(th)]);}}
  const pos=[],cg=[],lines=[];
  const c0=new THREE.Vector3(),c1=new THREE.Vector3();
  for(const st of starts){
    let px=-U.x*.24+e1.x*st[0]+e2.x*st[1], py=-U.y*.24+e1.y*st[0]+e2.y*st[1], pz=-U.z*.24+e1.z*st[0]+e2.z*st[1];
    const pts=[[px,py,pz,1]];
    let hitBody=false;
    for(let step=0;step<NSEG;step++){
      flowVel(px,py,pz,U,tNow,out);
      const mx=px+out.x*h*.5,my=py+out.y*h*.5,mz=pz+out.z*h*.5;
      const sp2=flowVel(mx,my,mz,U,tNow,out), inv=sp2>1e-5?h/sp2:h;
      px+=out.x*inv; py+=out.y*inv; pz+=out.z*inv;
      // 体表碰撞投影 (11-04 真实性修正: 势流点源离散不足致流线切入体 —
      //   CFD 后处理标准做法: 体内点沿径向投影到体表面外, 流线只能贴体不能穿体)
      const sx=px*U.x+py*U.y+pz*U.z;
      if(sx>AEROBODY.x0&&sx<AEROBODY.x1){
        const Rb=bodyR(sx)+.002;
        const ry2=py-U.y*sx, rz2=pz-U.z*sx, rb=Math.hypot(ry2,rz2);
        if(rb<Rb){const f=Rb/rb;py=U.y*sx+ry2*f;pz=U.z*sx+rz2*f;}
      }
      if(px*U.x+py*U.y+pz*U.z>.34)break;
      if(sp2<.03){hitBody=true;break;}                    // 驻点截断: 流线终止于驻点 (物理)
      pts.push([px,py,pz,sp2]);
    }
    lines.push(pts);
    for(let i=0;i<pts.length-1;i++){
      pos.push(...pts[i].slice(0,3),...pts[i+1].slice(0,3));
      cg.push(...jetColor(Math.max(0,Math.min(1,(pts[i][3]-.55)/.75))),
              ...jetColor(Math.max(0,Math.min(1,(pts[i+1][3]-.55)/.75))));
    }
  }
  const pg=new THREE.BufferGeometry();
  pg.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  pg.setAttribute('color',new THREE.Float32BufferAttribute(cg,3));
  AERO.sl=new THREE.LineSegments(pg,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.5}));
  AERO.scene.add(AERO.sl);
  // 流光点: 每 4 条流线 3 个亮点沿弧长参数循环滑动 (aeroTick 推进 t)
  const glow=[];AERO.glowRef=[];
  lines.forEach((pts,li)=>{if(li%4)return;
    for(let g=0;g<3;g++){glow.push(...pts[0].slice(0,3));AERO.glowRef.push({pts,t:(g/3+li*.11)%1});}});
  const gg=new THREE.BufferGeometry();
  gg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(glow),3));
  AERO.glow=new THREE.Points(gg,new THREE.PointsMaterial({color:0xeaffff,size:.007,transparent:true,opacity:.95,depthWrite:false,map:glowTex(),blending:THREE.AdditiveBlending}));
  AERO.glow.renderOrder=15;AERO.glow.frustumCulled=false; // 11-06: 圆点纹理防方块杂点; 最后渲染; 包围盒过期防误剔除
  AERO.scene.add(AERO.glow);
}
let _glowTexCache=null;
function glowTex(){ // 11-06 P1-7b: Points 默认方块杂点 → 径向渐变圆点纹理 (缓存单例)
  if(_glowTexCache)return _glowTexCache;
  const cv=document.createElement('canvas');cv.width=cv.height=32;
  const g=cv.getContext('2d');
  const gr=g.createRadialGradient(16,16,0,16,16,16);
  gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(.4,'rgba(255,255,255,.8)');gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=gr;g.fillRect(0,0,32,32);
  _glowTexCache=new THREE.CanvasTexture(cv);return _glowTexCache;
}
/* ---------- ⑤ 来流粒子背景层 (11-06 P1-7 重做) ----------
   旧版平行直线雨 (直线穿体/无梯度/方块杂点) 弃用。新版: 每粒子用势流函数 flowVel 采样 →
   近体自然沿切向偏转绕体; 每粒子=沿局部速度方向的短线段 (LineSegments, 长度∝|v| 封顶);
   色用流线同款 jet 色表 (按速度大小), 远场暗淡 — "来流方向感背景层", 视觉权重低于流线 Tube 主角。 */
const _fpE1=new THREE.Vector3(),_fpE2=new THREE.Vector3(),_fpRY=new THREE.Vector3(0,1,0),_fpRX=new THREE.Vector3(1,0,0);
function initFlowParticles(scene){
  const N=300;                                  // ~250-350 区间 (密度低于流线, 不抢戏)
  const pos=new Float32Array(N*2*3),col=new Float32Array(N*2*3);
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(pos,3));
  g.setAttribute('color',new THREE.BufferAttribute(col,3));
  const segs=new THREE.LineSegments(g,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.55,depthWrite:false}));
  segs.renderOrder=2;                           // 背景层: 低于流线 tube (远5/近10) 与 glow (15)
  segs.frustumCulled=false;                     // 位置每帧改, 包围盒不重算
  scene.add(segs);
  const parts=[];for(let i=0;i<N;i++)parts.push({x:0,y:0,z:0,t:Math.random()*5,life:1+Math.random()*4,init:false});
  AERO.flow={segs,parts,out:{wakeAmp:.5,wakeDir:{x:0,y:1,z:0},x:0,y:0,z:0}};
}
function respawnParticle(p,U){ // 上游盘重生: -U*0.26 + 垂面极坐标, ρ 幂分布 (近体稍密)
  _fpE1.copy(_fpRY).cross(U);if(_fpE1.lengthSq()<.25)_fpE1.copy(_fpRX).cross(U);_fpE1.normalize();
  _fpE2.crossVectors(U,_fpE1);
  const rho=.02+.14*Math.pow(Math.random(),1.4),th=Math.random()*6.2832;
  const r1=rho*Math.cos(th),r2=rho*Math.sin(th);
  p.x=-U.x*.26+_fpE1.x*r1+_fpE2.x*r2;
  p.y=-U.y*.26+_fpE1.y*r1+_fpE2.y*r2;
  p.z=-U.z*.26+_fpE1.z*r1+_fpE2.z*r2;
  p.t=0;p.life=3+Math.random()*4;
}
let _t0=performance.now();
function tNow0(){return (performance.now()-_t0)/1000;}
let _tickLast=performance.now();
const _tickV=new THREE.Vector3();
function aeroTick(){ // 流光点+来流粒子推进 (每帧; p5 不可见/窗口遮挡时由调用侧跳过)
  if(window.__aeroVisible===false)return;
  const nowMs=performance.now();
  const dt=Math.max(0,Math.min(.05,(nowMs-_tickLast)/1000));_tickLast=nowMs; // 11-06 P1-7e: 真实帧间隔 (原 1/60 硬编码; 钳 0-50ms)
  if(AERO.glowRef&&AERO.glow&&AERO.glow.geometry){
    const att=AERO.glow.geometry.attributes.position;
    for(let gi=0;gi<AERO.glowRef.length;gi++){
      const g=AERO.glowRef[gi], pts=g.pts;
      // 速度感知推进: 步长 ∝ 局部真实 |U| (尾迹慢/主流快 — 稳态场里的"流动感"来自差速)
      const fi0=g.t*(pts.length-1), i00=Math.floor(fi0);
      const vHere=pts[Math.min(i00,pts.length-1)][3]||20;
      g.t=(g.t+dt*.55*(vHere/22))%1;
      const fi=g.t*(pts.length-1), i0=Math.floor(fi), fr=fi-i0;
      const a=pts[Math.min(i0,pts.length-1)], b=pts[Math.min(i0+1,pts.length-1)];
      _tickV.set(a[0]+(b[0]-a[0])*fr, a[1]+(b[1]-a[1])*fr, a[2]+(b[2]-a[2])*fr); // 复用临时向量 (原每帧 new 致 GC 碎屑)
      att.array[gi*3]=_tickV.x; att.array[gi*3+1]=_tickV.y; att.array[gi*3+2]=_tickV.z;
    }
    att.needsUpdate=true;
  }
  if(AERO.flow&&AERO.U){ // ⑤ 来流粒子: 势流场 flowVel 采样推进 — 近体自然偏转绕体 (11-06 P1-7)
    const F=AERO.flow,U=AERO.U,out=F.out,tN=tNow0();
    // 11-06 分层: 真实流线在场 (收敛场版 surf+hasLayer) → 粒子退为弱背景 (opacity×0.5 + 线长上限减半),
    // 消侧视"篱笆墙"过载; 无流线/均匀场/加载失败 → 恢复全量。streamsOn 随流线显隐同源 (loadPoseFor 成败两侧设)
    const layered=AERO.streamsOn&&AERO.real&&AERO.real.surf&&AERO.hasLayer();
    const dimK=layered?.5:1;
    if(F.dimK!==dimK){F.dimK=dimK;F.segs.material.opacity=.55*dimK;}
    const pa=F.segs.geometry.attributes.position.array, ca=F.segs.geometry.attributes.color.array;
    for(let i=0;i<F.parts.length;i++){
      const p=F.parts[i];
      if(!p.init){respawnParticle(p,U);p.init=true;}
      const sp=flowVel(p.x,p.y,p.z,U,tN,out);
      const SC=.008; // 慢放: 场速 ~20m/s → 视觉 ~0.16m/s (0.7m 域穿越 ~4s)
      p.x+=out.x*dt*SC;p.y+=out.y*dt*SC;p.z+=out.z*dt*SC;p.t+=dt;
      { // 体表滑移投影 (与势流流线同款): 体内点径向推出包络 — 粒子贴体绕不穿体
        const sx=p.x*U.x+p.y*U.y+p.z*U.z;
        if(sx>AEROBODY.x0&&sx<AEROBODY.x1){
          const Rb=bodyR(sx)+.002;
          const ry=p.y-U.y*sx,rz=p.z-U.z*sx,rb=Math.hypot(ry,rz);
          if(rb<Rb){const f=Rb/(rb||1e-6);p.y=U.y*sx+ry*f;p.z=U.z*sx+rz*f;}
        }
      }
      // 短线段: 当前位置 → 沿局部速度方向 (长度∝|v| 封顶 4-20mm; 分层时上/下限减半)
      const vlen=Math.min(.02*dimK,Math.max(.004*dimK,sp*.0011)), il=1/(sp||1e-6);
      pa[i*6]=p.x;pa[i*6+1]=p.y;pa[i*6+2]=p.z;
      pa[i*6+3]=p.x+out.x*il*vlen;pa[i*6+4]=p.y+out.y*il*vlen;pa[i*6+5]=p.z+out.z*il*vlen;
      const cc=aeroJet(sp); // 与流线同款 jet 色表 (按速度大小)
      const rr=Math.hypot(p.y,p.z); // 远场暗化: 背景层不抢戏 (近体 r<.06 全亮, r>.14 减半封底)
      const dim=rr<.06?1:Math.max(.45,1-(rr-.06)/.08*.55);
      ca[i*6]=cc[0]*dim;ca[i*6+1]=cc[1]*dim;ca[i*6+2]=cc[2]*dim;
      ca[i*6+3]=cc[0]*dim;ca[i*6+4]=cc[1]*dim;ca[i*6+5]=cc[2]*dim;
      if(p.t>p.life||p.x*U.x+p.y*U.y+p.z*U.z>.32)respawnParticle(p,U); // 出域/寿命尽 → 上游重生 (下帧起画)
    }
    F.segs.geometry.attributes.position.needsUpdate=true;
    F.segs.geometry.attributes.color.needsUpdate=true;
  }
}
Object.defineProperty(window.WT_DEBUG,'AERO',{configurable:true,value:AERO}); // 附加直查: 流场状态
