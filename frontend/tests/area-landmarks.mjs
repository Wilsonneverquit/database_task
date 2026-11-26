import assert from 'node:assert/strict'
import {AREA_LANDMARKS,areaLandmark,landmarkSites,anchoredRiver,inverseCityWarp} from '../src/utils/area-landmarks.js'
import {landmarkParts} from '../src/utils/landmark-parts.js'
import {globeJump,spherePoint,GLOBE_RADIUS as R} from '../src/utils/globe-math.js'
assert.equal(AREA_LANDMARKS.length,12)
assert.equal(new Set(AREA_LANDMARKS.map(s=>s.kind)).size,12)
const areas=AREA_LANDMARKS.map((a,i)=>({area_id:a.id,area_name:a.name,cityLon:-35+i*6,cityLat:i%2?10:-10}))
const copy=structuredClone(areas),sites=landmarkSites(areas)
assert.deepEqual(areas,copy)
assert.deepEqual(landmarkSites([...areas].reverse()).reverse(),sites)
for(const site of sites){
  assert.equal(site.profile.name,site.node.area_name)
  assert.ok(site.radius>=3&&site.radius<=6.9)
  const parts=landmarkParts(site.profile.kind)
  assert.ok(parts.boxes.length||parts.paths.length)
  assert.ok(parts.trees.every(t=>Math.hypot(t.x,t.z)>9),'landing plaza must remain free of tree crowns')
}
assert.equal(areaLandmark({area_id:'A05',area_name:'未知片区'}).kind,'generic','an ID alone must not invent a campus')
assert.equal(areaLandmark({area_name:'大学城'}).kind,'campus')
const campus=landmarkParts('campus'),market=landmarkParts('nightmarket'),factory=landmarkParts('industrial')
assert.ok(campus.rings.some(r=>r.b>r.a&&r.color==='#c98068'),'campus needs a visible running track')
assert.equal(market.boxes.filter(b=>b.base===4&&b.w===6.8).length,10,'market needs two rows of stall canopies')
assert.equal(factory.roofs.length,9,'industrial sheds use repeated sawtooth roofs')
assert.ok(landmarkParts('highway').paths.some(p=>p.points.length>20),'highway needs a curved ramp')
const warp=(x,y)=>[x+1.8*Math.sin(y*.065+x*.035)+.6*Math.sin(y*.19),y+1.7*Math.sin(x*.07-y*.04)]
const river=anchoredRiver(sites,warp),site=sites.find(s=>s.profile.kind==='riverside')
const target=[site.node.cityLon-site.radius*.58,site.node.cityLat]
const [x,y]=inverseCityWarp(...target,warp),[actualX,actualY]=warp(river(y),y)
assert.ok(Math.abs(actualX-target[0])<.001&&Math.abs(actualY-target[1])<.001,'river must run beside the riverside landing site')
assert.ok(Math.abs(x-river(y))<.001)
const a=spherePoint(-10,3),b=spherePoint(11,-4)
assert.ok(Math.hypot(...Object.values(globeJump(a,b,.38,80)).slice(0,3))>R+90,'flight must rise above configured landmark clearance')
assert.ok(Math.abs(Math.hypot(...Object.values(globeJump(a,b,1,80)).slice(0,3))-(R+3))<1e-8,'tall buildings must not change the landing position')
console.log('PASS: twelve regional identities, stable bindings, unknown-area fallback, clear plazas, recognisable forms, river anchoring and flight clearance')
