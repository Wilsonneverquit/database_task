<template>
  <div>
    <div class="heat-controls">
      <el-radio-group v-model="dayType" aria-label="日期类型">
        <el-radio-button :value="1">工作日</el-radio-button>
        <el-radio-button :value="2">周末</el-radio-button>
      </el-radio-group>
      <span class="muted">{{ cells.length }} 个区域时段 · 空白表示无评分</span>
    </div>
    <el-alert v-if="!thresholds" type="info" :closable="false" title="当前接口未提供规则阈值，按已返回的风险等级着色。" />
    <el-empty v-if="!cells.length" description="该批次在此日期类型下暂无评分，可切换日期类型" />
    <div v-else class="heat-scroll" tabindex="0" aria-label="区域时段风险热力图，可滚动查看">
      <EChart :option="option" :height="`${Math.max(144, areas.length * 36 + 88)}px`" @click="openScore" />
    </div>
    <p class="muted chart-note">时段从 06 时排到次日 05 时；点击色块或下方区域链接查看命中依据。</p>
    <div class="heat-links">
      <router-link v-for="r in peaks" :key="r.area_id" :to="{ name: 'risk-detail', params: { scoreId: r.score_id } }">{{ r.area_name }} · 最高 {{ fixed(r.total_score) }} 分</router-link>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import EChart from './EChart.vue'
import { fixed, pad2 } from '@/utils/format'
import { chartPalette } from '@/styles/chart-theme'
import { heatCells, nightHours, escapeHtml } from '@/utils/dashboard'
const props = defineProps({ rows: { type: Array, default: () => [] }, rule: { type: Object, default: null } })
const router = useRouter()
const dayType = ref(1)
watch(() => props.rows, (rows) => { if (!rows.some((r) => r.day_type === dayType.value)) dayType.value = rows[0]?.day_type || 1 }, { immediate: true })
const cells = computed(() => heatCells(props.rows, dayType.value))
const areas = computed(() => [...new Map(cells.value.map((r) => [r.area_id, r.area_name])).entries()])
const peaks = computed(() => areas.value.map(([id]) => cells.value.filter((r) => r.area_id === id).reduce((a, b) => a.total_score >= b.total_score ? a : b)))
const thresholds = computed(() => props.rule?.low_threshold != null && props.rule?.high_threshold != null ? { low: Number(props.rule.low_threshold), high: Number(props.rule.high_threshold) } : null)
const option = computed(() => ({
  tooltip: { formatter: (p) => `${escapeHtml(p.data.row.area_name)} · ${pad2(p.data.row.hour_slot)} 时<br/>总分 ${fixed(p.data.row.total_score)} · ${escapeHtml(p.data.row.status_label || (p.data.row.total_score==null?'未评分':p.data.row.risk_level_name+'风险'))}<br/>样本 ${p.data.row.sample_size} · 命中 ${p.data.row.hit_cnt} 项` },
  grid: { left: 108, right: 16, top: 16, height: areas.value.length * 36 },
  xAxis: { type: 'category', data: nightHours.map((h) => `${pad2(h)}时`), axisLabel: { interval: 0 }, splitArea: { show: true } },
  yAxis: { type: 'category', inverse: true, data: areas.value.map(([, name]) => name), splitArea: { show: true } },
  visualMap: { type: 'piecewise', dimension: 2, orient: 'horizontal', left: 'center', bottom: 4, pieces: [
    { value: 1, label: thresholds.value ? `低 <${thresholds.value.low}` : '低风险', color: chartPalette.low },
    { value: 2, label: thresholds.value ? `中 ${thresholds.value.low}–<${thresholds.value.high}` : '中风险', color: chartPalette.mid },
    { value: 3, label: thresholds.value ? `高 ≥${thresholds.value.high}` : '高风险', color: chartPalette.high },
  ] },
  series: [{ type: 'heatmap', data: cells.value.map((r) => ({ value: [nightHours.indexOf(r.hour_slot), areas.value.findIndex(([id]) => id === r.area_id), r.risk_level], row: r, label: {color: r.risk_level===3 ? '#fff' : chartPalette.cellInk} })),
    label: { show: true, formatter: (p) => fixed(p.data.row.total_score, 2), color: chartPalette.cellInk, fontSize:11 },
    itemStyle: { borderColor: '#121d2d', borderWidth: 2 } }],
}))
function openScore(p) { if (p.data?.row) router.push({ name: 'risk-detail', params: { scoreId: p.data.row.score_id } }) }
</script>

<style scoped>
.heat-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }
.heat-scroll { overflow: auto; max-height: 530px; }
.heat-scroll :deep(.chart) { min-width: 760px; }
.chart-note { font-size: 12px; line-height: 1.6; }
.heat-links { display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: 12px; }
</style>
