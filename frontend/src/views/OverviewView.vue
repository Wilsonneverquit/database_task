<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>首页概览</h2>
        <p class="sub">以案找线：历史案件 → 风险特征 → 扫描日常数据 → 区域时段风险 → 待核查线索 → 核查结论回流</p>
      </div>
    </div>

    <AsyncState :loading="ov.loading.value" :error="ov.error.value" :data="ov.data.value" @retry="ov.run">
      <div v-if="ov.data.value" class="stat-grid">
        <template v-if="auth.canBlock('overview.clues')">
          <div class="stat">
            <div class="label">线索总数</div>
            <div class="value">{{ ov.data.value.clue_total }}</div>
            <div class="foot">已确认 {{ ov.data.value.clue_confirmed }} · 已排除 {{ ov.data.value.clue_excluded }}</div>
          </div>
          <div class="stat clickable" @click="router.push({ name: 'clues', query: { status: 0 } })">
            <div class="label">待核查</div>
            <div class="value warn">{{ ov.data.value.clue_open }}</div>
            <div class="foot">另有核查中 {{ ov.data.value.clue_checking }} 条</div>
          </div>
          <div class="stat">
            <div class="label">高风险对象</div>
            <div class="value high">{{ ov.data.value.high_risk_cnt }}</div>
            <div class="foot">评分 ≥ 高阈值（6 分）的研判对象</div>
          </div>
        </template>
        <div v-if="auth.canBlock('overview.eval')" class="stat clickable" @click="router.push({ name: 'eval' })">
          <div class="label">召回率</div>
          <div class="value">{{ percent(ov.data.value.eval.recall) }}</div>
          <div class="foot">精确率 {{ percent(ov.data.value.eval.precision) }} · 误报率 {{ percent(ov.data.value.eval.fpr) }}（模拟数据）</div>
        </div>
        <div class="stat">
          <div class="label">最近研判批次</div>
          <div class="value mono small">{{ ov.data.value.latest_batch?.batch_id || '—' }}</div>
          <div class="foot">
            <StatusTag v-if="ov.data.value.latest_batch" type="run_status" :value="ov.data.value.latest_batch.run_status" />
            <span v-if="ov.data.value.latest_batch?.duration_ms"> 耗时 {{ ov.data.value.latest_batch.duration_ms }} ms</span>
          </div>
        </div>
      </div>
    </AsyncState>

    <div v-if="auth.canBlock('overview.risk') || auth.canBlock('overview.clues')" class="two-col">
      <el-card v-if="auth.canBlock('overview.risk')" shadow="never">
        <template #header>
          <div class="card-title">区域 × 时段风险热力 <span class="hint">颜色越深总分越高，点击格子查看命中明细</span></div>
        </template>
        <AsyncState :loading="risk.loading.value" :error="risk.error.value" :data="risk.data.value" empty-text="暂无区域时段评分" @retry="risk.run">
          <EChart v-if="heatOption" :option="heatOption" height="300px" @click="onHeatClick" />
        </AsyncState>
      </el-card>

      <el-card v-if="auth.canBlock('overview.clues')" shadow="never">
        <template #header>
          <div class="card-title">最新线索 Top 5 <router-link class="link hint" :to="{ name: 'clues' }">全部线索</router-link></div>
        </template>
        <AsyncState :loading="clues.loading.value" :error="clues.error.value" :data="clues.data.value" empty-text="暂无线索" @retry="clues.run">
          <el-table v-if="clues.data.value" :data="clues.data.value.list" size="small" class="clickable-rows" @row-click="(r) => router.push({ name: 'clue-detail', params: { clueId: r.clue_id } })">
            <el-table-column label="编号" prop="clue_id" width="130"><template #default="{ row }"><span class="mono">{{ row.clue_id }}</span></template></el-table-column>
            <el-table-column label="对象" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.object_type === 2 ? `个人 ${row.object_id}` : `${row.area_name} ${pad2(row.hour_slot)} 点` }}</template>
            </el-table-column>
            <el-table-column label="等级" width="90"><template #default="{ row }"><LevelTag :level="row.risk_level" /></template></el-table-column>
            <el-table-column label="状态" width="80"><template #default="{ row }"><StatusTag type="clue_status" :value="row.clue_status" /></template></el-table-column>
          </el-table>
        </AsyncState>
      </el-card>
    </div>

    <el-card v-else shadow="never">
      <template #header><div class="card-title">你的工作入口</div></template>
      <p class="muted">当前角色不查看线索与研判结果（《前端交接文档》第十节权限要求），可进入以下模块：</p>
      <div class="entries">
        <el-button v-for="e in entries" :key="e.name" @click="router.push({ name: e.name })">{{ e.title }}</el-button>
        <span v-if="!entries.length" class="muted">数据管理员的信息库明细与导入质量报告页面不在本期 12 个页面内；可在页脚查看数据健康检查。</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/composables/useAsync'
import { pad2, percent } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'
import LevelTag from '@/components/LevelTag.vue'
import StatusTag from '@/components/StatusTag.vue'

const router = useRouter()
const auth = useAuthStore()

const ov = useAsync(() => api.overview())
const risk = useAsync(() => api.regionRisk({ size: 200 }), { immediate: auth.canBlock('overview.risk') })
const clues = useAsync(() => api.clues({ order: 'latest', size: 5 }), { immediate: auth.canBlock('overview.clues') })

const entries = computed(() => [
  { name: 'features', page: 'features', title: '特征清单' },
  { name: 'ops', page: 'ops', title: '版本与批次' },
  { name: 'cases', page: 'cases', title: '历史案件' },
  { name: 'audit', page: 'audit', title: '审计日志' },
  { name: 'admin', page: 'admin', title: '系统管理' },
].filter((e) => auth.canPage(e.page)))

// 热力：纵轴"区域·日期类型"，横轴小时，数值为 v_region_risk.total_score
const heatOption = computed(() => {
  const rows = risk.data.value?.list
  if (!rows?.length) return null
  const ys = [...new Set(rows.map((r) => `${r.area_name}·${r.day_type_name}`))]
  const xs = [...new Set(rows.map((r) => r.hour_slot))].sort((a, b) => a - b)
  return {
    tooltip: {
      formatter: (p) => {
        const r = p.data.row
        return `${r.area_name} · ${r.day_type_name} · ${pad2(r.hour_slot)} 点<br/>总分 <b>${r.total_score}</b>（${r.risk_level_name}风险）<br/>命中 ${r.hit_cnt} 项 · 样本 ${r.sample_size}<br/>批次 ${r.batch_id}`
      },
    },
    grid: { left: 110, right: 20, top: 10, bottom: 60 },
    xAxis: { type: 'category', data: xs.map((h) => `${pad2(h)}时`), splitArea: { show: true } },
    yAxis: { type: 'category', data: ys, splitArea: { show: true } },
    visualMap: {
      min: 0, max: 9, calculable: false, orient: 'horizontal', left: 'center', bottom: 0,
      pieces: [
        { min: 0, max: 2.999, label: '低 <3', color: '#e4e7ed' },
        { min: 3, max: 5.999, label: '中 3–6', color: '#f3d19e' },
        { min: 6, label: '高 ≥6', color: '#d03050' },
      ],
      type: 'piecewise',
    },
    series: [{
      type: 'heatmap',
      data: rows.map((r) => ({ value: [xs.indexOf(r.hour_slot), ys.indexOf(`${r.area_name}·${r.day_type_name}`), r.total_score], row: r })),
      label: { show: true, formatter: (p) => p.value[2].toFixed(2) },
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
    }],
  }
})

function onHeatClick(p) {
  if (p.data?.row) router.push({ name: 'risk-detail', params: { scoreId: p.data.row.score_id } })
}
</script>

<style scoped>
.warn { color: var(--level-mid); }
.high { color: var(--level-high); }
.small { font-size: 18px; }
.clickable { cursor: pointer; transition: border-color 0.2s; }
.clickable:hover { border-color: var(--el-color-primary); }
.clickable-rows :deep(tr) { cursor: pointer; }
.entries { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.entries .el-button { margin-left: 0; }
</style>
