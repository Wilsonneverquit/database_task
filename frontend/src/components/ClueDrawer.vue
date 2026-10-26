<template>
  <el-drawer :model-value="!!clueId" size="760px" :title="`线索详情 ${clueId || ''}`" @close="$emit('close')">
    <AsyncState :loading="loading" :error="error" :data="data" @retry="load">
      <template v-if="data">
        <div class="section head">
          <div>
            <div class="obj">{{ objectLabel(data.score) }}</div>
            <div class="meta muted">
              来源批次 <span class="mono">{{ data.clue.batch_id }}</span> · 权重版本 <span class="mono">{{ data.clue.version_id }}</span>
              · 承办人 {{ data.clue.assignee_name || '—' }}
            </div>
            <div class="meta muted">生成 {{ data.clue.create_at }} · 关闭 {{ data.clue.close_at || '—' }}</div>
          </div>
          <div class="score">
            <div class="num big">{{ fixed(data.score.total_score) }}</div>
            <LevelTag :level="data.score.risk_level" />
            <StatusTag type="clue_status" :value="data.clue.clue_status" />
          </div>
        </div>

        <el-alert type="info" :closable="false" show-icon
          title="本线索为待核查事项，仅提示风险等级与命中理由，不作定性结论，须经人工复核。" />

        <div class="section">
          <div class="section-title">
            命中特征
            <router-link class="link small" :to="{ name: 'risk-detail', params: { scoreId: data.score.score_id } }" v-if="auth.canPage('risk')">在风险详情中查看</router-link>
          </div>
          <FeatureJudgeTable :features="data.features" :total-score="data.score.total_score" />
        </div>

        <div class="section">
          <div class="section-title">核查记录</div>
          <el-empty v-if="!data.feedbacks.length" description="尚无核查记录" :image-size="60" />
          <el-timeline v-else>
            <el-timeline-item v-for="f in data.feedbacks" :key="f.feedback_id" :timestamp="f.check_time" placement="top">
              <div class="fb">
                <StatusTag type="check_result" :value="f.check_result" />
                <span class="muted">{{ enumLabel('check_method', f.check_method) }} · {{ f.checker_name || f.checker_id }}</span>
              </div>
              <div class="remark">{{ f.check_remark }}</div>
              <div v-if="f.wrong_features.length" class="wrong">
                被否定的特征：
                <el-tag v-for="id in f.wrong_features" :key="id" size="small" type="warning" class="mr">{{ id }} {{ featureName(id) }}</el-tag>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </template>
    </AsyncState>

    <template #footer v-if="data">
      <div class="footer">
        <span class="muted small">{{ footerHint }}</span>
        <div v-if="canAct">
          <template v-if="data.clue.clue_status === 0">
            <el-button type="primary" :loading="acting" @click="startCheck">开始核查</el-button>
            <el-button @click="openFeedback(2, true, '直接排除')">直接排除</el-button>
          </template>
          <template v-else-if="data.clue.clue_status === 1">
            <el-button type="danger" @click="openFeedback(1, false, '确认属实')">确认属实</el-button>
            <el-button @click="openFeedback(2, false, '排除')">排除</el-button>
          </template>
        </div>
      </div>
    </template>

    <FeedbackDialog v-if="data" v-model="dialog.open" :clue-id="clueId" :features="data.features"
      :preset="dialog.preset" :lock-result="dialog.lock" :title="dialog.title" @submitted="onSubmitted" />
  </el-drawer>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { enumLabel } from '@/constants/enums'
import { fixed, objectLabel } from '@/utils/format'
import AsyncState from './AsyncState.vue'
import LevelTag from './LevelTag.vue'
import StatusTag from './StatusTag.vue'
import FeatureJudgeTable from './FeatureJudgeTable.vue'
import FeedbackDialog from './FeedbackDialog.vue'

const props = defineProps({ clueId: { type: String, default: null } })
const emit = defineEmits(['close', 'changed'])
const auth = useAuthStore()

const data = ref(null)
const loading = ref(false)
const error = ref(null)
const acting = ref(false)
const dialog = reactive({ open: false, preset: 1, lock: false, title: '' })

async function load() {
  if (!props.clueId) return
  loading.value = true
  error.value = null
  try {
    data.value = await api.clueDetail(props.clueId)
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}
watch(() => props.clueId, (id) => { data.value = null; if (id) load() }, { immediate: true })

// 只显示合法的流转按钮；没有写权限（如教师）则不显示任何操作
const canAct = computed(() => auth.can('clue.feedback') && [0, 1].includes(data.value?.clue.clue_status))
const footerHint = computed(() => {
  const st = data.value?.clue.clue_status
  if (!auth.can('clue.feedback')) return '当前角色为只读，不能处理线索'
  if (st === 2 || st === 3) return '线索已关闭，状态不可再改'
  return st === 0 ? '待核查 → 核查中 / 已排除' : '核查中 → 已确认 / 已排除'
})

const featureName = (id) => data.value?.features.find((f) => f.feature_id === id)?.feature_name || ''

async function startCheck() {
  acting.value = true
  try {
    await api.setClueStatus(props.clueId, { status: 1 })
    ElMessage.success('线索已进入"核查中"')
    await load()
    emit('changed')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    acting.value = false
  }
}

function openFeedback(preset, lock, title) {
  Object.assign(dialog, { open: true, preset, lock, title })
}

async function onSubmitted() {
  await load()
  emit('changed')
}
</script>

<style scoped>
.section { margin-bottom: 20px; }
.section-title { font-weight: 600; margin-bottom: 10px; display: flex; align-items: center; gap: 12px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.obj { font-size: 17px; font-weight: 600; }
.meta { font-size: 13px; margin-top: 4px; }
.score { display: flex; align-items: center; gap: 10px; }
.big { font-size: 30px; font-weight: 600; }
.fb { display: flex; align-items: center; gap: 10px; }
.remark { margin: 6px 0; }
.wrong { font-size: 13px; }
.mr { margin-right: 6px; }
.small { font-size: 12px; font-weight: 400; }
.footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
:deep(.el-alert) { margin-bottom: 16px; }
</style>
