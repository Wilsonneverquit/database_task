import assert from 'node:assert/strict'
import {createServer} from 'vite'
import {fileURLToPath} from 'node:url'
import * as THREE from 'three'
import {AREA_LANDMARKS,landmarkSites} from '../src/utils/area-landmarks.js'
import {streetLayout} from '../src/utils/street-map.js'
import {globeLayout,globeJump,spherePoint,GLOBE_RADIUS as R} from '../src/utils/globe-math.js'

const areas=AREA_LANDMARKS.map((p,i)=>({area_id:p.id,area_name:p.name,lng:118.85+.045*Math.cos(i*Math.PI/6),lat:31.6+.035*Math.sin(i*Math.PI/6)}))
const nodes=globeLayout(streetLayout(areas).nodes),sites=landmarkSites(nodes)
const vite=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),configFile:fileURLToPath(new URL('../vite.config.js',import.meta.url)),server:{middlewareMode:true},appType:'custom'})
let model
try {
  const {createAreaLandmarks}=await vite.ssrLoadModule('/src/components/area-landmark-scene.js')
  model=createAreaLandmarks(sites,{rawPoint:(lon,lat,radius)=>{const p=spherePoint(lon*.4,lat*.4,radius);return new THREE.Vector3(p.x,p.y,p.z)},radius:R,facadeTexture:null})
  assert.equal(new Set(model.hits.map(m=>m.userData.id)).size,12)
  const medium=model.group.getObjectByName('district-medium-detail'),fine=model.group.getObjectByName('district-fine-detail')
  assert.equal(medium.children.length,0,'defer medium detail until it is requested')
  assert.equal(fine.children.length,0,'defer fine detail and signs until close viewing')
  model.setDetailLevel(0);assert.equal(medium.visible,false);assert.equal(fine.visible,false)
  model.setDetailLevel(1);assert.equal(medium.visible,true);assert.equal(fine.visible,false)
  model.setDetailLevel(2);assert.equal(medium.visible,true);assert.equal(fine.visible,true)
  assert.ok(medium.children.length>20&&fine.children.length>10,'requested zoom layers contain actual extra geometry')
  const builtCount=fine.children.length;model.setDetailLevel(0);model.setDetailLevel(2);assert.equal(fine.children.length,builtCount,'zooming again reuses detail instead of duplicating meshes')
  assert.equal(model.group.visible,true,'primary landmarks must remain visible at every zoom')
  const obstacles=[],matrix=new THREE.Matrix4(),inverse=new THREE.Matrix4()
  model.group.traverse(mesh=>{
    if(!mesh.geometry)return
    const positions=mesh.geometry.attributes.position.array
    assert.ok([...positions].every(Number.isFinite))
    if(!mesh.isInstancedMesh||mesh.geometry.type!=='BoxGeometry')return
    for(let i=0;i<mesh.count;i++){
      mesh.getMatrixAt(i,matrix);inverse.copy(matrix).invert()
      const scale=new THREE.Vector3().setFromMatrixScale(matrix)
      assert.ok(scale.x>0&&scale.y>0&&scale.z>0)
      obstacles.push({inverse:inverse.clone(),scale,id:mesh.userData.id})
    }
  })
  const local=new THREE.Vector3(),collisions=[]
  for(const a of nodes)for(const b of nodes){
    if(a===b)continue
    for(let step=0;step<=100;step++){
      const p=globeJump(a,b,step/100*.76,Math.max(40,model.maximumHeight))
      for(const o of obstacles){
        local.set(p.x,p.y,p.z).applyMatrix4(o.inverse)
        const dx=Math.max(0,Math.abs(local.x)-.5)*o.scale.x,dy=Math.max(0,Math.abs(local.y)-.5)*o.scale.y,dz=Math.max(0,Math.abs(local.z)-.5)*o.scale.z
        if(dx*dx+dy*dy+dz*dz<3.7**2){collisions.push(`${a.area_id}->${b.area_id}:${step}:${o.id}`);break}
      }
    }
  }
  assert.equal(collisions.length,0,`Flight intersects landmark buildings: ${collisions.slice(0,8).join(', ')}`)
  console.log('PASS: all twelve district meshes have finite geometry; 132 directed flights avoid landmark buildings')
} finally {
  if(model){const geometries=new Set(),materials=new Set();model.group.traverse(mesh=>{if(mesh.isInstancedMesh)mesh.dispose();if(mesh.geometry)geometries.add(mesh.geometry);if(mesh.material)(Array.isArray(mesh.material)?mesh.material:[mesh.material]).forEach(m=>materials.add(m))});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())}
  await vite.close()
}
