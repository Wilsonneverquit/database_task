<template>
  <div class="page">
    <div class="page-head"><div><h2>区域时段风险</h2><p class="sub">研判对象 = 区域 + 具体日期 + 小时。点击评分查看连续因子贡献、证据来源和风险趋势。</p></div></div>
    <el-card shadow="never">
      <div class="toolbar filter-bar">
        <el-select v-model="filters.batch_id" aria-label="筛选研判批次" placeholder="全部批次" clearable filterable class="batch-filter" @change="reload"><el-option v-for="b in batchOptions" :key="b.batch_id" :label="b.batch_id" :value="b.batch_id" /></el-select>
        <el-select v-model="filters.area_id" aria-label="筛选区域" placeholder="全部区域" clearable class="short-filter" @change="reload"><el-option v-for="a in dicts?.areas || []" :key="a.area_id" :label="a.area_name" :value="a.area_id" /></el-select>
        <el-select v-model="filters.risk_level" aria-label="筛选风险等级" placeholder="全部等级" clearable class="short-filter" @change="reload"><el-option v-for="o in enumOptions('risk_level')" :key="o.value" :label="`${o.label}风险`" :value="o.value" /></el-select>
        <el-button @click="clearFilters">清空筛选</el-button>
        <span class="muted result-count" role="status">共 {{ data?.total ?? 0 }} 个研判对象</span>
      </div>
      <AsyncState :loading="loading" :error="error" :data="data" empty-text="没有符合条件的研判对象，请清空或调整筛选" @retry="load">
        <el-table v-if="data" :data="data.list" row-key="score_id" @row-click="open" class="clickable-rows">
          <el-table-column type="expand" width="44"><template #default="{row}"><dl class="row-details"><div><dt>批次</dt><dd class="mono">{{ row.batch_id }}</dd></div><div><dt>区域编号</dt><dd>{{ row.area_id }}</dd></div><div><dt>样本量</dt><dd>{{ row.sample_size }}</dd></div><div><dt>命中特征</dt><dd>{{ row.hit_cnt }} 项</dd></div><div><dt>是否出线索</dt><dd>{{ row.is_clue ? '已生成线索' : '未生成' }}</dd></div></dl></template></el-table-column>
          <el-table-column label="区域" min-width="130" fixed="left"><template #default="{row}"><router-link @click.stop :to="{name:'risk-detail',params:{scoreId:row.score_id}}">{{ row.area_name }}</router-link></template></el-table-column>
          <el-table-column label="时段" width="140"><template #default="{row}">{{ row.window_start?.slice(0,10) }}<br/><span class="num muted">{{ hourLabel(row.hour_slot) }}</span></template></el-table-column>
          <el-table-column label="总分" width="90" align="right"><template #default="{row}"><b class="num">{{ fixed(row.total_score) }}</b></template></el-table-column>
          <el-table-column label="等级" width="100"><template #default="{row}"><LevelTag :level="row.risk_level" :status="row.risk_status" /></template></el-table-column>
          <el-table-column label="关键理由" min-width="210"><template #default="{row}"><div class="reasons"><el-tooltip v-for="h in parseHitFeatures(row.hit_features).slice(0,2)" :key="h.id" :content="`${h.id} · 贡献 ${signed(h.weight)}`"><span class="reason">{{ featureName(h.id) }}</span></el-tooltip><span v-if="parseHitFeatures(row.hit_features).length>2" class="muted">另 {{ parseHitFeatures(row.hit_features).length-2 }} 项</span><span v-if="!row.hit_features" class="muted">无命中</span></div></template></el-table-column>
          <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><router-link @click.stop :to="{name:'risk-detail',params:{scoreId:row.score_id}}">查看详情</router-link></template></el-table-column>
        </el-table>
      </AsyncState>
      <el-pagination v-if="data && data.total > filters.size" class="pager" layout="total, prev, pager, next" :total="data.total" :page-size="filters.size" v-model:current-page="filters.page" @current-change="load" />
    </el-card>
  </div>
</template>
<script setup>
import { computed, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { enumOptions } from '@/constants/enums'
import { useAsync } from '@/composables/useAsync'
import { useDicts } from '@/composables/useDicts'
import { fixed, hourLabel, parseHitFeatures, signed } from '@/utils/format'
import { allPages } from '@/utils/dashboard'
import AsyncState from '@/components/AsyncState.vue'
import LevelTag from '@/components/LevelTag.vue'
const router=useRouter(), route=useRoute(), dicts=useDicts()
const filters=reactive({batch_id:route.query.batch_id || '',area_id:route.query.area_id || '',risk_level:route.query.risk_level ? Number(route.query.risk_level) : '',page:1,size:20})
const {data,loading,error,run:load}=useAsync(()=>api.regionRisk({...filters}))
const batches=useAsync(()=>allPages(api.batches))
const batchOptions=computed(()=>(batches.data.value || []).filter((b)=>b.judge_object===1))
const featureName=(id)=>dicts.value?.features?.find((f)=>f.feature_id===id)?.feature_name || id
function reload(){filters.page=1;load()}
function clearFilters(){Object.assign(filters,{batch_id:'',area_id:'',risk_level:'',page:1});router.replace({name:'risk'});load()}
function open(row,column){if(column.type==='expand')return;router.push({name:'risk-detail',params:{scoreId:row.score_id}})}
watch(()=>route.query,(q)=>{Object.assign(filters,{batch_id:q.batch_id || '',area_id:q.area_id || '',risk_level:q.risk_level?Number(q.risk_level):'',page:1});load()})
</script>
<style scoped>
.filter-bar{margin-bottom:20px}.batch-filter{width:220px}.short-filter{width:150px}.result-count{margin-left:auto;font-size:13px}
.clickable-rows :deep(.el-table__row){cursor:pointer}.reasons{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px}.reason{color:var(--text-secondary)}
.row-details{display:flex;flex-wrap:wrap;gap:20px 32px;padding:8px 28px;margin:0;background:var(--surface-raised)}.row-details dt{color:var(--text-muted);font-size:12px}.row-details dd{margin:6px 0 0}.pager{margin-top:20px;justify-content:flex-end;max-width:100%;overflow:auto}
@media(max-width:600px){.batch-filter,.short-filter{width:100%}.result-count{margin:0}}
</style>
