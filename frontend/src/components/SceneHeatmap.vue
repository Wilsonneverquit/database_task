<template>
  <el-card shadow="never">
    <template #header>
      <div class="head">
        <div class="card-title">
          场景出现频度
          <span class="hint">{{ subtitle }}</span>
        </div>
        <div class="toolbar">
          <el-radio-group v-if="sources.length > 1" v-model="filters.source" size="small" @change="load">
            <el-radio-button v-for="s in sources" :key="s.value" :value="s.value">{{ s.label }}</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="filters.dim" size="small" @change="load">
            <el-radio-button value="place_type">按场所类型</el-radio-button>
            <el-radio-button value="area">按区域</el-radio-button>
          </el-radio-group>
          <el-select v-model="filters.day_type" placeholder="全部日期" clearable size="small" style="width: 110px" @change="load">
            <el-option v-for="o in enumOptions('day_type')" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" size="small" start-placeholder="开始日期" end-placeholder="结束日期"
            style="width: 230px" @change="load" />
        </div>
      </div>
    </template>

    <AsyncState :loading="loading" :error="error" :data="data" :empty="data ? data.total === 0 : undefined"
      empty-text="所选范围内没有记录" @retry="load">
      <template v-if="data">
        <el-alert v-if="data.total < SMALL_SAMPLE" type="info" :closable="false" show-icon class="note"
          :title="`样本较少（n=${data.total}），仅示意分布，不代表规律`" />
        <EChart :option="option" :height="`${Math.max(220, data.y.length * 34 + 90)}px`" />
        <p class="muted foot">{{ footnote }}</p>
      </template>
    </AsyncState>
  </el-card>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { api } from '@/api'
import { enumOptions } from '@/constants/enums'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/composables/useAsync'
import { halfOpenRange, pad2 } from '@/utils/format'
import AsyncState from './AsyncState.vue'
import EChart from './EChart.vue'

const SMALL_SAMPLE = 30

const auth = useAuthStore()
// 只列出当前角色有权看的数据源；一个都没有时父组件不渲染本组件
const sources = [
  { value: 'case', label: '历史案件', block: 'overview.freq.case' },
  { value: 'consume', label: '饮酒消费', block: 'overview.freq.consume' },
].filter((s) => auth.canBlock(s.block))

const filters = reactive({ source: sources[0]?.value, dim: 'place_type', day_type: '' })
const range = ref(null)
const { data, loading, error, run: load } = useAsync(() => api.sceneFrequency({ ...filters, ...halfOpenRange(range.value) }))

const subtitle = computed(() => {
  if (filters.source === 'case') return `历史案件发生在哪类场景、哪个时段（只读 v_case_history，截至 ${data.value?.history_cutoff?.slice(0, 10) || '时间边界'}）`
  return '含酒水消费发生在哪类场景、哪个时段（consume_record）'
})

const footnote = computed(() => {
  const what = filters.source === 'case' ? '起案件' : '条含酒水消费'
  return `共 ${data.value.total} ${what}。横轴从 06 时排到次日 05 时，使夜间时段连续；颜色只表示出现次数，不表示风险高低（风险见"区域 × 时段风险热力"）。`
})

const option = computed(() => {
  const d = data.value
  const xIndex = new Map(d.x.map((h, i) => [h, i]))
  const yIndex = new Map(d.y.map((r, i) => [r.key, i]))
  const unit = filters.source === 'case' ? '起' : '条'
  return {
    tooltip: {
      formatter: (p) => {
        const [xi, yi, cnt] = p.value
        const row = d.y[yi]
        const h = d.x[xi]
        const share = (n, total) => (total ? `${((n / total) * 100).toFixed(1)}%` : '—')
        return `${row.label} · ${pad2(h)}:00–${pad2(h)}:59<br/><b>${cnt}</b> ${unit}`
          + `<br/>占该场景 ${share(cnt, row.total)} · 占全部 ${share(cnt, d.total)}`
      },
    },
    grid: { left: 120, right: 70, top: 10, bottom: 40 },
    xAxis: { type: 'category', data: d.x.map((h) => `${pad2(h)}时`), splitArea: { show: true }, axisLabel: { interval: 0, fontSize: 11 } },
    yAxis: { type: 'category', data: d.y.map((r) => `${r.label}（${r.total}）`), splitArea: { show: true }, inverse: true },
    // 蓝色单色渐变，与风险图的灰/黄/红区分，避免把"次数多"读成"风险高"
    visualMap: {
      type: 'continuous', min: 0, max: Math.max(1, d.max), calculable: false, orient: 'vertical', right: 0, top: 'middle',
      itemHeight: 120, text: [`${Math.max(1, d.max)}`, '0'], inRange: { color: ['#e8f1fd', '#1f5fbf'] },
    },
    series: [{
      type: 'heatmap',
      // 0 次的格子不画，留空
      data: d.cells.filter((c) => c.cnt > 0 && yIndex.has(c.y)).map((c) => [xIndex.get(c.x), yIndex.get(c.y), c.cnt]),
      label: { show: true, color: '#fff', fontWeight: 600, formatter: (p) => p.value[2] },
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      emphasis: { itemStyle: { borderColor: '#303133', borderWidth: 1 } },
    }],
  }
})
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.note { margin-bottom: 8px; }
.foot { font-size: 12px; margin: 4px 0 0; line-height: 1.6; }
</style>
