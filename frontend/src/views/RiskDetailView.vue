<template>
  <div class="page">
    <AsyncState :loading="loading" :error="error" :data="data" @retry="load">
      <template v-if="data">
        <div class="page-head">
          <div>
            <h2>{{ objectLabel(data.score) }}</h2>
            <p class="sub">
              研判对象 <span class="mono">{{ data.score.object_id }}</span>
              · 批次 <span class="mono">{{ data.score.batch_id }}</span>
              · 规则 <span class="mono">{{ data.score.rule_id }}</span>
              · 权重版本 <span class="mono">{{ data.score.version_id }}</span>
            </p>
          </div>
          <el-button :icon="Back" @click="router.back()">返回</el-button>
        </div>

        <div class="stat-grid">
          <div class="stat">
            <div class="label">总分</div>
            <div class="value">{{ fixed(data.score.total_score) }}</div>
            <div class="foot">低 &lt;3 · 中 3–6 · 高 ≥6</div>
          </div>
          <div class="stat">
            <div class="label">风险等级</div>
            <div class="value"><LevelTag :level="data.score.risk_level" class="lv" /></div>
            <div class="foot">{{ data.score.is_clue === 1 ? '已生成待核查线索' : '未达线索条件' }}</div>
          </div>
          <div class="stat">
            <div class="label">命中特征</div>
            <div class="value">{{ hitCnt }} / {{ data.features.length }}</div>
            <div class="foot">数据不足 {{ missingCnt }} 项（不计入命中也不算未命中）</div>
          </div>
          <div class="stat">
            <div class="label">样本量</div>
            <div class="value">{{ data.score.sample_size }}</div>
            <div class="foot">该对象在数据窗内归集到的流水条数</div>
          </div>
        </div>

        <el-card shadow="never">
          <template #header>
            <div class="card-title">为什么提示：逐条特征判定明细 <span class="hint">每条被评估的特征一行（risk_score_feature），包含未命中项，才能区分"没命中"与"没评估"</span></div>
          </template>
          <FeatureJudgeTable :features="data.features" :total-score="data.score.total_score" />
        </el-card>

        <el-alert type="info" :closable="false" show-icon
          title="本页只解释评分由哪些特征构成，不代表对任何个人或场所作出定性结论。" />
      </template>
    </AsyncState>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'
import { api } from '@/api'
import { useAsync } from '@/composables/useAsync'
import { fixed, objectLabel } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import LevelTag from '@/components/LevelTag.vue'
import FeatureJudgeTable from '@/components/FeatureJudgeTable.vue'

const route = useRoute()
const router = useRouter()
const { data, loading, error, run: load } = useAsync(() => api.scoreFeatures(route.params.scoreId))

const hitCnt = computed(() => data.value.features.filter((f) => f.is_hit === 1 && f.is_missing !== 1).length)
const missingCnt = computed(() => data.value.features.filter((f) => f.is_missing === 1).length)
</script>

<style scoped>
.lv { font-size: 16px; padding: 4px 14px; }
</style>
