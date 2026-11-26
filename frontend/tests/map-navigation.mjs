import assert from 'node:assert/strict'
import {dragBindings,clampMapTarget,mapDetailLevel} from '../src/utils/map-navigation.js'
import {createMapFullscreen} from '../src/utils/map-fullscreen.js'
import {landmarkParts} from '../src/utils/landmark-parts.js'
import {landmarkDetails} from '../src/utils/landmark-details.js'

assert.deepEqual(dragBindings('pan'),{left:'PAN',right:'ROTATE',touch:'PAN'})
assert.deepEqual(dragBindings('rotate'),{left:'ROTATE',right:'PAN',touch:'ROTATE'})
assert.deepEqual(clampMapTarget({x:500,y:900,z:-300},700),{x:235,y:725,z:-160})
assert.deepEqual(clampMapTarget({x:3,y:690,z:4},700),{x:3,y:690,z:4})
assert.equal(mapDetailLevel(420),0);assert.equal(mapDetailLevel(300),1);assert.equal(mapDetailLevel(180),2)
assert.equal(mapDetailLevel(230,2),2);assert.equal(mapDetailLevel(340,0),0)
assert.ok(landmarkDetails('campus',landmarkParts('campus')).paths.length>5,'close campus view includes track lanes and pitch lines')
assert.ok(landmarkDetails('nightmarket',landmarkParts('nightmarket')).fine.length>30,'close market view has stall counters, goods and canopy stripes')

function environment(mode){
  const listeners=new Map(),states=[],doc={body:{style:{overflow:'auto'}},fullscreenElement:null,addEventListener(type,fn){listeners.set(type,fn)},removeEventListener(type){listeners.delete(type)}}
  const emit=type=>listeners.get(type)?.({key:'Escape',preventDefault(){}})
  const element={}
  if(mode==='native')element.requestFullscreen=async()=>{doc.fullscreenElement=element;emit('fullscreenchange')}
  if(mode==='denied')element.requestFullscreen=async()=>{throw new Error('not allowed')}
  doc.exitFullscreen=async()=>{doc.fullscreenElement=null;emit('fullscreenchange')}
  const controller=createMapFullscreen({getElement:()=>element,document:doc,onChange:s=>states.push(s)})
  return {controller,doc,states,listeners,emit,element}
}
for(const mode of ['native','unsupported','denied']){
  const e=environment(mode)
  await e.controller.toggle()
  assert.equal(e.states.at(-1).active,true)
  assert.equal(e.states.at(-1).native,mode==='native')
  assert.equal(e.doc.body.style.overflow,'hidden')
  await e.controller.toggle()
  assert.equal(e.states.at(-1).active,false)
  assert.equal(e.doc.body.style.overflow,'auto')
  await e.controller.toggle()
  if(mode==='native')await e.doc.exitFullscreen();else e.emit('keydown')
  assert.equal(e.states.at(-1).active,false,'Esc/native exit must restore normal layout')
  await e.controller.toggle();e.controller.dispose()
  assert.equal(e.doc.body.style.overflow,'auto');assert.equal(e.listeners.size,0)
}
const late=environment('native');let resolveRequest
late.element.requestFullscreen=()=>new Promise(resolve=>{resolveRequest=()=>{late.doc.fullscreenElement=late.element;resolve()}})
const entering=late.controller.toggle();late.controller.dispose();resolveRequest();await entering
assert.equal(late.doc.fullscreenElement,null,'pending fullscreen request must not trap a departed page')
const cancelled=environment('native')
cancelled.element.requestFullscreen=async()=>{cancelled.doc.fullscreenElement=cancelled.element;cancelled.emit('fullscreenchange');await cancelled.doc.exitFullscreen()}
await cancelled.controller.toggle()
assert.equal(cancelled.states.at(-1).active,false,'an immediate user exit must not reopen viewport fullscreen')
cancelled.controller.dispose()
console.log('PASS: pan/rotate bindings, bounded translation, zoom detail levels, native/denied/unsupported fullscreen, Esc exit and unmount cleanup')
