<template>
  <div class="page workbench">
    <div class="page-head"><div><p class="eyebrow">数据驱动 · 证据可追溯</p><h2>研判工作台</h2><p class="sub">{{ DATA_SOURCE==='real' ? '公开订单与场所来自独立数据集。可在数据管理中查阅原始记录和来源。' : '从区域异常找到人员事件，再沿原始记录核查。' }} <router-link v-if="DATA_SOURCE==='real' && auth.canPage('data')" to="/data">查看公开数据 →</router-link></p></div><el-button @click="refresh">刷新工作台</el-button></div>
    <AsyncState :loading="summary.loading.value" :error="summary.error.value" :data="summary.data.value" @retry="summary.run"><template v-if="summary.data.value">
      <div class="stat-grid"><div class="stat"><div class="label">累计生成线索</div><div class="value">{{ summary.data.value.clue_total }}</div><div class="foot">所有成功批次</div></div><div class="stat"><div class="label">待核查 / 核查中</div><div class="value">{{ summary.data.value.clue_open }} <small>/ {{ summary.data.value.clue_checking }}</small></div><div class="foot">需要人工处理</div></div><div class="stat"><div class="label">已完成核查</div><div class="value">{{ summary.data.value.clue_confirmed + summary.data.value.clue_excluded }}</div><div class="foot">确认 {{ summary.data.value.clue_confirmed }} · 排除 {{ summary.data.value.clue_excluded }}</div></div><div class="stat"><div class="label">风险指数</div><div class="value">0–100</div><div class="foot">连续因子 · 40 / 70 分级 · 非发生概率</div></div></div>
    </template></AsyncState>
    <template v-if="auth.canPage('risk')"><div class="view-paths"><router-link to="/evidence"><b>01</b><span>研判链路<small>评分解释与人工核查</small></span></router-link><router-link to="/risk-map"><b>02</b><span>区域态势<small>逐小时分布与时间回放</small></span></router-link><router-link to="/people"><b>03</b><span>人员风险<small>消费、出行和车辆记录</small></span></router-link></div>
      <div class="workbench-grid"><el-card shadow="never"><template #header><div class="card-title">优先核查<span class="hint">最近生成的待核查线索</span><router-link to="/clues">全部线索 →</router-link></div></template><AsyncState :data="queue.data.value" :loading="queue.loading.value" :error="queue.error.value" @retry="queue.run"><div v-if="queue.data.value?.list.length" class="work-queue"><button v-for="c in queue.data.value.list" :key="c.clue_id" :class="{selected:clueId===c.clue_id}" @click="clueId=c.clue_id"><div><LevelTag :level="c.risk_level" /><b>{{ fixed(c.total_score) }}</b></div><strong>{{ c.object_type===2?c.object_id:c.area_name }}</strong><span>{{ c.window_start }}</span><span class="mono">{{ c.clue_id }}</span></button></div></AsyncState></el-card>
      <el-card shadow="never"><EvidenceChain v-if="clueId" :key="clueId" :clue-id="clueId" /><el-empty v-else description="当前没有待核查线索" /><router-link v-if="clueId" :to="{name:'clue-detail',params:{clueId}}">进入线索详情并核查 →</router-link></el-card></div>
      <el-card shadow="never"><template #header><div class="card-title">区域 × 小时风险矩阵<span class="hint">单日单批次 · 北京时间</span><el-select v-model="batchId" aria-label="选择区域研判批次" style="width:240px" @change="risk.run"><el-option v-for="b in batches.data.value||[]" :key="b.batch_id" :label="b.data_start.slice(0,10)" :value="b.batch_id" /></el-select></div></template><AsyncState :data="risk.data.value" :loading="risk.loading.value" :error="risk.error.value" @retry="risk.run"><RiskHeatmap v-if="risk.data.value?.length" :rows="risk.data.value" :rule="{low_threshold:40,high_threshold:70}" /></AsyncState></el-card>
    </template>
    <el-card v-else shadow="never"><div class="card-title">管理入口</div><div class="toolbar" style="margin-top:20px"><router-link v-for="e in entries" :key="e.path" :to="e.path">{{ e.title }} →</router-link></div></el-card>
  </div>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {api,DATA_SOURCE} from '@/api'
import {useAuthStore} from '@/stores/auth'
import {useAsync} from '@/composables/useAsync'
import {allPages} from '@/utils/dashboard'
import {fixed} from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import RiskHeatmap from '@/components/RiskHeatmap.vue'
import EvidenceChain from '@/components/EvidenceChain.vue'
import LevelTag from '@/components/LevelTag.vue'
const auth=useAuthStore(),clueId=ref(''),batchId=ref('')
const summary=useAsync(()=>api.overview())
const queue=useAsync(()=>auth.canPage('clues')?api.clues({status:0,order:'latest',size:5}):Promise.resolve({list:[]}))
const batches=useAsync(async()=>auth.canPage('risk')?(await allPages(api.batches,{run_status:2})).filter(b=>b.judge_object===1):[])
const risk=useAsync(()=>batchId.value?allPages(api.regionRisk,{batch_id:batchId.value}):Promise.resolve([]),{immediate:false})
watch(()=>queue.data.value,q=>{if(q?.list.length&&!clueId.value)clueId.value=q.list[0].clue_id})
watch(()=>batches.data.value,b=>{if(b?.length&&!batchId.value){batchId.value=b[0].batch_id;risk.run()}})
const entries=computed(()=>[{path:'/data',page:'data',title:'数据管理'},{path:'/features',page:'features',title:'特征与统计'},{path:'/ops',page:'ops',title:'版本与批次'},{path:'/admin',page:'admin',title:'系统管理'},{path:'/audit',page:'audit',title:'审计日志'}].filter(e=>auth.canPage(e.page)))
function refresh(){summary.run();if(auth.canPage('risk')){queue.run();batches.run();risk.run()}}
</script>
<style scoped>
.workbench .stat-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.eyebrow{font-size:12px;color:var(--accent-ink);letter-spacing:2px;margin:0 0 8px}.stat .value small{font-size:20px;color:var(--text-muted)}.view-paths{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}.view-paths a{display:flex;gap:16px;align-items:center;text-decoration:none;padding:16px 0;border-top:1px solid var(--card-border);color:var(--text-primary)}.view-paths b{font-family:var(--font-mono);font-size:20px;font-weight:400;color:var(--accent-ink)}.view-paths small{display:block;color:var(--text-muted);font-size:12px;margin-top:8px}.workbench-grid{display:grid;grid-template-columns:minmax(240px,.7fr) minmax(0,1.6fr);gap:24px;align-items:start}.work-queue{display:grid;gap:4px}.work-queue button{display:grid;gap:10px;text-align:left;padding:16px;background:transparent;border:1px solid transparent;border-radius:8px;cursor:pointer;color:var(--text-primary)}.work-queue button.selected{background:var(--accent-soft);border-color:var(--card-border)}.work-queue button div{display:flex;justify-content:space-between;align-items:center}.work-queue button b{font-size:24px;font-family:var(--font-data);font-weight:500}.work-queue button strong{font-size:14px;font-weight:500}.work-queue button>span{font-size:12px;color:var(--text-muted)}.card-title{justify-content:space-between}.card-title a{font-size:12px}.workbench-grid>.el-card:last-child{min-height:480px}@media(max-width:1100px){.workbench .stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:1000px){.workbench-grid{grid-template-columns:minmax(0,1fr)}.work-queue{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}}@media(max-width:600px){.view-paths{grid-template-columns:1fr;gap:8px}}
</style>
