<template>
  <div class="judge">
    <div class="contributions" aria-label="风险因子贡献分"><div v-for="f in features" :key="f.feature_id" class="factor"><span>{{ f.feature_name }}</span><div class="bar-track"><i :class="{negative:f.contribution<0}" :style="{width:`${Math.min(100,Math.abs(f.contribution || 0)*2)}%`}" /></div><b class="mono">{{ f.is_missing ? '缺失' : signed(f.contribution,2) }}</b></div></div>
    <el-table :data="features" size="small"><el-table-column prop="feature_name" label="因子" min-width="180" /><el-table-column label="原始值" width="90"><template #default="{row}">{{ fixed(row.raw_value,3) }}</template></el-table-column><el-table-column label="归一化" width="90"><template #default="{row}">{{ fixed(row.normalized_value,3) }}</template></el-table-column><el-table-column label="系数" width="90"><template #default="{row}">{{ fixed(row.weight,2) }}</template></el-table-column><el-table-column label="贡献分" width="100"><template #default="{row}"><b>{{ signed(row.contribution,2) }}</b></template></el-table-column><el-table-column label="数据状态" width="110"><template #default="{row}">{{ row.is_missing ? '数据不足' : '有效' }}</template></el-table-column></el-table>
    <p class="formula">风险指数 = 截断到 0–100（{{ features.map(f=>signed(f.contribution,2)).join(' ') }}）= {{ fixed(totalScore) }}<span v-if="totalScore==null">（数据不足，不生成线索）</span></p>
    <el-alert v-if="mismatch" type="error" :closable="false" title="贡献分与评分不一致，请检查数据" />
    <p class="muted small">贡献分 = 归一化值 × 系数 × 100；安全出行反例扣 35 分。风险指数用于排序与核查，不是发生概率。</p>
  </div>
</template>
<script setup>
import {computed} from 'vue'
import {fixed,signed} from '@/utils/format'
const props=defineProps({features:{type:Array,default:()=>[]},totalScore:{type:Number,default:null}})
const mismatch=computed(()=>props.totalScore!=null&&Math.abs(Math.round(Math.min(100,Math.max(0,props.features.reduce((s,f)=>s+(f.contribution||0),0)))*100)/100-props.totalScore)>.01)
</script>
<style scoped>
.judge{display:flex;flex-direction:column;gap:16px}.contributions{display:flex;flex-direction:column;gap:14px}.factor{display:grid;grid-template-columns:minmax(140px,1fr) 2fr 64px;gap:16px;align-items:center;font-size:13px}.factor b{text-align:right;font-weight:500}.bar-track{height:8px;background:var(--surface-inset);border-radius:4px;overflow:hidden}.bar-track i{display:block;height:100%;background:var(--accent)}.bar-track i.negative{background:var(--el-color-success)}.small{font-size:12px;line-height:1.7}.formula{overflow-wrap:anywhere}@media(max-width:600px){.factor{grid-template-columns:1fr 1fr 54px;gap:8px}}
</style>
