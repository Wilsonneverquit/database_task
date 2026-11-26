import assert from 'node:assert/strict'
import {MAP_QUALITY,initialMapQuality,placeMapLabels,zoomAnchorShift} from '../src/utils/map-presentation.js'
import {createSceneLink,revealSceneLink} from '../src/components/scene-links.js'

assert.equal(initialMapQuality({width:390}),'smooth')
assert.equal(initialMapQuality({memory:2}),'smooth')
assert.equal(initialMapQuality({saved:'fine',width:390}),'fine','honor an explicit quality choice')
assert.equal(initialMapQuality({saved:'invalid'}),'standard')
assert.ok(MAP_QUALITY.smooth.textureSize<MAP_QUALITY.fine.textureSize)
const rows=Array.from({length:12},(_,i)=>({area_id:`A${i}`,area_name:'示例街区',left:150+(i%4)*130,top:80+Math.floor(i/4)*110,visible:true}))
const options={width:800,height:480,selected:'A2',landing:'A3',detail:0}
const labels=placeMapLabels(rows,options)
assert.equal(labels[0].area_id,'A3','landing labels receive first claim on space')
assert.deepEqual(labels,placeMapLabels(rows.slice().reverse(),options),'input order does not shuffle labels')
for(const a of labels){
  assert.ok(a.box.left>=8&&a.box.right<=792&&a.box.top>=8&&a.box.bottom<=470)
  for(const b of labels)if(a!==b)assert.ok(a.box.right<=b.box.left||b.box.right<=a.box.left||a.box.bottom<=b.box.top||b.box.bottom<=a.box.top)
}
assert.deepEqual(placeMapLabels(rows,{...options,preview:true}),[])
assert.deepEqual(zoomAnchorShift({x:6,y:2,z:3},{x:1,y:1,z:1}),{x:5,y:1,z:2})
assert.deepEqual(zoomAnchorShift(null,null),{x:0,y:0,z:0})
assert.ok(Math.hypot(...Object.values(zoomAnchorShift({x:500,y:500,z:500},{x:0,y:0,z:0},12)))<=12.00001)
const line=createSceneLink([{x:0,y:0,z:0},{x:2,y:3,z:0},{x:4,y:0,z:0}],{width:3.3,dashed:true})
try{
  assert.ok(line.isLine2);assert.equal(line.material.linewidth,3.3);assert.equal(line.material.dashed,true)
  revealSceneLink(line,0);assert.equal(line.geometry.instanceCount,0)
  revealSceneLink(line,.5);assert.equal(line.geometry.instanceCount,1)
  revealSceneLink(line,2);assert.equal(line.geometry.instanceCount,2)
}finally{line.geometry.dispose();line.material.dispose()}
console.log('PASS: quality selection, stable non-overlapping labels, bounded cursor anchor and progressive wide links')
