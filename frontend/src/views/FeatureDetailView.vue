<template>
  <div class="page">
    <AsyncState :loading="loading" :error="error" :data="data" @retry="load">
      <template v-if="data">
        <div class="page-head">
          <div>
            <h2><span class="mono muted">{{ f.feature_id }}</span> {{ f.feature_name }}</h2>
            <p class="sub">
              <span class="mono">{{ f.feature_code }}</span> · {{ enumLabel('feature_cat', f.feature_cat) }} ·
              {{ enumLabel('feature_direction', f.direction) }} · 适用 {{ enumLabel('object_scope', f.object_scope) }} ·
              <StatusTag type="enable_status" :value="f.status" />
            </p>
          </div>
          <el-button :icon="Back" @click="router.back()">返回</el-button>
        </div>

        <div class="two-col">
          <el-card shadow="never">
            <template #header><div class="card-title">口径说明</div></template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="训练源（统计权重）"><span class="mono">{{ f.src_table }}</span> {{ SRC_TABLE_LABEL[f.src_table] }}</el-descriptions-item>
              <el-descriptions-item label="研判源（扫描数据）"><b class="mono primary">{{ f.match_src }}</b> {{ SRC_TABLE_LABEL[f.match_src] }}</el-descriptions-item>
              <el-descriptions-item label="判定口径">{{ f.match_expr }}</el-descriptions-item>
              <el-descriptions-item label="取值类型">{{ enumLabel('value_type', f.value_type) }}</el-descriptions-item>
              <el-descriptions-item label="时间窗">{{ f.time_window_min ? `${f.time_window_min} 分钟` : '不限（历史档案类）' }}</el-descriptions-item>
              <el-descriptions-item label="最小样本">{{ f.min_sample }}</el-descriptions-item>
              <el-descriptions-item label="设计说明">{{ f.description }}</el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card shadow="never">
            <template #header><div class="card-title">权重计算 <span class="hint">当前已发布版本</span></div></template>
            <div v-if="current" class="calc">
              <div class="formula">
                P1 = {{ current.case_hit }}/{{ current.case_total }} = {{ fixed(current.p1, 2) }}，
                P0 = {{ current.ctrl_hit }}/{{ current.ctrl_total }} = {{ fixed(current.p0, 2) }}
              </div>
              <div class="formula">
                Lift = P1 / P0 = {{ fixed(current.lift, 2) }} → 权重 <b :class="current.weight < 0 ? 'neg' : 'pos'">{{ signed(current.weight) }}</b>
              </div>
              <p class="muted small">
                P1 = 案件组出现率，P0 = 对照组（同期同区域未酒驾人群）出现率。权重由存储过程 sp_calc_feature_weight 按平滑对数优势比
                ln[((a+0.5)/(b+0.5)) / ((c+0.5)/(d+0.5))] 计算并截断到 ±3；P1/P0/提升度为生成列，自动维护。
              </p>
              <el-tag :type="current.is_valid ? 'success' : 'info'">{{ enumLabel('is_valid', current.is_valid) }}</el-tag>
            </div>
            <el-empty v-else description="当前已发布版本尚未计算该特征的权重" :image-size="60" />
          </el-card>
        </div>

        <el-card shadow="never">
          <template #header><div class="card-title">各版本权重变化</div></template>
          <EChart :option="chartOption" height="240px" />
          <p class="muted small">
            示例库中只有现行版本 1.0 有命中统计与权重；0.9（已归档）与 2.0（草稿）没有权重记录，图中显示为空。
          </p>
          <el-table :data="data.weights" size="small" border>
            <el-table-column label="版本" width="150"><template #default="{ row }"><span class="mono">{{ row.version_id }}</span> v{{ row.version_no }}</template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="{ row }"><StatusTag type="publish_status" :value="row.publish_status" /></template></el-table-column>
            <el-table-column label="案件命中" width="110" align="right"><template #default="{ row }">{{ row.case_hit }}/{{ row.case_total }}</template></el-table-column>
            <el-table-column label="对照命中" width="110" align="right"><template #default="{ row }">{{ row.ctrl_hit }}/{{ row.ctrl_total }}</template></el-table-column>
            <el-table-column label="P1" width="80" align="right"><template #default="{ row }">{{ fixed(row.p1, 4) }}</template></el-table-column>
            <el-table-column label="P0" width="80" align="right"><template #default="{ row }">{{ fixed(row.p0, 4) }}</template></el-table-column>
            <el-table-column label="提升度" width="90" align="right"><template #default="{ row }">{{ fixed(row.lift, 4) }}</template></el-table-column>
            <el-table-column label="权重" width="100" align="right"><template #default="{ row }"><b class="mono">{{ signed(row.weight) }}</b></template></el-table-column>
            <el-table-column label="计算时间" prop="calc_at" min-width="160" />
          </el-table>
        </el-card>

        <div class="two-col">
          <el-card shadow="never">
            <template #header><div class="card-title">核查否定记录 <span class="hint">闭环回写：误报中被核查人员否定的次数，作为下一轮调权输入</span></div></template>
            <el-empty v-if="!data.negations.length" description="暂无核查否定记录" :image-size="60" />
            <el-table v-else :data="data.negations" size="small">
              <el-table-column label="线索" width="140"><template #default="{ row }"><span class="mono">{{ row.clue_id }}</span></template></el-table-column>
              <el-table-column label="结论" width="80"><template #default="{ row }"><StatusTag type="check_result" :value="row.check_result" /></template></el-table-column>
              <el-table-column label="说明" prop="check_remark" min-width="180" show-overflow-tooltip />
              <el-table-column label="时间" prop="check_time" width="160" />
            </el-table>
          </el-card>
          <el-card shadow="never">
            <template #header><div class="card-title">所属研判规则</div></template>
            <el-table :data="data.rules" size="small">
              <el-table-column label="规则" width="80"><template #default="{ row }"><span class="mono">{{ row.rule_id }}</span></template></el-table-column>
              <el-table-column label="名称" prop="rule_name" min-width="180" />
              <el-table-column label="强特征" width="80" align="center"><template #default="{ row }">{{ row.is_required ? '是' : '否' }}</template></el-table-column>
            </el-table>
          </el-card>
        </div>
      </template>
    </AsyncState>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'
import { api } from '@/api'
import { SRC_TABLE_LABEL, enumLabel } from '@/constants/enums'
import { useAsync } from '@/composables/useAsync'
import { fixed, signed } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const { data, loading, error, run: load } = useAsync(() => api.featureDetail(route.params.featureId))

const f = computed(() => data.value.feature)
const current = computed(() => data.value.weights.find((w) => w.publish_status === 1) || null)

// 横轴为全部版本（按版本号），没有权重记录的版本显示为空点
const chartOption = computed(() => {
  const versions = [...data.value.versions].sort((a, b) => a.version_no.localeCompare(b.version_no, undefined, { numeric: true }))
  const byVersion = Object.fromEntries(data.value.weights.map((w) => [w.version_id, w.weight]))
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: versions.map((v) => `v${v.version_no}（${enumLabel('publish_status', v.publish_status)}）`) },
    yAxis: { type: 'value', name: '权重', min: -3, max: 3 },
    series: [{
      type: 'line', connectNulls: false, symbolSize: 10,
      data: versions.map((v) => byVersion[v.version_id] ?? null),
      label: { show: true, formatter: (p) => (p.value === null ? '' : signed(p.value)) },
      markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: '#c0c4cc' } },
    }],
  }
})
</script>

<style scoped>
.calc { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.small { font-size: 12px; line-height: 1.7; }
.primary { color: var(--el-color-primary); }
.pos { color: var(--level-high); }
.neg { color: #529b2e; }
</style>
