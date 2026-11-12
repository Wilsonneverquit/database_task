<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>风险地图</h2>
        <p class="sub">按区域以红色深浅展示风险等级（颜色越深风险越高），拖动时间轴查看各观察夜的风险分布变化。坐标取自区域表 area_info 的经纬度字段。</p>
      </div>
      <div class="toolbar">
        <el-tag type="info" effect="plain">{{ areas.length }} 个区域 · {{ dates.length }} 个观察夜</el-tag>
      </div>
    </div>

    <AsyncState :loading="loading" :error="error" :data="mapData" empty-text="暂无区域坐标或风险数据" @retry="load">
      <el-card v-if="mapData" shadow="never">
        <template #header>
          <div class="card-title">
            区域风险分布
            <span class="hint">示例城市（虚构）· 坐标为示例值，仅用于教学演示</span>
          </div>
        </template>
        <EChart v-if="chartOption" :option="chartOption" height="500px" />
      </el-card>

      <el-card v-if="mapData && dates.length" shadow="never">
        <template #header>
          <div class="card-title">
            观察夜时间轴
            <span class="hint">
              当前：<b class="num">{{ currentDate }}</b> ·
              参与研判 <b class="num">{{ activeCount }}</b> 个区域 ·
              最高风险「{{ topArea?.area_name || '—' }}」（{{ topArea ? fixed(topArea.total_score) : '—' }} 分 · {{ topArea?.risk_level_name || '—' }}风险）
            </span>
          </div>
        </template>

        <div class="timeline">
          <el-button :icon="VideoPlay" :disabled="playing" @click="play">播放</el-button>
          <el-button :icon="VideoPause" :disabled="!playing" @click="pause">暂停</el-button>
          <el-slider v-model="currentIdx" :min="0" :max="dates.length - 1" :step="1" class="slider" />
          <span class="mono muted date-label">{{ currentDate }}</span>
        </div>

        <div class="legend">
          <span class="muted">风险总分</span>
          <div class="gradient-bar" />
          <span class="muted">0 · 低</span>
          <span class="muted">9 · 高</span>
          <span class="muted gray-dot" />
          <span class="muted">当夜无研判数据</span>
        </div>
      </el-card>
    </AsyncState>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { api } from '@/api'
import { useAsync } from '@/composables/useAsync'
import { fixed } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'

// 风险地图数据：areas（含 lng/lat）、dates（观察夜）、risk（按日期×区域的峰值风险）
const { data: mapData, loading, error, run: load } = useAsync(() => api.riskMap())

const areas = computed(() => mapData.value?.areas || [])
const dates = computed(() => mapData.value?.dates || [])
const risk = computed(() => mapData.value?.risk || [])

// 时间轴默认停在最新一个观察夜
const currentIdx = ref(0)
watch(dates, (d, old) => {
  if (d.length && (!old || !old.length)) currentIdx.value = d.length - 1
})

const currentDate = computed(() => dates.value[currentIdx.value] || '')
const currentRisk = computed(() => risk.value.find((r) => r.date === currentDate.value))
const riskByArea = computed(() => {
  const m = {}
  currentRisk.value?.areas.forEach((a) => { m[a.area_id] = a })
  return m
})
const activeCount = computed(() => currentRisk.value?.areas.length || 0)

const areaById = computed(() => Object.fromEntries(areas.value.map((a) => [a.area_id, a])))
const topArea = computed(() => {
  const arr = currentRisk.value?.areas || []
  if (!arr.length) return null
  const top = arr.reduce((m, a) => (!m || a.total_score > m.total_score ? a : m))
  return { ...top, area_name: areaById.value[top.area_id]?.area_name }
})

// 总分 0 → 9 映射为浅红 → 深红的连续渐变；无数据用中性灰
function riskColor(score) {
  if (score === null || score === undefined || Number.isNaN(score)) return '#e5e7eb'
  const t = Math.max(0, Math.min(1, score / 9))
  const lerp = (a, b) => Math.round(a + (b - a) * t)
  return `rgb(${lerp(253, 154)}, ${lerp(232, 18)}, ${lerp(232, 18)})`
}

const chartOption = computed(() => {
  if (!areas.value.length) return null
  const lngs = areas.value.map((p) => p.lng)
  const lats = areas.value.map((p) => p.lat)
  const pad = 0.018
  const minX = Math.min(...lngs) - pad
  const maxX = Math.max(...lngs) + pad
  const minY = Math.min(...lats) - pad
  const maxY = Math.max(...lats) + pad
  return {
    tooltip: {
      formatter: (p) => {
        const a = p.data.area
        const r = p.data.risk
        const head = `<b>${a.area_name}</b>（${a.area_id} · ${a.area_type_name}）<br/>`
        if (!r) return `${head}<span style="color:#909399">当夜无研判数据</span>`
        return `${head}风险等级：<b>${r.risk_level_name}风险</b><br/>总分：<b>${r.total_score.toFixed(2)}</b><br/>命中特征 ${r.hit_cnt} 项 · 样本量 ${r.sample_size}<br/>批次 ${r.batch_id}`
      },
    },
    grid: { left: 24, right: 24, top: 16, bottom: 24 },
    xAxis: {
      type: 'value', min: minX, max: maxX,
      axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: '#f2f4f7', type: 'dashed' } },
    },
    yAxis: {
      type: 'value', min: minY, max: maxY,
      axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: '#f2f4f7', type: 'dashed' } },
    },
    series: [{
      type: 'scatter',
      symbolSize: 34,
      data: areas.value.map((a) => {
        const r = riskByArea.value[a.area_id] || null
        return { value: [a.lng, a.lat], area: a, risk: r, itemStyle: { color: riskColor(r?.total_score) } }
      }),
      label: {
        show: true, position: 'bottom', distance: 6,
        formatter: (p) => p.data.area.area_name,
        color: '#606266', fontSize: 11,
      },
      itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.18)' },
    }],
  }
})

// 播放控制：每 1.6 秒推进一个观察夜，循环播放
const playing = ref(false)
let timer = null
function play() {
  if (playing.value || !dates.value.length) return
  playing.value = true
  timer = setInterval(() => {
    currentIdx.value = (currentIdx.value + 1) % dates.value.length
  }, 1600)
}
function pause() {
  playing.value = false
  if (timer) { clearInterval(timer); timer = null }
}
onBeforeUnmount(pause)
</script>

<style scoped>
.timeline { display: flex; align-items: center; gap: 12px; }
.slider { flex: 1; margin: 0 8px; }
.date-label { min-width: 86px; text-align: right; }
.legend { display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: 12px; }
.gradient-bar { width: 180px; height: 12px; border-radius: 6px; background: linear-gradient(to right, rgb(253, 232, 232), rgb(154, 18, 18)); }
.gray-dot { width: 12px; height: 12px; border-radius: 50%; background: #e5e7eb; display: inline-block; margin-left: 8px; }
</style>
