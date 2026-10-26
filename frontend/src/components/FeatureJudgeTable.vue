<template>
  <div class="judge">
    <el-table :data="features" :row-class-name="rowClass" border size="default">
      <el-table-column label="特征" min-width="220">
        <template #default="{ row }">
          <span class="mono muted">{{ row.feature_id }}</span>
          <span class="fname">{{ row.feature_name }}</span>
          <el-tag v-if="row.direction === 2" size="small" type="info" class="ml">反例</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="口径" prop="match_expr" min-width="260" show-overflow-tooltip />
      <el-table-column label="判定" width="110" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_missing === 1" type="info" effect="plain">数据不足</el-tag>
          <el-tag v-else-if="row.is_hit === 1" :type="row.weight < 0 ? 'success' : 'danger'" effect="dark">命中</el-tag>
          <span v-else class="muted">未命中</span>
        </template>
      </el-table-column>
      <el-table-column label="权重" width="100" align="right">
        <template #default="{ row }"><span class="num mono">{{ signed(row.weight) }}</span></template>
      </el-table-column>
      <el-table-column label="命中值" width="90" align="right">
        <template #default="{ row }"><span class="num">{{ row.is_missing === 1 ? '—' : fixed(row.hit_value, 2) }}</span></template>
      </el-table-column>
      <el-table-column label="数据缺失" width="90" align="center">
        <template #default="{ row }">{{ row.is_missing === 1 ? '是' : '否' }}</template>
      </el-table-column>
    </el-table>

    <div class="formula">
      总分 = {{ formula }}
    </div>
    <el-alert v-if="mismatch" type="error" :closable="false" show-icon
      :title="`明细加权和 ${sum.toFixed(4)} 与评分表总分 ${fixed(totalScore)} 不一致，请检查数据`" />
    <div class="legend muted">
      <span><i class="sw hit" />命中（计入总分）</span>
      <span><i class="sw missing" />数据不足：既不是命中，也不是"干净的未命中"，不参与计分</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { fixed, signed } from '@/utils/format'

const props = defineProps({
  features: { type: Array, default: () => [] },
  totalScore: { type: Number, default: null },
})

const hits = computed(() => props.features.filter((f) => f.is_hit === 1 && f.is_missing !== 1))
const sum = computed(() => hits.value.reduce((s, f) => s + f.weight, 0))

// 《前端交接文档》B2：总分 = 1.1693 + 2.9285 + 1.9274 = 6.0252 ≈ 6.03
const formula = computed(() => {
  if (!hits.value.length) return `0（无命中特征） = ${fixed(props.totalScore)}`
  const parts = hits.value.map((f, i) => {
    const abs = Math.abs(f.weight).toFixed(4)
    if (i === 0) return f.weight < 0 ? `−${abs}` : abs
    return f.weight < 0 ? `− ${abs}` : `+ ${abs}`
  })
  return `${parts.join(' ')} = ${sum.value.toFixed(4)} ≈ ${fixed(props.totalScore)}`
})

const mismatch = computed(() => props.totalScore !== null && hits.value.length > 0 && Math.abs(Math.round(sum.value * 100) / 100 - props.totalScore) > 0.005)

function rowClass({ row }) {
  if (row.is_missing === 1) return 'row-missing'
  return row.is_hit === 1 ? 'row-hit' : ''
}
</script>

<style scoped>
.judge { display: flex; flex-direction: column; gap: 12px; }
.fname { margin-left: 8px; }
.ml { margin-left: 6px; }
.legend { display: flex; gap: 20px; font-size: 12px; flex-wrap: wrap; }
.sw { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; border: 1px solid var(--card-border); }
.sw.hit { background: var(--hit-bg); }
.sw.missing { background: var(--missing-bg); }
</style>
