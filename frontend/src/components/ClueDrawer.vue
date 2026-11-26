<template>
  <el-drawer :model-value="!!clueId" class="clue-drawer" size="min(1240px, 100vw)" :title="`线索详情 ${clueId || ''}`" @close="$emit('close')">
    <AsyncState :loading="loading" :error="error" :data="data" @retry="load">
      <template v-if="data">
        <div class="clue-workspace"><div class="clue-evidence">
        <div class="section head">
          <div>
            <div class="obj">{{ objectLabel(data.score) }}</div>
            <div class="meta muted">承办人 {{ data.clue.assignee_name || '未分配' }}</div>
            <el-collapse class="source-details"><el-collapse-item title="来源信息" name="source"><dl><dt>来源批次</dt><dd class="mono">{{ data.clue.batch_id }}</dd><dt>权重版本</dt><dd class="mono">{{ data.clue.version_id }}</dd><dt>生成时间</dt><dd>{{ data.clue.create_at }}</dd><dt>关闭时间</dt><dd>{{ data.clue.close_at || '—' }}</dd></dl></el-collapse-item></el-collapse>
          </div>
        </div>

        <el-alert type="info" :closable="false" show-icon
          title="本线索为待核查事项，仅提示风险等级与命中理由，不作定性结论，须经人工复核。" />

        <el-steps :active="data.clue.clue_status >= 2 ? 3 : data.clue.clue_status" finish-status="success" simple class="clue-progress">
          <el-step title="待核查" /><el-step title="核查中" /><el-step :title="data.clue.clue_status === 3 ? '已排除' : data.clue.clue_status === 2 ? '已确认' : '核查结果'" />
        </el-steps>
        <el-tabs v-model="activeTab">
          <el-tab-pane label="证据链" name="chain"><EvidenceChain v-if="activeTab==='chain'" :clue-id="clueId" /></el-tab-pane>
          <el-tab-pane label="命中依据" name="evidence">
        <div class="section">
          <div class="section-title">
            命中特征
            <router-link class="link small" :to="{ name: 'risk-detail', params: { scoreId: data.score.score_id } }" v-if="auth.canPage('risk')">在风险详情中查看</router-link>
          </div>
          <FeatureJudgeTable :features="data.features" :total-score="data.score.total_score" />
        </div>

          </el-tab-pane>
          <el-tab-pane :label="`核查记录（${data.feedbacks.length}）`" name="records">
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
          </el-tab-pane>
        </el-tabs>
        </div>
        <aside class="clue-summary" aria-label="核查摘要与操作">
          <h3>核查摘要</h3><div class="num big">{{ fixed(data.score.total_score) }} <small>分</small></div>
          <div class="summary-tags"><LevelTag :level="data.score.risk_level" /><StatusTag type="clue_status" :value="data.clue.clue_status" /></div>
          <dl><dt>研判对象</dt><dd>{{ objectLabel(data.score) }}</dd><dt>承办人</dt><dd>{{ data.clue.assignee_name || '未分配' }}</dd><dt>生成时间</dt><dd>{{ data.clue.create_at }}</dd><dt>关闭时间</dt><dd>{{ data.clue.close_at || '—' }}</dd></dl>
          <p class="muted small">{{ footerHint }}</p>
          <ClueActions :status="data.clue.clue_status" :can-act="canAct" :acting="acting" @start="startCheck" @feedback="feedbackAction" />
        </aside></div>
      </template>
    </AsyncState>

    <template #footer v-if="data">
      <div class="footer">
        <span class="muted small">{{ footerHint }}</span>
        <ClueActions :status="data.clue.clue_status" :can-act="canAct" :acting="acting" @start="startCheck" @feedback="feedbackAction" />
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
import ClueActions from './ClueActions.vue'
import FeatureJudgeTable from './FeatureJudgeTable.vue'
import FeedbackDialog from './FeedbackDialog.vue'
import EvidenceChain from './EvidenceChain.vue'

const props = defineProps({ clueId: { type: String, default: null } })
const emit = defineEmits(['close', 'changed'])
const auth = useAuthStore()

const activeTab = ref('chain')
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
watch(() => props.clueId, (id) => { data.value = null; activeTab.value = 'chain'; if (id) load() }, { immediate: true })

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

function feedbackAction({preset,lock,title}) { openFeedback(preset,lock,title) }

function openFeedback(preset, lock, title) {
  Object.assign(dialog, { open: true, preset, lock, title })
}

async function onSubmitted() {
  await load()
  activeTab.value = 'records'
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
.big { font-size: 36px; font-family:var(--font-data); font-weight: 500; }
.fb { display: flex; align-items: center; gap: 10px; }
.remark { margin: 6px 0; }
.wrong { font-size: 13px; }
.mr { margin-right: 6px; }
.small { font-size: 12px; font-weight: 400; }
.footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.source-details { margin-top: 12px; max-width: 480px; }
.source-details dl { display: grid; grid-template-columns: 80px 1fr; gap: 8px; margin: 0; }
.source-details dt { color: var(--text-muted); }.source-details dd { margin: 0; overflow-wrap: anywhere; }
.clue-progress { margin: 20px 0; }
@media(max-width:700px) { .head { flex-direction: column; }.score { flex-wrap: wrap; }.footer { flex-wrap: wrap; }.clue-progress { padding: 12px 8px; }.clue-progress :deep(.el-step__title) { font-size:12px; white-space:nowrap; } }
:deep(.el-alert) { margin-bottom: 16px; }
</style>

<style scoped>
.clue-workspace { display:grid; grid-template-columns:minmax(0,1fr) 320px; gap:24px; height:calc(100dvh - 125px); }.clue-evidence { overflow-y:auto; min-width:0; padding:0 8px 20px 0; }.clue-summary { width:100%; align-self:start; max-height:100%; overflow-y:auto; background:var(--surface-raised); border-radius:12px; padding:20px; }.clue-summary h3 { font-size:16px; margin:0 0 24px; }.clue-summary small { font-size:14px; font-weight:400; }.summary-tags { display:flex; gap:10px; margin:12px 0 24px; }.clue-summary dl { margin:0; }.clue-summary dt { color:var(--text-muted); font-size:12px; margin-top:16px; }.clue-summary dd { margin:6px 0 0; line-height:1.7; overflow-wrap:anywhere; }.clue-summary :deep(.clue-actions) { flex-direction:column; margin-top:20px; }.clue-summary :deep(.clue-actions .el-button) { width:100%; }
:deep(.el-drawer__footer) { display:none; }
@media(max-width:1000px) { .clue-workspace { display:flex; flex-direction:column-reverse; height:auto; }.clue-summary { max-height:none; }.clue-summary dl { display:none; }.clue-summary h3 { margin-bottom:12px; }.clue-summary :deep(.clue-actions),.clue-summary > .small { display:none; }.clue-evidence { overflow:visible; padding:0; }.clue-summary .big { font-size:26px; }.summary-tags { margin-bottom:0; }:deep(.el-drawer__footer) { display:block; } }
</style>

<style>
/* Drawer 的 footer 由组件库生成，不带本组件的 scoped 标记。 */
.clue-drawer > .el-drawer__footer { display:none; }
@media(max-width:1000px) { .clue-drawer > .el-drawer__footer { display:block; } }
</style>
