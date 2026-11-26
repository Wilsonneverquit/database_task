<template>
  <div class="map-page">
    <AsyncState :loading="loading" :error="error" :data="mapData" :empty="!!mapData && !areas.length" empty-text="暂无区域坐标或风险数据" @retry="load">
      <div v-if="mapData" class="map-canvas" :class="{'legend-open':legendOpen}">
        <RiskStreetMap ref="streetMap" :areas="areas" :risk="riskByArea" :selected="selectedId" :show-buildings="showBuildings" :show-links="showLinks" :mode="viewMode" :insets="sceneInsets" @select="selectArea" @mode="fallback=$event" />
        <header ref="headingPanel" class="floating map-heading">
          <h2>{{ aggregation==='hour'?'区域逐小时风险分布':'区域日峰值风险分布' }}</h2>
          <el-radio-group v-model="aggregation" size="small" aria-label="地图风险聚合方式" @change="changeAggregation"><el-radio-button value="hour">逐小时</el-radio-button><el-radio-button value="day_peak">日峰值（当日最高）</el-radio-button></el-radio-group>
          <div class="map-range"><el-select :model-value="currentIdx" aria-label="选择观察时段" @change="selectDate"><el-option v-for="(d,i) in dates" :key="d" :label="d" :value="i" /></el-select><span class="muted">{{ activeCount }} 个已评分 · {{ quietCount }} 个暂无消费活动</span></div>
          <div class="view-controls" role="group" aria-label="地图视角与缩放">
            <div class="view-switch"><button :aria-pressed="viewMode==='inclined' && !fallback" :disabled="fallback" @click="viewMode='inclined'">倾斜</button><button :aria-pressed="viewMode==='top' || fallback" @click="viewMode='top'">俯视</button></div>
            <el-button :icon="ZoomOut" aria-label="缩小地图" @click="streetMap?.zoom(1/1.2)" /><el-button :icon="ZoomIn" aria-label="放大地图" @click="streetMap?.zoom(1.2)" /><el-button :icon="RefreshLeft" aria-label="重置地图视角" @click="resetCamera" />
          </div>
          <div class="layer-controls" role="group" aria-label="地图图层"><button :aria-pressed="showBuildings" @click="showBuildings=!showBuildings"><el-icon><OfficeBuilding /></el-icon>街区体块</button><button :aria-pressed="showLinks" @click="showLinks=!showLinks"><el-icon><Connection /></el-icon>空间链路</button><button :aria-pressed="fallback" aria-label="切换二维显示" @click="streetMap?.toggleFlat()">{{ fallback ? '返回三维' : '二维模式' }}</button></div>
          <p class="map-help">拖动平移 · 滚轮缩放<span v-if="!fallback"> · 右键拖动旋转</span></p>
          <details><summary>技术说明与示例范围</summary><p>按区域以红色深浅展示风险等级（颜色越深风险越高），拖动时间轴查看各观察时段的风险分布变化。坐标取自区域表 area_info 的经纬度字段。</p><p>{{ DATA_SOURCE==='real'?'区域中心取所在街道入样场所坐标的均值。':'示例城市（虚构）· 坐标仅用于教学演示。' }}</p><p>街道与链路为教学示意，链路表示空间邻近关系，无方向，不代表人员往来或风险传播。每个热斑表示一个区域的时段指数评分，大小不表示真实覆盖范围。</p></details>
        </header>
        <div class="map-tools" role="toolbar" aria-label="地图快捷工具">
          <el-tooltip content="刷新地图" placement="left"><el-button :icon="Refresh" :loading="loading" type="primary" aria-label="刷新地图" @click="pause();load()" /></el-tooltip>
          <el-tooltip content="区域排行" placement="left"><el-button :icon="Sort" :aria-pressed="rankingOpen" aria-label="切换区域排行" @click="rankingOpen=!rankingOpen" /></el-tooltip>
          <el-tooltip content="风险图例" placement="left"><el-button :icon="InfoFilled" :aria-pressed="legendOpen" aria-label="切换风险图例" @click="legendOpen=!legendOpen" /></el-tooltip>
          <el-tooltip content="恢复最近观察时段" placement="left"><el-button :icon="Aim" aria-label="恢复最近观察时段" @click="resetView" /></el-tooltip>
        </div>
        <aside v-if="rankingOpen" class="floating ranking-panel" aria-label="区域风险排行">
          <div class="panel-title"><h3>区域风险排行</h3><el-button text aria-label="关闭区域排行" @click="rankingOpen=false"><el-icon><Close /></el-icon></el-button></div>
          <p class="muted">按当前时段风险指数排列，点击区域查看依据</p>
          <div class="ranking-scroll"><button v-for="(a,i) in rankedAreas" :key="a.area_id" class="area-row" :class="{'is-selected':selectedId===a.area_id}" :aria-pressed="selectedId===a.area_id" @click="selectArea(a.area_id)"><span class="rank-num num">{{ i+1 }}</span><span class="area-name">{{ a.area_name }}<small>{{ a.risk ? `样本 ${a.risk.sample_size}` : '该时段无研判数据' }}</small></span><span class="area-value"><b class="num">{{ a.risk ? fixed(a.risk.total_score) : '—' }}</b><LevelTag v-if="a.risk" :level="a.risk.risk_level" :status="a.risk.risk_status" /></span></button></div>
        </aside>
        <aside v-if="legendOpen" class="floating legend-panel"><div class="panel-title"><h3>风险图例</h3><el-button text aria-label="关闭风险图例" @click="legendOpen=false"><el-icon><Close /></el-icon></el-button></div><div class="legend"><span class="gradient-bar" /><span>0 → 100 · 中 ≥40 · 高 ≥70</span><i class="gray-dot" /><span>该时段无研判数据</span></div></aside>
        <section v-if="selectedArea" ref="selectionPanel" class="floating selection-panel" aria-live="polite">
          <div class="selection-head"><div><h3>{{ selectedArea.area_name }}</h3><p class="muted">{{ currentDate || '暂无观察时段' }} · {{ selectedArea.area_type_name }}</p></div><LevelTag v-if="selectedArea.risk" :level="selectedArea.risk.risk_level" :status="selectedArea.risk.risk_status" /><el-button text :aria-expanded="detailOpen" aria-label="展开或收起区域详情" @click="detailOpen=!detailOpen"><el-icon><component :is="detailOpen ? 'ArrowDown' : 'ArrowUp'" /></el-icon></el-button></div>
          <div v-if="detailOpen"><template v-if="selectedArea.risk"><div class="selection-facts"><span>时段指数 <b>{{ fixed(selectedArea.risk.total_score) }}</b> 分</span><span v-if="selectedArea.risk.total_score!=null">命中 {{ selectedArea.risk.hit_cnt }} 项</span><span>近三小时消费 {{ selectedArea.risk.sample_size }} 条</span></div><p v-if="selectedArea.risk.status_reason" class="score-explanation">{{ selectedArea.risk.status_reason }}</p><div class="toolbar"><router-link v-if="selectedArea.risk.score_id != null" :to="{name:'risk-detail',params:{scoreId:selectedArea.risk.score_id}}">查看评分依据 →</router-link><router-link :to="{name:'risk',query:{area_id:selectedId,batch_id:selectedArea.risk.batch_id}}">区域评分 →</router-link><router-link v-if="auth.canPage('clues')" :to="{name:'clues',query:{area_id:selectedId}}">区域线索（全部时段） →</router-link></div><router-link :to="{name:'evidence',query:{scope:'area',area_id:selectedId,date:currentDate.slice(0,10)}}">浏览区域证据链 →</router-link><p class="mono muted batch-label">{{ selectedArea.risk.batch_id }}</p></template><p v-else class="muted">该区域该时段无研判数据，可切换观察时段查看。</p></div>
        </section>
        <section class="floating timeline-panel" aria-label="观察时段时间轴">
          <el-button :icon="playing ? VideoPause : VideoPlay" :disabled="dates.length<2" @click="playing ? pause() : play()">{{ playing ? '暂停' : '播放' }}</el-button>
          <div class="timeline-slider"><el-slider v-model="currentIdx" :min="0" :max="Math.max(1,dates.length-1)" :disabled="dates.length<2" :step="1" :marks="dateMarks" :format-tooltip="dateLabel" aria-label="观察时段时间轴" @change="pause" /></div><span class="num">{{ currentDate || '暂无观察时段' }}</span>
        </section>
      </div>
    </AsyncState>
  </div>
</template>
<script setup>
import {computed,nextTick,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {VideoPause,VideoPlay,Refresh,Sort,InfoFilled,Aim,ZoomIn,ZoomOut,RefreshLeft,OfficeBuilding,Connection} from '@element-plus/icons-vue'
import {api,DATA_SOURCE} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {useAuthStore} from '@/stores/auth'
import {fixed} from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import RiskStreetMap from '@/components/RiskStreetMap.vue'
import LevelTag from '@/components/LevelTag.vue'
const auth=useAuthStore()
const aggregation=ref('hour')
const {data:mapData,loading,error,run:load}=useAsync(()=>api.riskMap({aggregation:aggregation.value}))
async function changeAggregation(){pause();currentIdx.value=0;await load();currentIdx.value=Math.max(0,dates.value.length-1)}
const areas=computed(()=>mapData.value?.areas || []), dates=computed(()=>mapData.value?.dates || [])
const currentIdx=ref(0),selectedId=ref(''),playing=ref(false)
const rankingOpen=ref(window.innerWidth > 1200), legendOpen=ref(false), detailOpen=ref(window.innerWidth>600)
const streetMap=ref(null),headingPanel=ref(null),selectionPanel=ref(null)
const showBuildings=ref(true),showLinks=ref(true),viewMode=ref('inclined'),fallback=ref(false)
const sceneInsets=ref({left:420,right:370,top:36,bottom:130})
let panelObserver=null
function measurePanels(){
  const wide=window.innerWidth>1200
  sceneInsets.value=wide ? {left:420,right:rankingOpen.value?370:76,top:36,bottom:140} : {left:20,right:20,top:(headingPanel.value?.offsetHeight||240)+36,bottom:(detailOpen.value?Math.max(180,selectionPanel.value?.offsetHeight||0):60)+146}
}
function resetCamera(){viewMode.value='inclined';nextTick(()=>streetMap.value?.reset())}
let timer=null
function resetView(){pause();currentIdx.value=Math.max(0,dates.value.length-1);selectedId.value=rankedAreas.value[0]?.area_id || '';detailOpen.value=true}
function selectArea(id){pause();selectedId.value=id;detailOpen.value=true;nextTick(()=>streetMap.value?.focusArea(id))}
watch(dates,(d,old)=>{if(d.length && !old?.length)currentIdx.value=d.length-1})
const currentDate=computed(()=>dates.value[currentIdx.value] || '')
const currentRisk=computed(()=>mapData.value?.risk.find((r)=>r.date===currentDate.value))
const riskByArea=computed(()=>Object.fromEntries((currentRisk.value?.areas || []).map((a)=>[a.area_id,a])))
const activeCount=computed(()=>(currentRisk.value?.areas || []).filter(r=>r.total_score!=null).length)
const quietCount=computed(()=>(currentRisk.value?.areas || []).filter(r=>r.risk_status==='no_activity').length)
const rankedAreas=computed(()=>areas.value.map((a)=>({...a,risk:riskByArea.value[a.area_id]})).sort((a,b)=>(b.risk?.total_score ?? -Infinity)-(a.risk?.total_score ?? -Infinity) || a.area_id.localeCompare(b.area_id)))
const selectedArea=computed(()=>rankedAreas.value.find((a)=>a.area_id===selectedId.value))
watch(rankedAreas,(rows)=>{if(!rows.some((a)=>a.area_id===selectedId.value))selectedId.value=rows[0]?.area_id || ''},{immediate:true})
const dateLabel=(i)=>dates.value[i] || ''
const dateMarks=computed(()=>{
  const ids=[0,Math.floor((dates.value.length-1)/2),dates.value.length-1].filter((i)=>i>=0)
  return Object.fromEntries([...new Set(ids)].map((i)=>[i,dates.value[i]?.slice(5)]))
})
function selectDate(i){pause();currentIdx.value=i}
function play(){if(playing.value || dates.value.length<2)return;playing.value=true;timer=setInterval(()=>{currentIdx.value=(currentIdx.value+1)%dates.value.length},1600)}
function pause(){playing.value=false;if(timer){clearInterval(timer);timer=null}}
watch([headingPanel,selectionPanel],()=>{panelObserver?.disconnect();if(headingPanel.value)panelObserver?.observe(headingPanel.value);if(selectionPanel.value)panelObserver?.observe(selectionPanel.value);measurePanels()},{flush:'post'})
watch(rankingOpen,()=>nextTick(measurePanels))
onMounted(()=>{panelObserver=new ResizeObserver(measurePanels);if(headingPanel.value)panelObserver.observe(headingPanel.value);if(selectionPanel.value)panelObserver.observe(selectionPanel.value);window.addEventListener('resize',measurePanels);measurePanels()})
onBeforeUnmount(()=>{pause();panelObserver?.disconnect();window.removeEventListener('resize',measurePanels)})
</script>
<style scoped>
.map-page { height:100%; min-height:680px; }.map-page :deep(> div),.map-page :deep(.el-loading-parent--relative) { height:100%; }.map-canvas { position:relative; height:100%; min-height:680px; background:#eef0eb; overflow:hidden; }.floating { position:absolute; background:#ffffff; border-radius:14px; box-shadow:0 4px 20px #20282e10; padding:20px; }.map-heading { top:16px; left:16px; width:min(480px,calc(100% - 96px)); background:#ffffff; }.map-heading h2 { margin:0 0 12px; font-size:28px; font-weight:500; }.map-range { display:flex; gap:12px; align-items:center; flex-wrap:wrap; font-size:13px; }.map-range .el-select { width:220px; }details { margin-top:12px; font-size:12px; color:var(--text-muted); }summary { cursor:pointer; }details p { line-height:1.7; max-width:65ch; }
.map-tools { position:absolute; top:16px; right:16px; display:flex; flex-direction:column; gap:8px; }.map-tools .el-button { width:44px; height:44px; margin:0; box-shadow:0 1px 4px #20282e0d; }
.panel-title,.selection-head { display:flex; align-items:center; gap:8px; justify-content:space-between; }h3 { font-size:16px; font-weight:500; margin:0; }.ranking-panel { top:16px; right:76px; width:280px; max-height:calc(100% - 160px); display:flex; flex-direction:column; }.ranking-panel > p { font-size:12px; line-height:1.6; margin:8px 0; }.ranking-scroll { overflow:auto; }.area-row { display:flex; width:100%; align-items:center; gap:8px; padding:12px 4px; background:transparent; border:0; border-bottom:1px solid var(--card-border); color:inherit; font:inherit; text-align:left; cursor:pointer; }.area-row:hover,.area-row.is-selected { background:#f0f3ee; }.rank-num { width:16px; color:var(--text-muted); }.area-name { flex:1; }.area-name small { display:block; margin-top:5px; font-size:12px; color:var(--text-muted); }.area-value { display:flex; flex-direction:column; align-items:flex-end; gap:4px; }
.score-explanation{font-size:12px;line-height:1.7;color:var(--text-secondary);margin:12px 0}.selection-panel { bottom:126px; left:16px; width:min(460px,calc(100% - 32px)); }.selection-head p { font-size:12px; margin:6px 0 0; }.selection-facts { display:flex; gap:18px; flex-wrap:wrap; margin:14px 0; }.selection-panel .toolbar { gap:12px; font-size:13px; }.batch-label { margin:12px 0 0; font-size:12px; }.timeline-panel { bottom:16px; left:16px; right:16px; display:flex; align-items:center; gap:24px; min-height:88px; }.timeline-slider { flex:1; min-width:0; padding:0 12px 18px; }.timeline-panel > span { font-size:13px; }.legend-panel { right:76px; bottom:126px; width:260px; }.legend { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:12px; font-size:12px; }.gradient-bar { width:100%; height:10px; background:linear-gradient(to right,#f4e4de,#a84039); }.gray-dot { width:12px; height:12px; background:#dce1dd; border-radius:50%; }
@media(max-width:1000px) { .ranking-panel { top:180px; right:16px; max-height:300px; z-index:2; }.legend-panel { right:16px; bottom:126px; z-index:3; } }
@media(max-width:600px) { .map-heading h2 { font-size:23px; }.map-heading { width:calc(100% - 88px); padding:12px; }.timeline-panel { gap:12px; padding:12px; }.timeline-panel > span { display:none; }.selection-panel { padding:12px; }.map-page,.map-canvas { min-height:720px; }.map-page { overflow:auto; } }
</style>

<style scoped>
.ranking-panel .area-row { min-height:72px; border-radius:6px; }.rank-num { font-family:var(--font-mono); font-size:11px; }.area-value b { font-family:var(--font-data); font-size:20px; font-weight:500; }.area-name { font-size:13px; }.panel-title .el-button { width:32px; min-height:32px; padding:4px; }.map-heading details { border-top:1px solid var(--card-border); padding-top:12px; }.selection-facts b { font-family:var(--font-data); font-size:24px; font-weight:500; }.timeline-panel > span { font-family:var(--font-mono); }.map-tools .el-button { border-color:var(--card-border); }.selection-panel .toolbar { gap:12px 16px; }
.map-heading{width:380px;padding:20px}.map-heading h2{font-size:24px;margin-bottom:12px}.selection-panel{width:380px}.view-controls{display:flex;align-items:center;gap:6px;margin-top:16px}.view-switch{display:flex;background:var(--surface-inset,#ecefed);padding:3px;border-radius:7px;margin-right:auto}.view-switch button,.layer-controls button{border:0;background:transparent;font:inherit;font-size:12px;cursor:pointer;color:var(--text-secondary);border-radius:5px;min-height:30px;padding:4px 12px}.view-switch button[aria-pressed=true]{background:#fff;color:var(--accent-ink);box-shadow:0 1px 3px #20282e12}.view-switch button:disabled{cursor:default;opacity:.5}.view-controls .el-button{width:32px;min-height:32px;height:32px;padding:5px;margin:0}.layer-controls{display:flex;gap:8px;margin-top:10px}.layer-controls button{display:flex;align-items:center;gap:6px;padding:4px 8px;color:var(--text-muted)}.layer-controls button[aria-pressed=true]{color:var(--accent-ink);background:var(--accent-soft,#eef2fb)}.map-help{font-size:11px;line-height:1.7;color:var(--text-muted);margin:10px 0 0}.map-heading details{margin-top:10px;padding-top:10px}.ranking-panel{max-height:calc(100% - 160px)}
@media(max-width:1200px){.map-page,.map-canvas{min-height:980px}.map-heading{width:min(380px,calc(100% - 96px))}.ranking-panel{top:320px;right:16px;max-height:340px;z-index:3}.selection-panel{width:min(460px,calc(100% - 32px))}.legend-panel{z-index:4}}
@media(max-width:600px){.map-heading{width:calc(100% - 88px);padding:12px}.map-heading h2{font-size:21px}.map-range{gap:6px;font-size:11px}.map-range .el-select{width:132px}.view-controls{margin-top:8px}.view-switch button{padding:4px 10px}.map-help{display:none}.selection-panel{padding:12px}.map-page,.map-canvas{min-height:760px}.map-tools .el-button{width:40px;height:40px}.timeline-panel{gap:8px}.layer-controls{gap:5px;margin-top:6px}.layer-controls button{padding:4px 6px}}
.legend-open .ranking-panel{max-height:calc(100% - 310px)}
@media(max-width:1200px){.legend-open .ranking-panel{max-height:190px}}
</style>
