<template>
  <div ref="root" class="street-map" :class="{interacting:interactive,preview:preview}" tabindex="0" aria-label="城市弧面风险地图，方向键平移，加减键缩放，Esc恢复页面滚动" @keydown="onKey">
    <div v-if="!preview" class="globe-controls">
      <button class="interaction-button" :aria-pressed="interactive" @click="setInteractive(!interactive)">{{ interactive?'退出操作 · Esc':'操作地图' }}</button>
      <button :aria-pressed="dragMode==='pan'" @click="setDragMode('pan')">平移</button><button :aria-pressed="dragMode==='rotate'" :disabled="fallback" @click="setDragMode('rotate')">旋转</button>
      <button @click="emit('fullscreen')">{{fullscreen?'退出全屏':'全屏地图'}}</button>
      <button aria-label="缩小地图" @click="zoom(1/1.2)"><el-icon><ZoomOut/></el-icon></button><button aria-label="放大地图" @click="zoom(1.2)"><el-icon><ZoomIn/></el-icon></button>
      <button @click="reset">查看全貌</button><button v-if="replayEnabled" @click="scene?.focusChain()">聚焦当前链</button><button v-else :disabled="!selected" @click="focusArea(selected)">区域近景</button>
      <button :aria-pressed="showLabels" @click="showLabels=!showLabels">地名</button>
      <button :aria-pressed="fallback" @click="toggleFlat">{{fallback?'返回三维':'二维回退'}}</button>
      <label class="quality-control">画质<select v-model="quality" aria-label="地图画质" @change="changeQuality"><option v-for="(q,key) in MAP_QUALITY" :key="key" :value="key">{{q.label}}</option></select></label>
      <span>{{interactive?(fallback?'拖动平移 · 滚轮缩放':dragMode==='pan'?'左键平移 · 右键旋转 · 滚轮缩放':'左键旋转 · 右键平移 · 滚轮缩放'):'上下滑动页面 · 开启操作后缩放地图'}}</span>
    </div>
    <div ref="viewport" class="scene-viewport">
    <div v-show="!fallback" ref="host" class="scene-host" />
    <svg v-if="fallback" class="flat-map" :viewBox="flatViewBox" aria-label="二维街区风险地图" @pointerdown="flatDown" @pointermove="flatMove" @pointerup="flatUp" @pointercancel="flatUp" @wheel="flatWheel">
      <defs><radialGradient id="street-heat"><stop offset="0" stop-color="#fff" stop-opacity=".7" /><stop offset="1" stop-color="#fff" stop-opacity="0" /></radialGradient><mask id="street-heat-mask" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#street-heat)" /></mask><radialGradient id="street-sphere" cx="30%" cy="25%" r="80%"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset=".35" stop-color="#fff" stop-opacity=".08"/><stop offset="1" stop-color="#17282e" stop-opacity=".45"/></radialGradient></defs>
      <rect x="-1000" y="-1000" width="2000" height="2000" fill="#e9ede7" />
      <image :href="mapTextureUrl" x="-360" y="-360" width="720" height="720" />
      <g v-if="showBuildings" fill="#c3cec1"><rect v-for="(b,i) in layout.buildings" :key="i" :x="b.x-b.w/2" :y="b.z-b.d/2" :width="b.w" :height="b.d" /></g>
      <g v-for="n in layout.nodes" :key="`landmark-${n.area_id}`" :transform="`translate(${n.x} ${n.z})`"><AreaLandmarkSymbol :area="n"/></g>
      <g v-if="showLinks && !replayEnabled" fill="none" stroke-width=".6"><path v-for="e in layout.edges" :key="e.id" :d="flatPath(e)" :stroke="edgeActive(e) ? '#345fc5' : '#80949c'" :opacity="edgeActive(e) ? 1 : .5" @pointerenter="edgeHover(e,$event)" @pointerleave="clearHover" /></g>
      <g v-for="n in layout.nodes" :key="n.area_id" :transform="`translate(${n.x} ${n.z})`" :style="{color:riskColor(risk[n.area_id]?.total_score)}" @pointerenter="nodeHover(n.area_id,$event)" @pointerleave="clearHover">
        <circle v-if="risk[n.area_id]" r="11" fill="currentColor" mask="url(#street-heat-mask)" />
        <circle v-if="selected===n.area_id" r="3.6" fill="none" stroke="#345fc5" stroke-width=".6" />
        <ellipse cy="1.8" rx="3.2" ry="1.3" fill="#334736" opacity=".16" /><circle r="3.5" fill="currentColor"/><circle r="3.5" fill="url(#street-sphere)" stroke="#79897a" stroke-width=".2" />
      </g>
      <g v-if="flatReplay && flatReplay.showLinks" fill="none" stroke="#345fc5" stroke-width=".6"><path v-for="(line,i) in flatReplayLines" :key="i" :d="replayPath(line)" :stroke-dasharray="line.related?undefined:'1.2 1'" opacity=".6" /></g>
      <g v-if="flatTraveller" style="color:var(--accent-ink)"><ellipse :cx="flatTraveller.x" :cy="flatTraveller.z" rx="4" ry="1.5" fill="#334736" opacity=".2"/><circle :cx="flatTraveller.x" :cy="flatTraveller.z-(flatTraveller.y-3.5)*.5" r="4" fill="currentColor"/><circle :cx="flatTraveller.x" :cy="flatTraveller.z-(flatTraveller.y-3.5)*.5" r="4" fill="url(#street-sphere)"/><circle v-if="flatTraveller.landed" :cx="flatTraveller.x" :cy="flatTraveller.z" :r="3.5+flatTraveller.pulse*7" fill="none" stroke="#345fc5" :opacity="1-flatTraveller.pulse" stroke-width=".5"/></g>
    </svg>
    <div v-show="showLabels" class="map-labels">
      <button v-for="n in labels" :key="n.area_id" class="map-label" :class="{'is-selected':selected===n.area_id}" :style="{left:`${n.left}px`,top:`${n.top}px`}" :aria-pressed="selected===n.area_id" :aria-label="`${n.area_name}，${risk[n.area_id] ? risk[n.area_id].total_score==null ? (risk[n.area_id].status_label || '未评分') : `${fixed(risk[n.area_id].total_score)}分` : '当前时段无研判记录'}`" @click="emit('select',n.area_id)" @pointerenter="nodeHover(n.area_id,$event)" @pointerleave="clearHover" @focus="nodeHover(n.area_id,$event)" @blur="clearHover">{{ n.area_name }}<b v-if="selected===n.area_id && risk[n.area_id]">{{ risk[n.area_id].total_score==null?'未评分':fixed(risk[n.area_id].total_score) }}</b></button>
    </div>
    <div v-if="hover" class="map-point-tip" role="tooltip" :style="tipStyle">
      <template v-if="hover.kind==='node'"><strong>{{ hoverNode?.area_name }}</strong><span>{{areaLandmark(hoverNode).short}} · 教学场景</span><template v-if="hoverRisk"><span>{{ hoverRisk.total_score==null ? (hoverRisk.status_label || '未评分') : `${hoverRisk.risk_level_name}风险 · ${fixed(hoverRisk.total_score)} 分` }}</span><span>近三小时消费 {{ hoverRisk.sample_size }} 条<span v-if="hoverRisk.total_score!=null"> · 命中 {{ hoverRisk.hit_cnt }} 项</span></span></template><span v-else>当前时段无研判记录</span></template>
      <template v-else><strong>{{ hoverEdgeNames }}</strong><span>空间邻近示意 · 无方向连接</span></template>
    </div>
    <div v-if="displayArea && !preview" class="area-scene-note" aria-live="polite"><span>{{replayEnabled?scenePhase:'当前区域'}} · 区域级示意</span><strong>{{displayArea.area_name}}</strong><p>{{areaLandmark(displayArea).short}}</p></div>
    <div class="scene-status"><span v-if="!preview">{{detailLevel===2?'近景细节':detailLevel===1?'街区视图':'城市概览'}}</span><span>{{ fallback ? '二维区域图' : '城市弧面' }}</span><span>虚构城市 · 街区及位置均为教学示意</span></div>
    <div v-if="fallback" class="fallback-note"  role="status">{{ fallbackReason }}<button @click="start">重试三维</button></div>
    <div v-if="starting" class="scene-loading" role="status">正在渲染立体城市街区…</div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { streetLayout, riskColor, edgeHeight } from '@/utils/street-map'
import {mapTextureUrl} from '@/utils/map-cartography'
import {jumpPoint,replaySegments} from '@/utils/clue-replay'
import { fixed } from '@/utils/format'
import {ZoomIn,ZoomOut} from '@element-plus/icons-vue'
import {areaLandmark} from '@/utils/area-landmarks'
import AreaLandmarkSymbol from './AreaLandmarkSymbol.vue'
import {MAP_QUALITY,initialMapQuality,placeMapLabels} from '@/utils/map-presentation'
const props=defineProps({areas:{type:Array,required:true},risk:{type:Object,required:true},selected:{type:String,default:''},showBuildings:{type:Boolean,default:true},showLinks:{type:Boolean,default:true},mode:{type:String,default:'inclined'},insets:{type:Object,default:()=>({})},replayEnabled:{type:Boolean,default:false},fullscreen:{type:Boolean,default:false},preview:{type:Boolean,default:false}})
const emit=defineEmits(['select','mode','interact','fullscreen'])
let savedQuality
try{savedQuality=localStorage.getItem('risk_map_quality')}catch{}
const quality=ref(props.preview?'smooth':initialMapQuality({width:window.innerWidth,memory:navigator.deviceMemory||8,cores:navigator.hardwareConcurrency||8,saved:savedQuality})),detailLevel=ref(0)
const dragMode=ref('pan')
const interactive=ref(false),viewport=ref(null),showLabels=ref(true),sceneAreaId=ref(''),scenePhase=ref('')
const displayArea=computed(()=>props.areas.find(a=>a.area_id===(props.replayEnabled?sceneAreaId.value:props.selected)))
const root=ref(null),host=ref(null),projected=ref([]),fallback=ref(false),starting=ref(true),hover=ref(null),tipPosition=ref({x:0,y:0})
const fallbackReason=ref('当前设备暂无法显示三维，已保留二维地图与全部业务操作。')
const layout=computed(()=>streetLayout(props.areas))
const size=ref({w:1000,h:700}),flatCamera=ref({x:0,z:0,zoom:1})
let scene=null,observer=null,disposed=false,generation=0
let latestReplay=null
const flatReplay=shallowRef(null)
function setReplayFrame(state){latestReplay=state;sceneAreaId.value=state?.events[state.index]?.area_id||'';scenePhase.value=state?.progress<.76?'下一落点':'当前落点';if(fallback.value)flatReplay.value=state;else scene?.replay(state)}
const flatReplayLines=computed(()=>flatReplay.value?replaySegments(flatReplay.value.events,flatReplay.value.chain).filter(e=>e.index<=flatReplay.value.index):[])
const flatTraveller=computed(()=>{const s=flatReplay.value;if(!s)return null;const b=layout.value.nodes.find(n=>n.area_id===s.events[s.index]?.area_id),a=layout.value.nodes.find(n=>n.area_id===s.events[s.index-1]?.area_id);return b?jumpPoint(a||b,b,s.progress):null})
function replayPath(line){const a=layout.value.nodes.find(n=>n.area_id===line.from),b=layout.value.nodes.find(n=>n.area_id===line.to);return a&&b?`M ${a.x} ${a.z} Q ${(a.x+b.x)/2} ${(a.z+b.z)/2-edgeHeight(Math.hypot(a.x-b.x,a.z-b.z))*.45} ${b.x} ${b.z}`:''}
const flatDimensions=computed(()=>{
  const {w,h}=size.value,{left=24,right=24,top=24,bottom=24}=props.insets
  const fullH=Math.max(202*h/Math.max(180,h-top-bottom),202*h/Math.max(180,w-left-right))/flatCamera.value.zoom
  const fullW=fullH*w/h
  return {w:fullW,h:fullH,x:-fullW/2+flatCamera.value.x-(left-right)/w*fullW/2,z:-fullH/2+flatCamera.value.z-(top-bottom)/h*fullH/2}
})
const flatViewBox=computed(()=>{const d=flatDimensions.value;return `${d.x} ${d.z} ${d.w} ${d.h}`})
const positions=computed(()=>fallback.value ? layout.value.nodes.map((n)=>{const d=flatDimensions.value;return {...n,left:(n.x-d.x)/d.w*size.value.w,top:(n.z-d.z)/d.h*size.value.h,visible:true}}) : projected.value)
// Fixed ID order keeps label placement stable when night scores change.
const labels=computed(()=>placeMapLabels(positions.value,{width:size.value.w,height:size.value.h,selected:props.selected,landing:sceneAreaId.value,detail:detailLevel.value,preview:props.preview}))
const hoverNode=computed(()=>layout.value.nodes.find((n)=>n.area_id===hover.value?.id))
const hoverRisk=computed(()=>props.risk[hover.value?.id])
const hoverEdgeNames=computed(()=>{const e=layout.value.edges.find((e)=>e.id===hover.value?.id);return e ? [e.a,e.b].map((id)=>layout.value.nodes.find((n)=>n.area_id===id)?.area_name).join(' — ') : ''})
const tipStyle=computed(()=>({left:`${Math.max(8,Math.min(size.value.w-260,tipPosition.value.x+16))}px`,top:`${Math.max(8,Math.min(size.value.h-112,tipPosition.value.y-98))}px`}))
function receiveHover(value,event){
  hover.value=value
  if(!value)return
  const rect=viewport.value.getBoundingClientRect()
  if(event?.clientX != null && event.type!=='focus')tipPosition.value={x:event.clientX-rect.left,y:event.clientY-rect.top}
  else {const p=positions.value.find((n)=>n.area_id===value.id);tipPosition.value={x:p?.left||rect.width/2,y:p?.top||rect.height/2}}
}
function nodeHover(id,event){if(scene)scene.hover(id,event);else receiveHover({kind:'node',id},event)}
function edgeHover(e,event){receiveHover({kind:'edge',id:e.id},event)}
function clearHover(){if(scene)scene.hover(null);else hover.value=null}
function edgeActive(e){return e.id===hover.value?.id || e.a===props.selected || e.b===props.selected}
function flatPath(e){const a=layout.value.nodes.find((n)=>n.area_id===e.a),b=layout.value.nodes.find((n)=>n.area_id===e.b);return `M ${a.x} ${a.z} Q ${(a.x+b.x)/2} ${(a.z+b.z)/2-edgeHeight(e.distance)*.45} ${b.x} ${b.z}`}
function updateScene(){scene?.update({risk:props.risk,selected:props.selected,buildings:props.showBuildings,links:props.showLinks,mode:props.mode,insets:props.insets})}
function useFallback(){generation++;scene?.dispose();scene=null;fallback.value=true;flatReplay.value=latestReplay;starting.value=false;hover.value=null;emit('mode',true)}
function toggleFlat(){if(fallback.value)start();else {fallbackReason.value='已切换二维模式，支持拖动、双指缩放和区域选择。';useFallback()}}
async function start(){
  const current=++generation
  const previousView=scene?.captureView();scene?.dispose();scene=null;fallback.value=false;starting.value=true;hover.value=null
  fallbackReason.value='当前设备暂无法显示三维，已保留二维地图与全部业务操作。'
  await nextTick()
  try {
    const {createStreetScene}=await import('./street-scene')
    if(disposed||current!==generation)return
    scene=createStreetScene(host.value,layout.value,{onProject:(rows)=>{projected.value=rows},onHover:receiveHover,onSelect:(id)=>emit('select',id),onFailure:useFallback,onInteract:()=>emit('interact'),onDetail:level=>{detailLevel.value=level}},{quality:quality.value,preview:props.preview})
    updateScene();if(previousView)scene.restoreView(previousView);scene.setDragMode(dragMode.value);scene.setInteractive(interactive.value);scene.replay(latestReplay);starting.value=false;emit('mode',false)
  }catch {if(!disposed&&current===generation)useFallback()}
}
function changeQuality(){try{localStorage.setItem('risk_map_quality',quality.value)}catch{}start()}
function setDragMode(value){dragMode.value=value;scene?.setDragMode(value);if(!interactive.value)setInteractive(true);else emit('interact')}
function setInteractive(value){interactive.value=value;scene?.setInteractive(value)}
function reset(){hover.value=null;flatCamera.value={x:0,z:0,zoom:1};scene?.reset()}
function zoom(factor){if(scene)scene.zoom(factor);else flatCamera.value={...flatCamera.value,zoom:Math.max(.6,Math.min(3.5,flatCamera.value.zoom*factor))}}
function focusArea(id){if(scene)scene.focus(id);else {const n=layout.value.nodes.find((n)=>n.area_id===id);if(n)flatCamera.value={...flatCamera.value,x:n.x*.45,z:n.z*.45}}}
function pan(x,z){if(scene)scene.pan(x,z);else flatCamera.value={...flatCamera.value,x:flatCamera.value.x+x,z:flatCamera.value.z+z}}
function onKey(e){
  if(e.key==='Escape'){setInteractive(false);return}
  if(e.target!==root.value)return
  const actions={ArrowLeft:()=>pan(-8,0),ArrowRight:()=>pan(8,0),ArrowUp:()=>pan(0,-8),ArrowDown:()=>pan(0,8),'+':()=>zoom(1.2),'=':()=>zoom(1.2),'-':()=>zoom(1/1.2),Home:reset}
  if(actions[e.key]){e.preventDefault();emit('interact');actions[e.key]()}
}
const pointers=new Map();let flatGesture=null
function flatDown(e){
  if(!interactive.value)return
  emit('interact')
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});e.currentTarget.setPointerCapture(e.pointerId)
  flatGesture={camera:{...flatCamera.value},points:[...pointers.values()],moved:false,start:{x:e.clientX,y:e.clientY}}
  hover.value=null
}
function flatMove(e){
  if(!pointers.has(e.pointerId)||!flatGesture)return
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const points=[...pointers.values()],start=flatGesture.points
  if(points.length===2&&start.length===2){const ratio=Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y)/Math.max(1,Math.hypot(start[0].x-start[1].x,start[0].y-start[1].y));flatCamera.value={...flatGesture.camera,zoom:Math.max(.6,Math.min(3.5,flatGesture.camera.zoom*ratio))};flatGesture.moved=true}
  else if(points.length===1&&start.length===1){const dx=points[0].x-start[0].x,dy=points[0].y-start[0].y,d=flatDimensions.value;flatCamera.value={...flatCamera.value,x:flatGesture.camera.x-dx*d.w/size.value.w,z:flatGesture.camera.z-dy*d.h/size.value.h};if(Math.hypot(dx,dy)>5)flatGesture.moved=true}
}
function flatUp(e){
  if(flatGesture&&!flatGesture.moved&&pointers.size===1&&e.type!=='pointercancel'){
    const rect=viewport.value.getBoundingClientRect(),p=positions.value.find((n)=>Math.hypot(n.left-(e.clientX-rect.left),n.top-(e.clientY-rect.top))<16)
    if(p)emit('select',p.area_id)
  }
  pointers.delete(e.pointerId);flatGesture=null
}
function flatWheel(e){if(!interactive.value)return;e.preventDefault();emit('interact');const delta=e.deltaY*(e.deltaMode===1?16:1);zoom(Math.exp(-Math.max(-160,Math.min(160,delta))*.002))}
watch(()=>[props.risk,props.selected,props.showBuildings,props.showLinks,props.mode,props.insets],()=>{hover.value=null;updateScene()},{deep:true})
watch(layout,()=>{if(!fallback.value)start()})
onMounted(()=>{observer=new ResizeObserver(()=>{size.value={w:viewport.value.clientWidth,h:viewport.value.clientHeight}});observer.observe(viewport.value);start()})
onBeforeUnmount(()=>{disposed=true;generation++;observer?.disconnect();scene?.dispose()})
defineExpose({reset,zoom,focusArea,toggleFlat,setReplayFrame,setInteractive})
</script>

<style scoped>
.street-map{position:relative;display:flex;flex-direction:column;background:var(--surface-inset);border-radius:12px;overflow:hidden;min-width:0;outline-offset:-3px}.globe-controls{display:flex;align-items:center;gap:5px;flex-wrap:wrap;padding:10px 12px;background:var(--surface);color:#e5f0f4;flex-shrink:0}.globe-controls button{border:0;background:var(--surface-raised);border-radius:5px;color:inherit;font:12px var(--font-ui);padding:7px 9px;cursor:pointer;min-height:32px;display:inline-flex;align-items:center;gap:4px}.globe-controls button[aria-pressed=true]{background:var(--accent-soft);color:var(--accent-ink)}.globe-controls button:hover{background:#2b4565}.globe-controls button:disabled{opacity:.5}.globe-controls .interaction-button{background:var(--accent);color:#081322}.globe-controls .interaction-button[aria-pressed=true]{background:var(--cyan);color:#081322}.globe-controls>span{font-size:10px;color:#bdd0d8;margin-left:auto}.scene-viewport{position:relative;flex:1;min-height:0;overflow:hidden}.scene-host,.flat-map,.map-labels{position:absolute;inset:0;width:100%;height:100%}.scene-host :deep(canvas){display:block}.flat-map{touch-action:pan-y}.interacting .flat-map{touch-action:none;cursor:grab}.map-labels{pointer-events:none;overflow:hidden}.map-label{position:absolute;transform:translateX(-50%);pointer-events:auto;white-space:nowrap;background:#13243bf2;border:1px solid #506d90;border-radius:4px;padding:3px 7px;color:#f0f6f7;font:12px/1.5 var(--font-ui);cursor:pointer}.map-label:hover,.map-label.is-selected{background:#254b74;color:#f0f6f7}.map-label b{margin-left:7px;font-family:var(--font-data);font-weight:500}.map-point-tip{position:absolute;z-index:5;pointer-events:none;display:flex;flex-direction:column;gap:5px;max-width:250px;background:var(--surface-raised);padding:12px 16px;border-radius:10px;box-shadow:0 5px 20px #0b17251a;font-size:12px;line-height:1.6}.map-point-tip strong{font-size:13px;font-weight:500}.map-point-tip span{color:var(--text-secondary)}.scene-status{position:absolute;left:14px;bottom:12px;display:flex;gap:10px;pointer-events:none;color:#d2e3ea;font-size:10px;line-height:1.7;flex-wrap:wrap}.scene-status span{background:#132e3bd9;padding:2px 6px;border-radius:3px}.fallback-note{position:absolute;left:12px;top:12px;right:12px;width:fit-content;max-width:calc(100% - 24px);padding:8px 12px;background:var(--surface-raised);font-size:11px;line-height:1.8;border-radius:8px}.fallback-note button{background:transparent;border:0;color:var(--accent-ink);cursor:pointer;padding:4px 8px;font:inherit}.scene-loading{position:absolute;left:50%;top:45%;transform:translate(-50%,-50%);background:var(--surface-raised);padding:12px 18px;border-radius:10px;font-size:13px;white-space:nowrap}
@media(max-width:600px){.map-label{font-size:10px;padding:2px 4px}.globe-controls{gap:4px;padding:8px}.globe-controls button{padding:6px 8px;font-size:11px}.globe-controls>span{margin-left:0;flex-basis:100%;line-height:1.6}.scene-status{gap:4px;left:8px;bottom:8px}.map-point-tip{max-width:220px}}
.area-scene-note{position:absolute;left:14px;bottom:45px;max-width:260px;padding:10px 13px;background:#15253bf2;border-radius:8px;color:var(--text-primary);pointer-events:none;box-shadow:0 3px 10px #263a3e14}.area-scene-note>span{display:block;font-size:10px;color:var(--text-muted)}.area-scene-note strong{display:block;font-weight:500;font-size:15px;margin-top:4px}.area-scene-note p{font-size:11px;margin:4px 0 0;line-height:1.7}@media(max-width:600px){.area-scene-note{bottom:42px;left:8px;max-width:220px;padding:8px 10px}.area-scene-note strong{font-size:13px}.area-scene-note p{font-size:10px}}
.quality-control{display:inline-flex;align-items:center;gap:6px;font-size:12px;margin-left:4px}.quality-control select{background:var(--surface-raised);color:var(--text-primary);border:1px solid var(--card-border);border-radius:5px;min-height:32px;padding:4px 6px}.preview .scene-status{font-size:10px}.preview{min-height:320px}.preview .map-point-tip{font-size:12px}.preview .scene-status span{background:#13243bf2}
</style>
