<template>
  <div class="kanban" tabindex="0" aria-label="线索状态看板，可横向滚动">
    <section v-for="column in columns" :key="column.status" class="kanban-column" :aria-label="column.title">
      <header class="column-head"><h3>{{ column.title }}</h3><span class="column-count num">{{ column.rows.length }}</span></header>
      <p class="column-caption muted">{{ column.hint }}</p>
      <div class="column-body">
        <button v-for="clue in column.rows.slice(0,limits[column.status])" :key="clue.clue_id" class="clue-card" @click="$emit('open',clue)">
          <span class="clue-object">{{ clue.object_type===2 ? `个人 ${clue.object_id}` : clue.area_name }}</span>
          <span class="clue-score"><LevelTag :level="clue.risk_level" /><b class="num">{{ fixed(clue.total_score) }} 分</b></span>
          <span class="clue-reason">{{ reason(clue) }}</span>
          <span class="clue-meta">{{ clue.assignee_name || '未分配承办人' }} · {{ clue.hour_slot==null ? '个人对象' : `${pad2(clue.hour_slot)}时` }}</span>
          <span class="mono muted">{{ clue.clue_id }}</span>
        </button>
        <p v-if="!column.rows.length" class="column-empty muted">暂无{{ column.title }}线索</p>
        <el-button v-if="limits[column.status]<column.rows.length" class="load-more" @click="limits[column.status]+=20">继续显示（剩余 {{ column.rows.length-limits[column.status] }} 条）</el-button>
      </div>
    </section>
  </div>
</template>
<script setup>
import { computed, reactive, watch } from 'vue'
import { fixed, pad2, parseHitFeatures } from '@/utils/format'
import { useDicts } from '@/composables/useDicts'
import LevelTag from './LevelTag.vue'
const props=defineProps({rows:{type:Array,default:()=>[]}})
defineEmits(['open'])
const dicts=useDicts()
const limits=reactive([20,20,20,20])
watch(()=>props.rows,()=>limits.fill(20))
const columns=computed(()=>[
  {status:0,title:'待核查',hint:'等待人工开始核查'},
  {status:1,title:'核查中',hint:'查看依据并提交核查结论'},
  {status:2,title:'已确认',hint:'核查已完成，记录只读'},
  {status:3,title:'已排除',hint:'已关闭，保留否定特征与反馈'},
].map((c)=>({...c,rows:props.rows.filter((r)=>r.clue_status===c.status)})))
function reason(c){return parseHitFeatures(c.hit_features).slice(0,2).map((h)=>dicts.value?.features?.find((f)=>f.feature_id===h.id)?.feature_name || h.id).join('、') || '暂无命中理由'}
</script>
<style scoped>
.kanban { display:grid; grid-template-columns:repeat(4,minmax(260px,1fr)); gap:16px; overflow-x:auto; align-items:start; padding:4px 4px 16px; }.kanban-column { min-width:0; background:var(--surface-inset); border-radius:12px; padding:16px; }.column-head { display:flex; justify-content:space-between; align-items:center; gap:12px; }.column-head h3 { font-size:15px; font-weight:500; margin:0; }.column-count { font-weight:500; }.column-caption { font-size:12px; margin:8px 0 16px; line-height:1.6; }.column-body { display:flex; flex-direction:column; gap:12px; max-height:65vh; overflow-y:auto; padding:2px; }.clue-card { display:flex; flex-direction:column; gap:12px; width:100%; padding:16px; background:var(--surface); border:1px solid var(--card-border); border-radius:12px; text-align:left; font:inherit; color:inherit; cursor:pointer; }.clue-card:hover { border-color:var(--accent); }.clue-object { font-weight:500; }.clue-score { display:flex; gap:12px; align-items:center; justify-content:space-between; }.clue-reason { font-size:13px; line-height:1.7; min-height:44px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }.clue-score b { font-family:var(--font-data); font-size:24px; font-weight:500; }.column-count { font-family:var(--font-mono); font-size:12px; color:var(--text-secondary); }.clue-card { min-height:212px; transition:border-color .16s var(--ease-out),background-color .16s var(--ease-out); }.clue-meta,.clue-card > .mono { font-size:12px; color:var(--text-muted); }.column-empty { font-size:13px; text-align:center; padding:20px 0; }.load-more { width:100%; }
</style>
