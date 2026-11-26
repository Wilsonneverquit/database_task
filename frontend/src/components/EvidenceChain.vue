<template>
  <section class="evidence-chain" aria-label="研判事件链">
    <AsyncState :loading="loading" :error="error" :data="data" @retry="load">
      <template v-if="data">
        <div class="chain-heading"><div><h3>证据时间轴</h3><p class="muted">原始记录、关联推断与人工确认分别标识，可逐项追溯。</p></div>
          <el-select v-if="chains.length>1" v-model="selected" aria-label="选择当前线索关联事件"><el-option v-for="c in chains" :key="c.chain_id" :value="c.chain_id" :label="eventLabel(c)" /></el-select>
          <span v-else-if="active" class="single-event">{{ eventLabel(active) }}</span>
        </div>
        <div class="chain-scope"><span>{{ data.context?.object_type===1 ? `区域线索 · ${data.context.area_name || data.context.area_id}` : `人员线索 · ${data.context?.person_id || active?.person_id || ''}` }} · 当前线索关联 {{ data.chains.length }} 个事件</span><router-link :to="browseLink">浏览其他区域 / 人员事件 →</router-link></div>
        <el-empty v-if="!active" description="此线索尚无人员事件链，请查看评分明细或补充核查" :image-size="60" />
        <template v-else>
          <p class="chain-context"><span class="mono">{{ active.person_id }}</span><router-link :to="{name:'people',query:{person_id:active.person_id}}">查看人员流水 →</router-link><span>快照截至 {{ active.snapshot_at }}</span></p>
          <el-timeline class="evidence-track">
            <el-timeline-item v-for="n in active.nodes" :key="n.node_id" :timestamp="n.event_at" placement="top" :type="nodeType[n.certainty] || 'primary'" :hollow="n.certainty==='association'">
              <div class="event-title"><strong>{{ n.title }}</strong><el-tag size="small" :type="nodeType[n.certainty] || 'info'">{{ certainty[n.certainty] }}</el-tag></div>
              <p>{{ n.explanation }}</p>
              <el-button v-if="splitSources" class="source-action" link type="primary" @click="chooseSource(n)">查看来源 <el-icon><ArrowRight /></el-icon></el-button><el-collapse v-else><el-collapse-item title="来源与关联理由" :name="n.node_id"><p class="mono">{{ source(n) }}</p><dl v-if="n.source_record" class="source-record"><template v-for="(value,key) in n.source_record" :key="key"><dt>{{ key }}</dt><dd>{{ value ?? '—' }}</dd></template></dl><p v-if="n.driver_record">独立观察 #{{ n.driver_record.evidence_id }} · {{ n.driver_record.source_type }} · 观察时间 {{ n.driver_record.observed_at }} · 入库 {{ n.driver_record.recorded_at }}</p><p v-for="e in active.edges.filter(e=>e.to_node===n.node_id)" :key="e.edge_id">{{ e.reason }}</p><el-button v-if="n.score_id" link type="primary" @click="$router.push({name:'risk-detail',params:{scoreId:n.score_id}})">打开评分解释</el-button></el-collapse-item></el-collapse>
            </el-timeline-item>
            <el-timeline-item v-for="f in data.feedbacks" :key="`f${f.feedback_id}`" :timestamp="f.check_time" placement="top" type="success"><strong>人工核查：{{ {1:'已确认',2:'已排除',3:'无法核实'}[f.check_result] }}</strong><p>{{ f.check_remark }}</p></el-timeline-item>
          </el-timeline>
        </template>
        <p class="muted chain-note">{{ data.note }}</p>
      </template>
    </AsyncState>
  </section>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import AsyncState from './AsyncState.vue'
const props=defineProps({clueId:{type:String,required:true},chainId:{type:[Number,String],default:null},splitSources:{type:Boolean,default:false}})
const emit=defineEmits(['source'])
function chooseSource(node){emit('source',{node,edges:active.value?.edges.filter(e=>e.to_node===node.node_id)||[]})}
const selected=ref(null)
const {data,loading,error,run:load}=useAsync(()=>api.chain(props.clueId),{immediate:false})
watch(()=>props.clueId,()=>load(),{immediate:true})
const chains=computed(()=>props.chainId!=null ? (data.value?.chains || []).filter(c=>String(c.chain_id)===String(props.chainId)) : data.value?.chains || [])
watch(chains,rows=>{if(!rows.some(c=>c.chain_id===selected.value))selected.value=rows[0]?.chain_id ?? null},{immediate:true})
const active=computed(()=>chains.value.find(c=>c.chain_id===selected.value))
watch(active,value=>{if(props.splitSources)emit('source',value?.nodes.length?{node:value.nodes[0],edges:value.edges.filter(e=>e.to_node===value.nodes[0].node_id)}:null)},{immediate:true})
const eventLabel=c=>`${c.person_id} · ${(c.nodes.find(n=>n.node_type==='consume')?.event_at || c.snapshot_at).slice(5,16)}`
const browseLink=computed(()=>({name:'evidence',query:data.value?.context?.object_type===1?{scope:'area',area_id:data.value.context.area_id}:{scope:'person',person_id:active.value?.person_id || data.value?.context?.person_id}}))
const certainty={record:'原始记录',association:'关联推断 · 待核实',confirmed:'独立观察记录',counterexample:'反例',missing:'证据缺口'}
const nodeType={record:'primary',association:'warning',confirmed:'success',counterexample:'success',missing:'info'}
const source=n=>n.consume_id?`consume_record.consume_id = ${n.consume_id}`:n.track_id?`vehicle_track.track_id = ${n.track_id}`:n.order_id?`taxi_order.order_id = ${n.order_id}`:n.score_id?`risk_score.score_id = ${n.score_id}`:'截至快照时刻尚无对应记录'
</script>
<style scoped>
.single-event{font-size:13px;color:var(--text-secondary)}.chain-scope{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;margin:12px 0;font-size:12px;color:var(--text-muted)}.chain-heading,.chain-context{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.chain-heading h3{margin:0;font-size:18px;font-weight:500}.chain-heading p,.chain-note{font-size:12px;line-height:1.7}.chain-heading .el-select{width:min(100%,320px)}.chain-context{padding:16px 0;margin-bottom:16px;border-bottom:1px solid var(--card-border);font-size:12px}.event-title{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.event-title strong{font-weight:500}.el-timeline{padding-left:8px}.el-timeline p{line-height:1.8}.el-collapse{border:0}.evidence-chain{min-width:0}.source-record{display:grid;grid-template-columns:minmax(90px,1fr) 2fr;gap:8px;font-size:12px}.source-record dt{color:var(--text-muted)}.source-record dd{margin:0;overflow-wrap:anywhere}

/* The grid belongs only to the temporal evidence workspace, never the page background. */
.evidence-track{padding:22px 20px 4px 28px;border:1px solid var(--border-soft);border-radius:10px;background-color:var(--surface-inset);background-image:linear-gradient(#30415a26 1px,transparent 1px),linear-gradient(90deg,#30415a26 1px,transparent 1px);background-size:32px 32px}
.evidence-track :deep(.el-timeline-item__tail){border-left-color:#3a526f}.evidence-track :deep(.el-timeline-item__node){box-shadow:0 0 0 4px var(--surface-inset)}.evidence-track :deep(.el-collapse-item__wrap){background:transparent}.evidence-track :deep(.el-collapse-item__header){height:auto;min-height:36px;font-size:12px}.source-record{padding:14px;background:var(--surface);border-radius:8px}.chain-note{max-width:75ch}.event-title strong{color:var(--text-primary)}
@media(max-width:600px){.evidence-track{padding:16px 12px 0 18px}.source-record{grid-template-columns:minmax(80px,.8fr) minmax(0,1.3fr);padding:10px}.chain-heading h3{font-size:17px}}
</style>
