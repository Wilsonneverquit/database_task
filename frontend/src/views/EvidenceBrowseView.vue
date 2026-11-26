<template>
  <div class="page evidence-browser">
    <div class="page-head"><div><h2>证据链浏览</h2><p class="sub">先选区域或人员，再选有线索关联的消费事件，追溯原始记录。</p></div><el-radio-group v-model="scope" aria-label="证据链浏览范围" @change="resetScope"><el-radio-button value="area">按区域</el-radio-button><el-radio-button value="person">按人员</el-radio-button></el-radio-group></div>
    <div class="toolbar"><el-input v-model="keyword" :placeholder="scope==='area'?'区域编号或名称':'人员编号，支持部分输入'" clearable aria-label="搜索证据链对象" style="width:250px" @change="searchSubjects" @keyup.enter="searchSubjects" /><el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="事件起始日期" end-placeholder="事件结束日期" range-separator="至" @change="searchSubjects" /><el-button @click="clearFilters">清空筛选</el-button></div>
    <div class="evidence-layout">
      <aside class="subject-panel" aria-label="证据链对象列表"><div class="panel-heading"><h3>{{ scope==='area'?'区域':'人员' }}</h3><span class="muted">{{ subjects.data.value?.total || 0 }} 个有事件的对象</span></div>
        <AsyncState :data="subjects.data.value" :loading="subjects.loading.value" :error="subjects.error.value" empty-text="没有匹配对象，可清空关键词或调整日期" @retry="subjects.run"><div v-if="subjects.data.value" class="subject-list"><button v-for="s in subjects.data.value.list" :key="s.subject_id" :aria-pressed="selectedId===s.subject_id" :class="{selected:selectedId===s.subject_id}" @click="selectSubject(s.subject_id)"><strong>{{ s.label }}</strong><span>{{ s.event_count }} 个事件</span><small>关联线索峰值 {{ fixed(s.peak_score) }}</small></button></div></AsyncState>
        <el-pagination v-if="subjects.data.value?.total>12" v-model:current-page="subjectPage" :total="subjects.data.value.total" :page-size="12" layout="prev,pager,next" small @current-change="subjects.run" />
      </aside>
      <section class="event-workspace">
        <el-card shadow="never"><template #header><div class="card-title">{{ selectedSubject?.label || selectedId || '选择区域或人员' }}<span class="hint">{{ events.data.value?.total || 0 }} 个消费事件 · 重复快照已合并</span></div></template>
          <AsyncState :data="events.data.value" :loading="events.loading.value" :error="events.error.value" empty-text="该范围暂无事件，请选择其他对象或调整日期" @retry="events.run"><div v-if="events.data.value" class="event-list"><button v-for="e in events.data.value.list" :key="e.chain_id" :aria-pressed="active?.chain_id===e.chain_id" :class="{selected:active?.chain_id===e.chain_id}" @click="selectEvent(e)"><span>{{ e.event_at }}</span><strong>{{ e.person_id }} · {{ e.area_name }}</strong><span>{{ e.object_type===1?'区域线索':'人员线索' }} · 快照分 {{ fixed(e.total_score) }} · {{ e.snapshot_count }} 份快照</span></button></div></AsyncState>
          <el-pagination v-if="events.data.value?.total>8" v-model:current-page="eventPage" :total="events.data.value.total" :page-size="8" layout="total,prev,pager,next" small @current-change="events.run" />
        </el-card>
        <el-card v-if="active" ref="detailPanel" shadow="never"><EvidenceChain split-sources @source="activeSource=$event" :key="active.chain_id" :clue-id="active.clue_id" :chain-id="active.chain_id" /><div class="toolbar"><router-link :to="{name:'clue-detail',params:{clueId:active.clue_id}}">进入来源线索与核查记录 →</router-link><span class="muted small">此事件选取截至 {{ active.snapshot_at }} 的最新快照</span></div></el-card>
      </section>
      <EvidenceSource :source="activeSource" />
    </div>
  </div>
</template>
<script setup>
import {computed,ref,watch,nextTick} from 'vue'
import {useRoute} from 'vue-router'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {fixed,halfOpenRange} from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import EvidenceChain from '@/components/EvidenceChain.vue'
import EvidenceSource from '@/components/EvidenceSource.vue'
const route=useRoute()
const scope=ref(route.query.scope==='person'?'person':'area'),keyword=ref(String(route.query.area_id||route.query.person_id||''))
const dateRange=ref(route.query.date?[String(route.query.date),String(route.query.date)]:[])
const selectedId=ref(''),subjectPage=ref(1),eventPage=ref(1),active=ref(null)
const detailPanel=ref(null),activeSource=ref(null)
watch(active,()=>{activeSource.value=null})
const subjects=useAsync(()=>api.evidenceSubjects({scope:scope.value,q:keyword.value,...halfOpenRange(dateRange.value),page:subjectPage.value,size:12}))
const events=useAsync(()=>selectedId.value?api.evidenceEvents({scope:scope.value,[scope.value==='area'?'area_id':'person_id']:selectedId.value,...halfOpenRange(dateRange.value),page:eventPage.value,size:8}):Promise.resolve({list:[],total:0,scope:scope.value}),{immediate:false})
const selectedSubject=computed(()=>subjects.data.value?.list.find(s=>s.subject_id===selectedId.value))
watch(()=>route.query,q=>{scope.value=q.scope==='person'?'person':'area';keyword.value=String(q.area_id||q.person_id||'');dateRange.value=q.date?[String(q.date),String(q.date)]:[];searchSubjects()})
watch(()=>subjects.data.value,d=>{if(d?.scope!==scope.value)return;if(d.list.length)selectSubject(d.list[0].subject_id);else{selectedId.value='';active.value=null;events.run()}})
watch(()=>events.data.value,d=>{if(d?.scope===scope.value)active.value=d.list[0]||null})
function selectSubject(id){selectedId.value=id;active.value=null;eventPage.value=1;events.run()}
async function selectEvent(event){active.value=event;await nextTick();detailPanel.value?.$el.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})}
function searchSubjects(){selectedId.value='';active.value=null;subjectPage.value=1;subjects.run()}
function resetScope(){keyword.value='';searchSubjects()}
function clearFilters(){keyword.value='';dateRange.value=[];searchSubjects()}
</script>
<style scoped>
.evidence-layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:24px;align-items:start}.subject-panel{background:var(--surface);border:1px solid var(--card-border);border-radius:12px;padding:20px}.panel-heading{display:flex;flex-direction:column;gap:8px;margin-bottom:16px}.panel-heading h3{font-size:16px;font-weight:500;margin:0}.panel-heading span,.small{font-size:12px}.subject-list,.event-workspace{display:grid;gap:16px}.subject-list{gap:4px;max-height:420px;overflow:auto}.subject-list button,.event-list button{display:grid;gap:8px;text-align:left;background:transparent;border:1px solid transparent;border-radius:8px;color:var(--text-primary);padding:12px;cursor:pointer;min-width:0}.subject-list button.selected,.event-list button.selected{background:var(--accent-soft);border-color:var(--accent)}.subject-list strong,.event-list strong{font-weight:500}.subject-list span,.subject-list small,.event-list span{font-size:12px;color:var(--text-muted)}.event-list{max-height:280px;overflow:auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.el-pagination{margin-top:16px}.event-workspace>.el-card>.el-card__body>.toolbar{margin-top:16px}.card-title{justify-content:space-between}@media(max-width:1000px){.evidence-layout{grid-template-columns:minmax(0,1fr)}.subject-list{grid-template-columns:repeat(3,minmax(0,1fr));max-height:180px}}@media(max-width:600px){.subject-list,.event-list{grid-template-columns:repeat(2,minmax(0,1fr))}.subject-panel{padding:12px}.event-list button{padding:10px}.toolbar .el-date-editor{max-width:100%}}
.evidence-layout{grid-template-columns:200px minmax(360px,1fr) 290px;gap:20px}.subject-panel{position:sticky;top:0;padding:16px}.event-list{grid-template-columns:1fr;max-height:240px;gap:4px}.event-list button{padding:12px;border-bottom:1px solid var(--border-soft);border-radius:6px}.event-list button:hover,.subject-list button:hover{background:var(--surface-raised)}.subject-list{max-height:calc(100dvh - 360px)}.event-workspace{min-width:0}.event-workspace :deep(.evidence-track){padding-right:16px}.event-workspace :deep(.el-card__body){padding:20px}
@media(max-width:1100px){.evidence-layout{grid-template-columns:200px minmax(0,1fr)}.subject-panel{grid-row:1 / 3}}
@media(max-width:800px){.evidence-layout{grid-template-columns:1fr}.subject-panel{position:static;grid-row:auto}.subject-list{grid-template-columns:repeat(2,minmax(0,1fr));max-height:200px}.event-list{grid-template-columns:1fr}.event-workspace :deep(.el-card__body){padding:16px}}
</style>
