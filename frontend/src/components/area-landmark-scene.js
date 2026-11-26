import * as THREE from 'three'
import {landmarkParts} from '@/utils/landmark-parts'
import {landmarkDetails} from '@/utils/landmark-details'

// Low-detail, recognisable district silhouettes, bent onto the shared city surface.
export function createAreaLandmarks(sites,{rawPoint,radius,facadeTexture}){
  const group=new THREE.Group(),hits=[],outlines=new Map(),dummy=new THREE.Object3D()
  const medium=new THREE.Group(),fine=new THREE.Group();medium.name='district-medium-detail';fine.name='district-fine-detail';medium.visible=fine.visible=false;group.add(medium,fine)
  const material={
    solid:new THREE.MeshStandardMaterial({roughness:.85}),
    facade:new THREE.MeshStandardMaterial({map:facadeTexture,roughness:.82}),
    glass:new THREE.MeshStandardMaterial({map:facadeTexture,roughness:.2,metalness:.18,envMapIntensity:.8}),
    roof:new THREE.MeshStandardMaterial({roughness:.9,flatShading:true,emissive:'#6f817e',emissiveIntensity:.22}),
    trunk:new THREE.MeshStandardMaterial({color:'#8a7e60',roughness:1}),
    foliage:new THREE.MeshStandardMaterial({roughness:1}),
  }
  const boxGeometry=new THREE.BoxGeometry(1,1,1)
  let roofGeometry=new THREE.BufferGeometry()
  const vertices=[[-.5,-.5,-.5],[.5,-.5,-.5],[0,.5,-.5],[-.5,-.5,.5],[.5,-.5,.5],[0,.5,.5]]
  roofGeometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices.flat(),3));roofGeometry.setIndex([0,2,1,3,4,5,0,3,5,0,5,2,2,5,4,2,4,1,0,1,4,0,4,3]);const indexedRoof=roofGeometry;roofGeometry=indexedRoof.toNonIndexed();indexedRoof.dispose();roofGeometry.computeVertexNormals()
  const trunkGeometry=new THREE.CylinderGeometry(.2,.28,1,5),crownGeometry=new THREE.IcosahedronGeometry(1,1)
  let maximumHeight=0
  const deferred=[];let builtLevel=0
  function at(site,x,z,h=0){return rawPoint(site.node.cityLon+x*site.scale/4.887,site.node.cityLat-z*site.scale/4.887,radius+h*site.scale)}
  function basis(site,x,z){const up=at(site,x,z).normalize(),east=at(site,x+1,z).sub(at(site,x-1,z)).normalize(),south=new THREE.Vector3().crossVectors(east,up).normalize();east.crossVectors(up,south).normalize();return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(east,up,south))}
  function batch(site,items,geometry,mat,transform,target=group){
    if(!items.length)return
    const mesh=new THREE.InstancedMesh(geometry,mat,items.length);mesh.userData={kind:'node',id:site.node.area_id};mesh.castShadow=true;mesh.receiveShadow=geometry!==roofGeometry
    items.forEach((item,i)=>{const {x,z,y,w,h,d,color}=transform(item,i);dummy.position.copy(at(site,x,z,y));dummy.quaternion.copy(basis(site,x,z));dummy.scale.set(w*site.scale,h*site.scale,d*site.scale);dummy.updateMatrix();mesh.setMatrixAt(i,dummy.matrix);if(color)mesh.setColorAt(i,new THREE.Color(color))})
    target.add(mesh);if(target===group)hits.push(mesh)
  }
  function surface(site,vertices,indices,color,target=group){
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices.flatMap(([x,z])=>at(site,x,z,.25).toArray()),3));g.setIndex(indices);g.computeVertexNormals()
    const mesh=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color,roughness:.95,side:THREE.DoubleSide}));mesh.receiveShadow=true;target.add(mesh)
  }
  function patch(site,p){const vertices=[],indices=[],steps=5;for(let j=0;j<=steps;j++)for(let i=0;i<=steps;i++){vertices.push([p.x+(i/steps-.5)*p.w,p.z+(j/steps-.5)*p.d]);if(i&&j){const a=(j-1)*(steps+1)+i-1;indices.push(a,a+1,a+steps+1,a+1,a+steps+2,a+steps+1)}}surface(site,vertices,indices,p.color)}
  function path(site,p,target=group){
    const vertices=[],indices=[],points=[]
    p.points.forEach((point,i)=>{if(!i){points.push(point);return}const a=p.points[i-1],count=Math.max(1,Math.ceil(Math.hypot(point[0]-a[0],point[1]-a[1])/5));for(let j=1;j<=count;j++)points.push([a[0]+(point[0]-a[0])*j/count,a[1]+(point[1]-a[1])*j/count])})
    points.forEach(([x,z],i)=>{const before=points[Math.max(0,i-1)],after=points[Math.min(points.length-1,i+1)],dx=after[0]-before[0],dz=after[1]-before[1],length=Math.hypot(dx,dz)||1;for(const side of [-1,1])vertices.push([x-dz/length*p.width/2*side,z+dx/length*p.width/2*side]);if(i){const a=(i-1)*2;indices.push(a,a+1,a+2,a+1,a+3,a+2)}})
    surface(site,vertices,indices,p.color,target)
    if(p.dashed){const centers=points.map(([x,z])=>at(site,x,z,.34));const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(centers),new THREE.LineDashedMaterial({color:'#f0ead2',dashSize:1.2,gapSize:1}));line.computeLineDistances();target.add(line)}
  }
  for(const site of sites){
    const plan=landmarkParts(site.profile.kind)
    for(const p of plan.patches)patch(site,p)
    for(const p of plan.paths)path(site,p)
    for(const r of plan.rings){const v=[],indices=[];for(let i=0;i<=80;i++){const t=i/80*Math.PI*2;v.push([r.x+Math.cos(t)*r.a,r.z+Math.sin(t)*r.b],[r.x+Math.cos(t)*r.innerA,r.z+Math.sin(t)*r.innerB]);if(i){const a=(i-1)*2;indices.push(a,a+1,a+2,a+1,a+3,a+2)}}surface(site,v,indices,r.color)}
    for(const tag of ['solid','facade','glass']){
      const items=plan.boxes.filter(b=>(b.glass?'glass':b.h>5&&b.w>4&&site.profile.kind!=='industrial'?'facade':'solid')===tag)
      batch(site,items,boxGeometry,material[tag],b=>({...b,y:b.base+b.h/2}))
    }
    batch(site,plan.roofs,roofGeometry,material.roof,b=>({...b,y:b.base+b.h/2}))
    batch(site,plan.trees,trunkGeometry,material.trunk,t=>({x:t.x,z:t.z,y:t.h*.3,w:1,h:t.h*.6,d:1}))
    batch(site,plan.trees,crownGeometry,material.foliage,(t,i)=>({x:t.x,z:t.z,y:t.h*.76,w:t.r,h:t.h*.44,d:t.r,color:['#739c57','#90b66f','#5f8f56'][i%3]}))
    deferred.push(level=>{
      const detail=landmarkDetails(site.profile.kind,plan)
      if(level===1){
    batch(site,detail.fixtures,boxGeometry,material.solid,b=>({...b,y:b.base+b.h/2}),medium)
    batch(site,detail.poles,trunkGeometry,material.solid,p=>({x:p.x,z:p.z,y:p.h/2,w:p.r*5,h:p.h,d:p.r*5,color:p.color}),medium)
    for(const p of detail.paths)path(site,p,medium)
      }else{
        batch(site,detail.fine,boxGeometry,material.solid,b=>({...b,y:b.base+b.h/2}),fine)
    if(typeof document!=='undefined')for(const sign of detail.signs){
      const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;const ctx=canvas.getContext('2d');ctx.fillStyle=sign.color;ctx.fillRect(0,0,512,128);ctx.strokeStyle='#e9efdd';ctx.lineWidth=5;ctx.strokeRect(6,6,500,116);ctx.fillStyle='#fffdf0';ctx.font='500 58px "Microsoft YaHei",sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(sign.text,256,66)
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace
      const mesh=new THREE.Mesh(new THREE.PlaneGeometry(Math.max(5,sign.text.length*1.7)*site.scale,1.9*site.scale),new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide}))
      mesh.position.copy(at(site,sign.x,sign.z,sign.y));mesh.quaternion.copy(basis(site,sign.x,sign.z));fine.add(mesh)
    }
      }
    })
    maximumHeight=Math.max(maximumHeight,...plan.boxes.map(b=>(b.base+b.h)*site.scale),...plan.roofs.map(b=>(b.base+b.h)*site.scale))
    const outline=Array.from({length:33},(_,i)=>{const t=i/32*Math.PI*2,r=29*(1+.07*Math.sin(t*3));return at(site,Math.cos(t)*r,Math.sin(t)*r,.42)})
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(outline),new THREE.LineBasicMaterial({color:'#3378aa',transparent:true,opacity:.65}));line.visible=false;group.add(line);outlines.set(site.node.area_id,line)
  }
  let active=null
  return {group,hits,maximumHeight,setDetailLevel(level){for(let next=builtLevel+1;next<=level;next++){deferred.forEach(build=>build(next));builtLevel=next}medium.visible=level>=1;fine.visible=level>=2},highlight(id){if(active===id)return;active=id;for(const [key,line] of outlines)line.visible=key===id}}
}
