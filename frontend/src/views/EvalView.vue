<template>
  <div class="page eval-page">
    <div class="page-head">
      <div><h2>评估报告</h2><p class="sub">用观察段埋入的评估标签（eval_label）对照研判结果。标签只在评估时关联，研判过程绝不读取。</p></div>
      <div class="heading-range"><label for="eval-batch">评估批次</label><el-select id="eval-batch" v-model="batchId" placeholder="全部批次" clearable filterable aria-label="评估批次" @change="changeBatch"><el-option v-for="b in batches.data.value || []" :key="b.batch_id" :label="b.batch_id" :value="b.batch_id" /></el-select></div>
    </div>
    <AsyncState :loading="report.loading.value" :error="report.error.value" :data="report.data.value" @retry="report.run">
      <div v-if="report.data.value" class="eval-bands">
        <section aria-labelledby="metric-title"><div class="band-heading"><h3 id="metric-title">指标概览</h3><span class="muted">{{ batchId || '全部批次' }} · 评估标签 {{ report.data.value.cm.sample_total }} 个</span></div><div class="stat-grid"><div v-for="m in metrics" :key="m.key" class="stat"><div class="label">{{ m.label }}</div><div class="value">{{ m.key==='f1' ? fixed(report.data.value.cm[m.key],2) : percent(report.data.value.cm[m.key]) }}</div><div class="foot mono">{{ m.formula }}</div></div></div></section>
        <section aria-labelledby="diagnostic-title"><div class="band-heading"><h3 id="diagnostic-title">诊断分析</h3><span class="muted">混淆矩阵与样本分布</span></div>
          <div class="diagnostics">
            <div><h4>混淆矩阵</h4><div class="table-scroll"><table class="cm"><thead><tr><th scope="col">真实标签 / 研判输出</th><th scope="col">出线索（预测为正）</th><th scope="col">未出线索（预测为负）</th></tr></thead><tbody><tr><th scope="row">确有酒驾（label=1）</th><td class="tp"><b>{{ report.data.value.cm.tp }}</b><span>TP 真阳性</span></td><td class="fn"><b>{{ report.data.value.cm.fn }}</b><span>FN 漏报</span></td></tr><tr><th scope="row">无酒驾（label=0）</th><td class="fp"><b>{{ report.data.value.cm.fp }}</b><span>FP 误报</span></td><td class="tn"><b>{{ report.data.value.cm.tn }}</b><span>TN 真阴性</span></td></tr></tbody></table></div>
              <p class="muted small">按对象类型、对象编号和具体时间窗关联，并对重复批次去重；以评分表 is_clue 判定是否出线索，覆盖缺口不计入四格；指标由接口计算返回，前端不自行计算，分母为 0 时显示"—"。</p>
            </div>
            <div><h4>标签分布</h4><p class="muted small">干扰样本占比 {{ percent(report.data.value.cm.noise_ratio,0) }}（要求 ≥ 30%）</p><EChart :option="pieOption" height="260px" /></div>
          </div>
        </section>
        <section aria-labelledby="sample-title">
          <div class="band-heading"><h3 id="sample-title">样本明细</h3><el-select v-model="sampleFilter.result" clearable placeholder="全部评估结果" aria-label="筛选评估结果" @change="reloadSamples"><el-option v-for="(name,key) in resultNames" :key="key" :label="name" :value="key" /></el-select></div>
          <p class="muted small">明细与矩阵使用相同的关联口径：按对象和具体小时对齐；同一时段仅取最新成功评分，缺少评分单列为覆盖缺口。</p>
          <AsyncState :loading="samples.loading.value" :error="samples.error.value" :data="samples.data.value" empty-text="当前筛选下无评估样本，可清除结果筛选" @retry="samples.run">
            <el-table v-if="samples.data.value" :data="samples.data.value.list" row-key="row_id">
              <el-table-column label="对象" min-width="160"><template #default="{row}"><span class="mono">{{ row.object_id }}</span><div class="muted small">{{ row.object_type===1?'区域时段':'个人' }}</div></template></el-table-column>
              <el-table-column label="样本类别" width="120"><template #default="{row}">{{ sampleNames[row.sample_type] }}</template></el-table-column>
              <el-table-column label="真实标签" width="100"><template #default="{row}">{{ row.label===1?'确有酒驾':'无酒驾' }}</template></el-table-column>
              <el-table-column label="研判输出" width="100"><template #default="{row}">{{ row.result==='missing'?'覆盖缺口':row.prediction===1?'出线索':'未出线索' }}</template></el-table-column>
              <el-table-column label="结果" width="120"><template #default="{row}"><el-tag :type="['fp','fn'].includes(row.result)?'warning':'success'">{{ resultNames[row.result] }}</el-tag></template></el-table-column>
              <el-table-column label="评分来源" min-width="170"><template #default="{row}"><router-link v-if="row.score_id!=null" :to="{name:'risk-detail',params:{scoreId:row.score_id}}">{{ row.batch_id }} · {{ fixed(row.total_score) }} 分</router-link><span v-else class="muted">未匹配评分</span></template></el-table-column>
            </el-table>
          </AsyncState>
          <div v-if="samples.data.value" class="sample-foot"><span class="muted small">标签 {{ samples.data.value.sample_total }} 个 · 关联结果 {{ samples.data.value.joined_total }} 行 · 筛选结果 {{ samples.data.value.total }} 行</span><el-pagination v-if="samples.data.value.total>sampleFilter.size" v-model:current-page="sampleFilter.page" :total="samples.data.value.total" :page-size="sampleFilter.size" layout="prev,pager,next" @current-change="samples.run" /></div>
        </section>
      </div>
    </AsyncState>
    <el-alert type="warning" :closable="false" show-icon title="以上为模拟数据上的指标，仅用于验证研判流程，不代表真实执法效果。" />
  </div>
</template>
<script setup>
import {computed,reactive,ref} from 'vue'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {allPages} from '@/utils/dashboard'
import {fixed,percent} from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'
const metrics=[{key:'precision',label:'精确率',formula:'TP / (TP + FP)'},{key:'recall',label:'召回率',formula:'TP / (TP + FN)'},{key:'fpr',label:'误报率',formula:'FP / (FP + TN)'},{key:'f1',label:'F1',formula:'2PR / (P + R)'}]
const resultNames={tp:'TP 真阳性',fp:'FP 误报',fn:'FN 漏报',tn:'TN 真阴性',missing:'覆盖缺口'}
const sampleNames={1:'正样本',2:'干扰样本',3:'对照样本'}
const batchId=ref('')
const report=useAsync(async()=>{const [cm,labels]=await Promise.all([api.confusion({batch_id:batchId.value}),api.labels()]);return {cm,labels}})
const batches=useAsync(()=>allPages(api.batches,{run_status:2}))
const sampleFilter=reactive({result:'',page:1,size:20})
const samples=useAsync(()=>api.evalSamples({...sampleFilter,batch_id:batchId.value}))
function changeBatch(){sampleFilter.page=1;report.run();samples.run()}
function reloadSamples(){sampleFilter.page=1;samples.run()}
const pieOption=computed(()=>({tooltip:{trigger:'item',formatter:'{b}：{c} 个（{d}%）'},legend:{bottom:0},color:['#ee8d87','#d9b474','#8aadaa'],series:[{type:'pie',radius:['40%','68%'],center:['50%','45%'],label:{formatter:'{b}\n{c}'},data:(report.data.value?.labels || []).map((l)=>({name:l.name,value:l.cnt}))}]}))
</script>
<style scoped>
.eval-bands{display:flex;flex-direction:column;gap:48px}.band-heading{display:flex;gap:16px;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:20px}.band-heading h3{font-size:20px;font-weight:500;margin:0}.band-heading > .muted{font-size:13px}.band-heading .el-select{width:190px}.heading-range{display:flex;align-items:center;gap:12px}.heading-range label{font-size:13px}.heading-range .el-select{width:220px}.diagnostics{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:32px}.diagnostics h4{margin:0 0 16px;font-size:16px;font-weight:500}.cm{width:100%;border-collapse:collapse;text-align:center}.cm th,.cm td{border:1px solid var(--card-border);padding:18px 12px}.cm th{font-size:13px;background:var(--surface-raised)}.cm td b{display:block;font-size:36px;font-family:var(--font-data);font-weight:500;font-variant-numeric:tabular-nums}.cm td span{font-size:12px;color:var(--text-muted)}.tp,.tn{background:var(--surface-raised)}.fp,.fn{background:var(--level-high-bg)}.small{font-size:12px;line-height:1.8}.table-scroll{overflow-x:auto}.sample-foot{display:flex;justify-content:space-between;flex-wrap:wrap;align-items:center;gap:16px;margin-top:20px}
@media(max-width:1000px){.diagnostics{grid-template-columns:minmax(0,1fr)}}@media(max-width:600px){.eval-bands{gap:28px}.heading-range{width:100%}.heading-range .el-select{flex:1}.cm th,.cm td{padding:12px 6px}}
</style>
