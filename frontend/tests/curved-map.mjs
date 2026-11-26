import assert from 'node:assert/strict'
import {spherePoint,globeLayout,globeJump,angularDistance,wheelDistance,GLOBE_RADIUS as R,jumpDuration} from '../src/utils/globe-math.js'
const input=[{area_id:'A',lng:1,lat:2,x:-82,z:-82},{area_id:'B',lng:2,lat:1,x:82,z:82}]
const original=structuredClone(input),nodes=globeLayout(input)
assert.deepEqual(input,original)
assert.deepEqual(globeLayout([...input].reverse()).reverse(),nodes)
assert.ok(nodes[0].displayLon<0&&nodes[0].displayLat>0)
assert.ok(nodes[1].displayLon>0&&nodes[1].displayLat<0)
assert.notEqual(Math.hypot(nodes[0].cityLon,nodes[0].cityLat),Math.hypot(nodes[1].cityLon,nodes[1].cityLat))
for(const n of nodes)assert.ok(Math.abs(Math.hypot(n.x,n.y,n.z)-R)<1e-8)
assert.ok(Math.abs(nodes[1].x-nodes[0].x)>R*.25)
assert.ok(spherePoint(0,0).y>spherePoint(24,16.8).y,'the city surface must bulge upwards')
assert.ok(spherePoint(0,0,R-5).y<spherePoint(0,0).y,'the concave underside stays below the ground')
const a=spherePoint(-35,20),b=spherePoint(32,-20)
for(let i=0;i<=100;i++){
  const p=globeJump(a,b,i/100)
  assert.ok(Math.hypot(p.x,p.y,p.z)>=R+3-1e-8,'flight must not tunnel through the curved map')
}
const end=globeJump(a,b,1)
assert.ok(angularDistance(end,b)<1e-7,'landing must use the original destination direction')
assert.ok(Math.abs(Math.hypot(end.x,end.y,end.z)-(R+3))<1e-8)
assert.ok(angularDistance(globeJump(a,a,.4),a)<1e-7)
assert.ok(jumpDuration(a,b)>jumpDuration(a,a))
assert.ok(wheelDistance(350,-1)<350&&wheelDistance(350,1)>350)
assert.equal(wheelDistance(130,-10000),130);assert.equal(wheelDistance(650,10000),650)
console.log('PASS: stable curved coordinates, broad coverage, exact spherical landing, surface clearance, same-location bounce, bounded continuous zoom')
