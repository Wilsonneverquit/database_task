<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>评估报告</h2>
        <p class="sub">用观察段埋入的评估标签（eval_label）对照研判结果。标签只在评估时关联，研判过程绝不读取。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="batchId" placeholder="全部批次" clearable filterable style="width: 200px" @change="cm.run">
          <el-option v-for="b in batches.data.value?.list || []" :key="b.batch_id" :label="b.batch_id" :value="b.batch_id" />
        </el-select>
      </div>
    </div>

    <AsyncState :loading="cm.loading.value" :error="cm.error.value" :data="cm.data.value" @retry="cm.run">
      <template v-if="cm.data.value">
        <div class="stat-grid">
          <div v-for="m in metrics" :key="m.key" class="stat">
            <div class="label">{{ m.label }}</div>
            <div class="value">{{ fixed(cm.data.value[m.key], 2) }}</div>
            <div class="foot mono">{{ m.formula }}</div>
          </div>
        </div>

        <div class="two-col">
          <el-card shadow="never">
            <template #header><div class="card-title">混淆矩阵 <span class="hint">样本 {{ cm.data.value.sample_total }} 个</span></div></template>
            <table class="cm">
              <thead>
                <tr><th /><th>出线索（预测为正）</th><th>未出线索（预测为负）</th></tr>
              </thead>
              <tbody>
                <tr>
                  <th>确有酒驾（label=1）</th>
                  <td class="tp"><b>{{ cm.data.value.tp }}</b><span>TP 真阳性</span></td>
                  <td class="fn"><b>{{ cm.data.value.fn }}</b><span>FN 漏报</span></td>
                </tr>
                <tr>
                  <th>无酒驾（label=0）</th>
                  <td class="fp"><b>{{ cm.data.value.fp }}</b><span>FP 误报</span></td>
                  <td class="tn"><b>{{ cm.data.value.tn }}</b><span>TN 真阴性</span></td>
                </tr>
              </tbody>
            </table>
            <p class="muted small">
              口径与《前端交接文档》第八节一致：eval_label LEFT JOIN risk_score（按 object_type + object_id），以评分表 is_clue 判定是否出线索；
              指标由接口计算返回，前端不自行计算，分母为 0 时显示"—"。
            </p>
          </el-card>

          <el-card shadow="never">
            <template #header>
              <div class="card-title">标签分布 <span class="hint">干扰样本占比 {{ percent(cm.data.value.noise_ratio, 0) }}（要求 ≥ 30%）</span></div>
            </template>
            <AsyncState :loading="labels.loading.value" :error="labels.error.value" :data="labels.data.value" @retry="labels.run">
              <EChart v-if="labels.data.value" :option="pieOption" height="260px" />
            </AsyncState>
          </el-card>
        </div>
      </template>
    </AsyncState>

    <el-alert type="warning" :closable="false" show-icon title="以上为模拟数据上的指标，仅用于验证研判流程，不代表真实执法效果。" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '@/api'
import { useAsync } from '@/composables/useAsync'
import { fixed, percent } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'

const metrics = [
  { key: 'precision', label: '精确率', formula: 'TP / (TP + FP)' },
  { key: 'recall', label: '召回率', formula: 'TP / (TP + FN)' },
  { key: 'fpr', label: '误报率', formula: 'FP / (FP + TN)' },
  { key: 'f1', label: 'F1', formula: '2PR / (P + R)' },
]

const batchId = ref('')
const cm = useAsync(() => api.confusion({ batch_id: batchId.value }))
const labels = useAsync(() => api.labels())
const batches = useAsync(() => api.batches({ size: 100, run_status: 2 }))

const pieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}：{c} 个（{d}%）' },
  legend: { bottom: 0 },
  color: ['#d03050', '#e6a23c', '#909399'],
  series: [{
    type: 'pie', radius: ['40%', '68%'], center: ['50%', '45%'],
    label: { formatter: '{b}\n{c}' },
    data: labels.data.value.map((l) => ({ name: l.name, value: l.cnt })),
  }],
}))
</script>

<style scoped>
.cm { width: 100%; border-collapse: collapse; text-align: center; }
.cm th, .cm td { border: 1px solid var(--card-border); padding: 14px 10px; }
.cm thead th { background: #fafafa; font-weight: 600; font-size: 13px; }
.cm tbody th { background: #fafafa; font-weight: 600; font-size: 13px; width: 30%; }
.cm td b { display: block; font-size: 28px; font-variant-numeric: tabular-nums; }
.cm td span { font-size: 12px; color: var(--text-muted); }
.tp, .tn { background: #f0f9eb; }
.fp, .fn { background: #fef0f0; }
.small { font-size: 12px; line-height: 1.7; }
</style>
