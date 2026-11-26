import * as THREE from 'three'
import {OrbitControls} from 'three/addons/controls/OrbitControls.js'
import {riskColor} from '@/utils/street-map'
import {replaySegments} from '@/utils/clue-replay'
import {GLOBE_RADIUS as R,globeLayout,globeJump,angularDistance,wheelDistance} from '@/utils/globe-math'
import {createCitySurfaces,CITY_BOUNDS,cityRoadLatitudes,CITY_ANGLE_SCALE,cityWarp} from './city-surfaces'
import {createAreaLandmarks} from './area-landmark-scene'
import {dragBindings,clampMapTarget,mapDetailLevel} from '@/utils/map-navigation'
import {MAP_QUALITY,zoomAnchorShift} from '@/utils/map-presentation'
import {createSceneLink,revealSceneLink} from './scene-links'
import {daylightEnvironment} from './scene-environment'

export function createStreetScene(host,layout,callbacks,options={}){
  const quality=MAP_QUALITY[options.quality]||MAP_QUALITY.standard,preview=!!options.preview
  const renderer=new THREE.WebGLRenderer({antialias:true})
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,quality.pixelRatio));renderer.setClearColor('#0b1525')
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.1
  renderer.shadowMap.enabled=quality.shadows&&!preview;renderer.shadowMap.type=THREE.PCFSoftShadowMap
  renderer.domElement.setAttribute('aria-hidden','true');host.appendChild(renderer.domElement)
  const scene=new THREE.Scene(),environment=quality.environment&&!preview?daylightEnvironment(renderer):null
  if(environment){scene.environment=environment.texture;scene.environmentIntensity=.38}
  const camera=new THREE.PerspectiveCamera(42,1,.1,1800)
  camera.position.set(0,R+420,310)
  const controls=new OrbitControls(camera,renderer.domElement)
  controls.enableDamping=true;controls.dampingFactor=.12;controls.enablePan=true;controls.screenSpacePanning=false;controls.panSpeed=.72;controls.rotateSpeed=.5
  controls.target.set(0,R*.99,0);controls.minDistance=100;controls.maxDistance=1000;controls.minPolarAngle=.35;controls.maxPolarAngle=1.35;controls.minAzimuthAngle=-1.1;controls.maxAzimuthAngle=1.1
  function setDragMode(mode){const b=dragBindings(mode);controls.mouseButtons={LEFT:THREE.MOUSE[b.left],MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE[b.right]};controls.touches={ONE:THREE.TOUCH[b.touch],TWO:THREE.TOUCH.DOLLY_PAN}}
  setDragMode('pan')
  scene.add(new THREE.HemisphereLight('#edf8ff','#779b8e',1.6))
  const sun=new THREE.DirectionalLight('#fff5dc',2.0);sun.position.set(-330,R+500,500);sun.target.position.set(0,R*.97,0);sun.castShadow=true;sun.shadow.mapSize.set(quality.shadowSize,quality.shadowSize);Object.assign(sun.shadow.camera,{left:-350,right:350,top:350,bottom:-350,near:1,far:1400});sun.shadow.bias=-.0004;sun.shadow.normalBias=.25;scene.add(sun,sun.target)
  const fill=new THREE.DirectionalLight('#9acbea',1.2);fill.position.set(180,R+180,-100);scene.add(fill)
  const nodes=globeLayout(layout.nodes),byId=new Map(nodes.map(n=>[n.area_id,n])),nodeMeshes=[]
  const surfaces=createCitySurfaces(nodes,{textureSize:quality.textureSize}),riverLongitude=surfaces.riverLongitude,textures=Object.fromEntries(['color','relief','detail'].map(k=>[k,new THREE.CanvasTexture(surfaces[k])]))
  textures.color.colorSpace=THREE.SRGBColorSpace;textures.detail.colorSpace=THREE.SRGBColorSpace
  Object.values(textures).forEach(t=>{t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy())})
  const rad=THREE.MathUtils.degToRad
  const capGeometry=()=>new THREE.SphereGeometry(R,128,96,Math.PI/2-rad(CITY_BOUNDS.lon*CITY_ANGLE_SCALE),rad(CITY_BOUNDS.lon*2*CITY_ANGLE_SCALE),Math.PI/2-rad(CITY_BOUNDS.lat*CITY_ANGLE_SCALE),rad(CITY_BOUNDS.lat*2*CITY_ANGLE_SCALE)).rotateX(-Math.PI/2)
  const globe=new THREE.Mesh(capGeometry(),new THREE.MeshStandardMaterial({map:textures.color,bumpMap:textures.relief,bumpScale:.22,roughness:.92,metalness:0}))
  globe.receiveShadow=true;scene.add(globe)
  const parcelGeometry=capGeometry().scale((R+.08)/R,(R+.08)/R,(R+.08)/R)
  const parcelLayer=new THREE.Mesh(parcelGeometry,new THREE.MeshBasicMaterial({map:textures.detail,transparent:true,opacity:.48,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1}))
  scene.add(parcelLayer)
  const details=new THREE.Group();scene.add(details)
  const hitTargets=[globe]
  const rawPoint=(lon,lat,r=R)=>{const a=rad(lon*CITY_ANGLE_SCALE),b=rad(lat*CITY_ANGLE_SCALE);return new THREE.Vector3(r*Math.cos(b)*Math.sin(a),r*Math.cos(b)*Math.cos(a),-r*Math.sin(b))}
  const point=(lon,lat,r=R)=>{const [l,t]=cityWarp(lon,lat);return rawPoint(l,t,r)}
  const basis=(lon,lat)=>{const [l]=cityWarp(lon,lat),up=point(lon,lat,1),east=new THREE.Vector3(Math.cos(rad(l*CITY_ANGLE_SCALE)),-Math.sin(rad(l*CITY_ANGLE_SCALE)),0),south=new THREE.Vector3().crossVectors(east,up).normalize();east.crossVectors(up,south).normalize();return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(east,up,south))}
  // A thin shell: convex upper ground and concave lower face, never a complete globe.
  const underside=new THREE.Mesh(capGeometry().scale((R-5)/R,(R-5)/R,(R-5)/R),new THREE.MeshStandardMaterial({color:'#c6c9b7',roughness:1,side:THREE.BackSide}));scene.add(underside)
  const rimPoints=[]
  for(let i=0;i<=80;i++)rimPoints.push([-60+i*1.5,-42])
  for(let i=1;i<=56;i++)rimPoints.push([60,-42+i*1.5])
  for(let i=1;i<=80;i++)rimPoints.push([60-i*1.5,42])
  for(let i=1;i<=56;i++)rimPoints.push([-60,42-i*1.5])
  const rimVertices=[],rimIndices=[]
  rimPoints.forEach(([l,t],i)=>{for(const radius of [R,R-5]){const v=rawPoint(l,t,radius);rimVertices.push(v.x,v.y,v.z)}if(i){const a=(i-1)*2;rimIndices.push(a,a+1,a+2,a+1,a+3,a+2)}})
  const rimGeo=new THREE.BufferGeometry();rimGeo.setAttribute('position',new THREE.Float32BufferAttribute(rimVertices,3));rimGeo.setIndex(rimIndices);rimGeo.computeVertexNormals();scene.add(new THREE.Mesh(rimGeo,new THREE.MeshStandardMaterial({color:'#c4c6b5',roughness:1,side:THREE.DoubleSide})))
  const dummy=new THREE.Object3D()
  const facade=document.createElement('canvas');facade.width=128;facade.height=256
  const fc=facade.getContext('2d');fc.fillStyle='#dfdfd2';fc.fillRect(0,0,128,256)
  for(let row=0;row<9;row++)for(let col=0;col<4;col++){fc.fillStyle=(row+col)%4===0?'#9bb7bd':'#597b88';fc.fillRect(9+col*29,10+row*27,18,20);fc.strokeStyle='#b2c5c4';fc.lineWidth=1;fc.strokeRect(9+col*29,10+row*27,18,20);fc.fillStyle='#c6d9db';fc.fillRect(12+col*29,13+row*27,3,16)}
  const facadeTexture=new THREE.CanvasTexture(facade);facadeTexture.colorSpace=THREE.SRGBColorSpace
  const wall=new THREE.MeshStandardMaterial({map:facadeTexture,roughness:.72}),roof=new THREE.MeshStandardMaterial({color:'#eef0e5',roughness:.9})
  const boxes=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),[wall,wall,roof,roof,wall,wall],surfaces.buildings.length)
  const roofUnits=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color:'#909d9a',roughness:.85}),surfaces.buildings.length)
  const tones=['#eee6d2','#d6e2e1','#f0ddc3','#d8cab5','#e1e5d6']
  surfaces.buildings.forEach((b,i)=>{dummy.quaternion.copy(basis(b.lon,b.lat)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),b.yaw||0));dummy.position.copy(point(b.lon,b.lat,R+b.h/2));dummy.scale.set(b.w,b.h,b.d);dummy.updateMatrix();boxes.setMatrixAt(i,dummy.matrix);boxes.setColorAt(i,new THREE.Color(tones[b.shade%tones.length]));dummy.position.copy(point(b.lon,b.lat,R+b.h+.7));dummy.scale.set(b.w*.25,1.4,b.d*.4);dummy.updateMatrix();roofUnits.setMatrixAt(i,dummy.matrix)})
  boxes.castShadow=boxes.receiveShadow=true;roofUnits.castShadow=true;details.add(boxes,roofUnits)
  const trunks=new THREE.InstancedMesh(new THREE.CylinderGeometry(.18,.26,1,5),new THREE.MeshStandardMaterial({color:'#776951',roughness:1}),surfaces.trees.length)
  const crowns=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),new THREE.MeshStandardMaterial({roughness:1}),surfaces.trees.length)
  surfaces.trees.forEach((t,i)=>{dummy.quaternion.copy(basis(t.lon,t.lat));dummy.position.copy(point(t.lon,t.lat,R+t.h*.3));dummy.scale.set(1,t.h*.6,1);dummy.updateMatrix();trunks.setMatrixAt(i,dummy.matrix);dummy.position.copy(point(t.lon,t.lat,R+t.h*.75));dummy.scale.set(t.r,t.h*.45,t.r);dummy.updateMatrix();crowns.setMatrixAt(i,dummy.matrix);crowns.setColorAt(i,new THREE.Color(['#689753','#81aa61','#9abb76'][i%3]))})
  crowns.castShadow=true;details.add(trunks,crowns)
  const cars=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({roughness:.4}),surfaces.cars.length)
  surfaces.cars.forEach((c,i)=>{dummy.quaternion.copy(basis(c.lon,c.lat));dummy.position.copy(point(c.lon,c.lat,R+.65));dummy.scale.set(1.15,1.1,2.5);dummy.updateMatrix();cars.setMatrixAt(i,dummy.matrix);cars.setColorAt(i,new THREE.Color(['#e5e4db','#718d9b','#a8b1ad'][c.shade%3]))});cars.castShadow=true;details.add(cars)
  const landmarks=createAreaLandmarks(surfaces.sites,{rawPoint,radius:R,facadeTexture});scene.add(landmarks.group);hitTargets.push(...landmarks.hits)
  const clearance=Math.max(landmarks.maximumHeight,...surfaces.buildings.map(b=>b.h))
  const sceneJump=(a,b,p)=>globeJump(a,b,p,clearance)
  function ribbon(samples,material,radius=R+.08){
    const positions=[],indices=[]
    samples.forEach(([left,right],i)=>{for(const [lon,lat] of [left,right]){const p=point(lon,lat,radius);positions.push(p.x,p.y,p.z)}if(i){const a=(i-1)*2;indices.push(a,a+1,a+2,a+1,a+3,a+2)}})
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setIndex(indices);geometry.computeVertexNormals();const mesh=new THREE.Mesh(geometry,material);mesh.receiveShadow=true;scene.add(mesh);return mesh
  }
  ribbon(Array.from({length:169},(_,i)=>{const lat=-42+i*.5,lon=riverLongitude(lat);return [[lon-1.05,lat],[lon+1.05,lat]]}),new THREE.MeshStandardMaterial({color:'#66b4c7',roughness:.24,metalness:.12,envMapIntensity:.65,side:THREE.DoubleSide}))
  for(const [j,lat] of cityRoadLatitudes.entries()){
    const half=j%4===1?.62:.35,lon=riverLongitude(lat)
    ribbon(Array.from({length:9},(_,i)=>{const l=lon-1.5+i*.375;return [[l,lat-half],[l,lat+half]]}),new THREE.MeshStandardMaterial({color:'#a3acab',roughness:.8,side:THREE.DoubleSide}),R+.65)
    for(const side of [-1,1]){const path=Array.from({length:12},(_,i)=>point(lon-1.5+i/11*3,lat+side*(half+.06),R+.9));scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(path),new THREE.LineBasicMaterial({color:'#e5e2d5'})))}
  }

  const normal=v=>new THREE.Vector3(v.x,v.y,v.z).normalize()
  const orient=(mesh,n,radius)=>{mesh.position.copy(normal(n).multiplyScalar(radius));mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal(n))}
  const heatCanvas=document.createElement('canvas');heatCanvas.width=heatCanvas.height=64
  const hc=heatCanvas.getContext('2d'),g=hc.createRadialGradient(32,32,0,32,32,32)
  g.addColorStop(0,'#ffffffcc');g.addColorStop(1,'#ffffff00');hc.fillStyle=g;hc.fillRect(0,0,64,64)
  const heatTexture=new THREE.CanvasTexture(heatCanvas)
  for(const n of nodes){
    const ball=new THREE.Mesh(new THREE.SphereGeometry(2.8,20,14),new THREE.MeshStandardMaterial({roughness:.3,metalness:.08}))
    ball.position.copy(normal(n).multiplyScalar(R+3));ball.userData={kind:'node',id:n.area_id};scene.add(ball);hitTargets.push(ball)
    const ring=new THREE.Mesh(new THREE.RingGeometry(3,3.45,48),new THREE.MeshBasicMaterial({color:'#f5f6ee',side:THREE.DoubleSide}))
    orient(ring,n,R+.5);scene.add(ring)
    const heat=new THREE.Mesh(new THREE.PlaneGeometry(13,13),new THREE.MeshBasicMaterial({map:heatTexture,transparent:true,opacity:.65,depthWrite:false,side:THREE.DoubleSide}))
    orient(heat,n,R+.3);scene.add(heat);nodeMeshes.push({node:n,ball,ring,heat})
  }
  const neighbourhood=new THREE.Group(),replayGroup=new THREE.Group();scene.add(neighbourhood,replayGroup)
  const neighbourhoodMeshes=[]
  const tracePoints=(a,b)=>Array.from({length:73},(_,i)=>{const p=sceneJump(a,b,i/72*.76);return new THREE.Vector3(p.x,p.y,p.z)})
  for(const edge of layout.edges){
    const a=byId.get(edge.a),b=byId.get(edge.b)
    const line=createSceneLink(tracePoints(a,b),{color:'#42637a',width:1.6,opacity:.42})
    line.userData={kind:'edge',id:edge.id};neighbourhood.add(line);neighbourhoodMeshes.push({edge,line});hitTargets.push(line)
  }
  const traveller=new THREE.Mesh(new THREE.SphereGeometry(3.7,24,16),new THREE.MeshStandardMaterial({color:'#276cce',emissive:'#12346c',emissiveIntensity:.7,roughness:.2,metalness:.1}))
  const landing=new THREE.Mesh(new THREE.RingGeometry(3.2,3.7,48),new THREE.MeshBasicMaterial({color:'#2464b5',transparent:true,side:THREE.DoubleSide}))
  const shadow=new THREE.Mesh(new THREE.PlaneGeometry(9,9),new THREE.MeshBasicMaterial({map:heatTexture,color:'#092a35',transparent:true,opacity:.6,depthWrite:false}))
  replayGroup.add(traveller,landing,shadow);replayGroup.visible=false
  let width=Math.max(1,host.clientWidth),height=Math.max(1,host.clientHeight),frame=0,disposed=false,selected='',hovered=null,risk={},visibleLinks=true,replayState=null,replayEvents=null,replayLines=[]
  let detailLevel=0
  let interactive=false,dragging=false,distance=400,fitDistance=400,transition=null,previousTime=0,zoomAnchor=null
  camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height)
  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2()
  const reduced=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches
  function invalidate(){if(!disposed&&!document.hidden&&!frame)frame=requestAnimationFrame(render)}
  function render(time){
    frame=0;if(disposed)return
    const dt=Math.min(.05,(time-(previousTime||time))/1000);previousTime=time
    let moving=false
    if(transition){
      const t=Math.min(1,(time-transition.start)/650),e=reduced()?1:1-Math.pow(1-t,3)
      controls.target.copy(transition.fromTarget).lerp(transition.toTarget,e)
      camera.position.copy(transition.from).lerp(transition.to,e)
      if(t>=1||reduced())transition=null;else moving=true
    }
    if(!dragging&&!transition&&Math.abs(camera.position.distanceTo(controls.target)-distance)>.015){const length=camera.position.distanceTo(controls.target);camera.position.sub(controls.target).setLength(THREE.MathUtils.lerp(length,distance,reduced()?1:1-Math.exp(-12*(dt||.016)))).add(controls.target);moving=true}
    camera.updateMatrixWorld()
    if(zoomAnchor){
      raycaster.setFromCamera(zoomAnchor.pointer,camera)
      const next=raycaster.intersectObject(globe,false)[0]?.point
      const delta=zoomAnchorShift(zoomAnchor.point,next,12)
      controls.target.add(new THREE.Vector3(delta.x,delta.y,delta.z));camera.position.add(new THREE.Vector3(delta.x,delta.y,delta.z))
      if(Math.abs(camera.position.distanceTo(controls.target)-distance)<=.015)zoomAnchor=null
    }
    if(controls.update())moving=true
    constrainTarget()
    const nextDetail=preview?0:Math.min(quality.detail,mapDetailLevel(camera.position.distanceTo(controls.target),detailLevel))
    if(nextDetail!==detailLevel){detailLevel=nextDetail;landmarks.setDetailLevel(detailLevel)}
    parcelLayer.visible=detailLevel>=1&&!preview
    renderer.render(scene,camera)
    callbacks.onDetail?.(detailLevel)
    callbacks.onProject?.(nodes.map(n=>{const v=normal(n).multiplyScalar(R+2),visible=normal(n).dot(camera.position)>R;v.project(camera);return {...n,left:(v.x+1)*width/2,top:(1-v.y)*height/2,visible:visible&&v.z>-1&&v.z<1}}))
    if(moving)invalidate();else previousTime=0
  }
  function constrainTarget(){const next=clampMapTarget(controls.target,R),delta=new THREE.Vector3(next.x,next.y,next.z).sub(controls.target);if(delta.lengthSq()>.00001){controls.target.add(delta);camera.position.add(delta)}}
  function setInteractive(value){interactive=value;controls.enabled=value;renderer.domElement.style.touchAction=value?'none':'pan-y';renderer.domElement.style.cursor=value?'grab':'default';if(!value){dragging=false;distance=camera.position.distanceTo(controls.target)}invalidate()}
  function fit(resize=false){
    const previous=fitDistance
    // Include all regional landing plazas with room for the UI labels.
    const extentX=Math.max(180,...nodes.map(n=>Math.abs(n.x)+22)),extentZ=Math.max(125,...nodes.map(n=>Math.abs(n.z)+22))
    fitDistance=Math.max(extentX/(Math.tan(rad(camera.fov/2))*camera.aspect),extentZ/Math.tan(rad(camera.fov/2)))*1.12
    fitDistance=Math.min(950,fitDistance)
    distance=resize?THREE.MathUtils.clamp(distance/previous*fitDistance,100,1000):fitDistance
    invalidate()
  }
  function moveCamera(target,nextDistance){zoomAnchor=null;const dir=new THREE.Vector3(0,1.35,1).normalize();distance=THREE.MathUtils.clamp(nextDistance,100,1000);transition={from:camera.position.clone(),to:target.clone().addScaledVector(dir,distance),fromTarget:controls.target.clone(),toTarget:target.clone(),start:performance.now()};invalidate()}
  function reset(){fit();moveCamera(new THREE.Vector3(0,R*.99,0),fitDistance)}
  function face(direction,nextDistance){moveCamera(direction.clone().multiplyScalar(R*.98),nextDistance)}
  function style(){
    const edge=hovered?.kind==='edge'?neighbourhoodMeshes.find(e=>e.edge.id===hovered.id)?.edge:null
    for(const {node,ball,ring,heat} of nodeMeshes){const active=node.area_id===(hovered?.kind==='node'?hovered.id:selected)||[edge?.a,edge?.b].includes(node.area_id);ball.material.color.set(riskColor(risk[node.area_id]?.total_score));ball.scale.setScalar(active?1.2:1);ring.visible=active;heat.material.color.copy(ball.material.color)}
    for(const {line} of neighbourhoodMeshes){line.material.color.set(line.userData.id===hovered?.id?'#215fae':'#456a82');line.material.opacity=line.userData.id===hovered?.id?1:.42}
    if(!replayState)landmarks.highlight(hovered?.kind==='node'?hovered.id:selected)
    neighbourhood.visible=visibleLinks&&!replayState;invalidate()
  }
  function replay(state){
    replayState=state;replayGroup.visible=!!state;neighbourhood.visible=visibleLinks&&!state
    if(!state){landmarks.highlight(selected);invalidate();return}
    if(replayEvents!==state.events){
      for(const {line} of replayLines){replayGroup.remove(line);line.geometry.dispose();line.material.dispose()}
      replayEvents=state.events
      replayLines=replaySegments(state.events,state.chain).flatMap(s=>{const a=byId.get(s.from),b=byId.get(s.to);if(!a||!b)return []
        const line=createSceneLink(tracePoints(a,b),{color:s.related?'#215cc5':'#365d97',width:s.related?3.3:2.6,opacity:.8,dashed:!s.related});replayGroup.add(line);return [{...s,line}]})
    }
    for(const {index,line} of replayLines){line.visible=state.showLinks&&index<=state.index;line.material.opacity=index===state.index?1:.62;revealSceneLink(line,index===state.index?state.progress/.76:1)}
    const to=byId.get(state.events[state.index]?.area_id),from=byId.get(state.events[state.index-1]?.area_id)||to
    landmarks.highlight(to?.area_id||null)
    traveller.visible=landing.visible=shadow.visible=!!to
    if(to){const p=sceneJump(from,to,state.progress);traveller.position.set(p.x,p.y,p.z);orient(shadow,p,R+.35);shadow.scale.setScalar(1+(traveller.position.length()-R-3)/18);orient(landing,to,R+.55);landing.scale.setScalar(1+p.pulse*2);landing.material.opacity=p.landed?1-p.pulse:.8}
    invalidate()
  }
  function hit(event){const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects(hitTargets.filter(o=>o.userData.kind!=='edge'||neighbourhood.visible),false)[0];return hit?.object.userData?.kind?hit.object.userData:null}
  function hover(hit,event){hovered=hit;callbacks.onHover(hit,event);style()}
  let down=null,moved=false;const activePointers=new Set()
  const onDown=e=>{if(!interactive)return;activePointers.add(e.pointerId);down={x:e.clientX,y:e.clientY};moved=activePointers.size>1}
  const onMove=e=>{if(down){if(Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)moved=true;return}hover(hit(e),e)}
  const onUp=e=>{if(down&&!moved&&activePointers.size===1&&e.type!=='pointercancel'){const h=hit(e);if(h?.kind==='node')callbacks.onSelect(h.id)}activePointers.delete(e.pointerId);if(!activePointers.size)down=null}
  const onLeave=e=>hover(null,e)
  const onWheel=e=>{if(!interactive)return;e.preventDefault();e.stopImmediatePropagation();callbacks.onInteract?.();transition=null;const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);camera.updateMatrixWorld();raycaster.setFromCamera(pointer,camera);const ground=raycaster.intersectObject(globe,false)[0]?.point;zoomAnchor=ground?{point:ground.clone(),pointer:pointer.clone()}:null;distance=wheelDistance(distance,e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?height:1),100,1000);invalidate()}
  const onStart=()=>{dragging=true;transition=null;zoomAnchor=null;callbacks.onHover(null);callbacks.onInteract?.()}
  const onEnd=()=>{dragging=false;distance=camera.position.distanceTo(controls.target);invalidate()}
  const onChange=()=>{constrainTarget();if(dragging)distance=camera.position.distanceTo(controls.target);invalidate()}
  const onLost=e=>{e.preventDefault();callbacks.onFailure()}
  renderer.domElement.addEventListener('wheel',onWheel,{capture:true,passive:false})
  renderer.domElement.addEventListener('pointerdown',onDown);renderer.domElement.addEventListener('pointermove',onMove);renderer.domElement.addEventListener('pointerleave',onLeave);renderer.domElement.addEventListener('webglcontextlost',onLost)
  window.addEventListener('pointerup',onUp);window.addEventListener('pointercancel',onUp)
  controls.addEventListener('start',onStart);controls.addEventListener('end',onEnd);controls.addEventListener('change',onChange)
  const onVisibility=()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;previousTime=0}else invalidate()}
  document.addEventListener('visibilitychange',onVisibility)
  const observer=new ResizeObserver(()=>{width=Math.max(1,host.clientWidth);height=Math.max(1,host.clientHeight);renderer.setSize(width,height);for(const {line} of [...neighbourhoodMeshes,...replayLines])line.material.resolution.set(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();fit(true)})
  observer.observe(host);controls.update();setInteractive(false);fit();camera.position.sub(controls.target).setLength(distance).add(controls.target)
  return {
    replay,setInteractive,setDragMode,reset,
    captureView(){return {position:camera.position.toArray(),target:controls.target.toArray(),distance}},
    restoreView(view){camera.position.fromArray(view.position);controls.target.fromArray(view.target);distance=view.distance;controls.update();invalidate()},
    update(next){risk=next.risk;selected=next.selected;visibleLinks=next.links;details.visible=next.buildings;style()},
    zoom(factor){transition=null;zoomAnchor=null;callbacks.onInteract?.();distance=THREE.MathUtils.clamp(distance/factor,100,1000);invalidate()},
    pan(x,z){zoomAnchor=null;const delta=new THREE.Vector3(x,0,z);controls.target.add(delta);camera.position.add(delta);transition=null;constrainTarget();controls.update();invalidate()},
    focus(id){const n=byId.get(id);if(n)face(normal(n),Math.min(fitDistance,230))},
    focusChain(){const chainNodes=[...new Set(replayState?.events.map(e=>e.area_id))].map(id=>byId.get(id)).filter(Boolean);if(!chainNodes.length){reset();return}const center=chainNodes.reduce((v,n)=>v.add(normal(n)),new THREE.Vector3()).normalize();const spread=Math.max(...chainNodes.map(n=>angularDistance(center,n)));face(center,Math.max(170,fitDistance*Math.min(1,.42+spread/.95)))},
    hover(id,event){hover(id?{kind:'node',id}:null,event)},
    dispose(){disposed=true;cancelAnimationFrame(frame);observer.disconnect();controls.dispose();document.removeEventListener('visibilitychange',onVisibility);environment?.dispose();window.removeEventListener('pointerup',onUp);window.removeEventListener('pointercancel',onUp);renderer.domElement.removeEventListener('wheel',onWheel,true);renderer.domElement.removeEventListener('pointerdown',onDown);renderer.domElement.removeEventListener('pointermove',onMove);renderer.domElement.removeEventListener('pointerleave',onLeave);renderer.domElement.removeEventListener('webglcontextlost',onLost);const geometries=new Set(),materials=new Set(),materialTextures=new Set();scene.traverse(o=>{if(o.isInstancedMesh)o.dispose();if(o.geometry)geometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>materials.add(m))});geometries.forEach(g=>g.dispose());materials.forEach(m=>{if(m.map)materialTextures.add(m.map);m.dispose()});materialTextures.forEach(t=>t.dispose());facadeTexture.dispose();Object.values(textures).forEach(t=>t.dispose());heatTexture.dispose();renderer.dispose();renderer.domElement.remove()}
  }
}
