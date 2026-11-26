import assert from 'node:assert/strict'
import {jumpPoint,chronological,replaySegments} from '../src/utils/clue-replay.js'
const from={x:1,z:2},to={x:10,z:20}
assert.deepEqual(jumpPoint(from,to,1),{x:10,z:20,y:3.5,landed:true,pulse:1})
assert.ok(jumpPoint(from,to,.4).y>3.5)
assert.equal(jumpPoint(from,from,.4).x,from.x)
assert.ok(jumpPoint(from,from,.4).y>3.5)
const events=[{event_id:'2',event_at:'2026-11-24 12:00:00',area_id:'A02'},{event_id:'1',event_at:'2026-11-24 11:00:00',area_id:'A01'},{event_id:'3',event_at:'2026-11-24 12:00:00',area_id:null},{event_id:'4',event_at:'2026-11-24 13:00:00',area_id:'A03'}]
const sorted=chronological(events)
assert.equal(events[0].event_id,'2')
assert.equal(sorted[0].event_id,'1')
assert.equal(replaySegments(sorted).length,1)
assert.equal(replaySegments(sorted)[0].related,false)
assert.equal(replaySegments(sorted,true)[0].related,true)
assert.equal(replaySegments([sorted[0],{...sorted[0],event_id:'5'}]).length,0)
const simultaneous=[{node_id:9,event_id:'9',event_at:'2026-11-24 12:00:00',area_id:'A02'},{node_id:9,event_id:'9:start',event_at:'2026-11-24 12:00:00',area_id:'A01'}]
assert.equal(chronological(simultaneous)[0].event_id,'9:start')
assert.equal(replaySegments(chronological(simultaneous),true)[0].simultaneous,true)
console.log('PASS: chronological replay, same-place jump, exact landing, no path across unlocated nodes')
