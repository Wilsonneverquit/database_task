<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>版本与批次</h2>
        <p class="sub">特征权重按版本管理：草稿 → 发布 → 归档，同一风险类型只能有一个已发布版本。一次研判 = 一个批次，可重跑，已核查对象自动跳过。</p>
      </div>
    </div>

    <el-card shadow="never">
      <template #header><div class="card-title">特征库版本</div></template>
      <AsyncState :loading="versions.loading.value" :error="versions.error.value" :data="versions.data.value" @retry="versions.run">
        <el-table v-if="versions.data.value" :data="versions.data.value">
          <el-table-column label="版本编号" width="150"><template #default="{ row }"><span class="mono">{{ row.version_id }}</span></template></el-table-column>
          <el-table-column label="版本号" width="80"><template #default="{ row }">v{{ row.version_no }}</template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><StatusTag type="publish_status" :value="row.publish_status" /></template></el-table-column>
          <el-table-column label="统计样本" width="150"><template #default="{ row }">案件 {{ row.based_case_cnt }} / 对照 {{ row.based_ctrl_cnt }}</template></el-table-column>
          <el-table-column label="已算权重" width="90" align="center"><template #default="{ row }">{{ row.weight_cnt }} 条</template></el-table-column>
          <el-table-column label="计算时间" prop="calc_at" width="165" />
          <el-table-column label="发布人" prop="published_by_name" width="110" />
          <el-table-column label="说明" prop="remark" min-width="200" show-overflow-tooltip />
          <el-table-column v-if="auth.can('version.publish')" label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.publish_status !== 1" link type="primary" @click="publish(row)">{{ row.publish_status === 2 ? '回滚发布' : '发布' }}</el-button>
              <el-button v-if="row.publish_status === 1" link type="warning" @click="archive(row)">归档</el-button>
              <el-button v-if="auth.can('weight.recalc')" link :loading="recalcing === row.version_id" @click="recalc(row)">重算权重</el-button>
            </template>
          </el-table-column>
        </el-table>
      </AsyncState>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="batch-head">
          <div class="card-title">研判批次</div>
          <div class="toolbar">
            <el-select v-model="runStatus" placeholder="全部状态" clearable style="width: 120px" @change="batches.run">
              <el-option v-for="o in enumOptions('run_status')" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-button v-if="auth.can('batch.create')" type="primary" :icon="Plus" @click="openCreate">创建批次</el-button>
          </div>
        </div>
      </template>
      <AsyncState :loading="batches.loading.value" :error="batches.error.value" :data="batches.data.value" empty-text="没有符合条件的批次" @retry="batches.run">
        <el-table v-if="batches.data.value" :data="batches.data.value.list">
          <el-table-column label="批次" width="140"><template #default="{ row }"><span class="mono">{{ row.batch_id }}</span></template></el-table-column>
          <el-table-column label="规则" min-width="190" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono muted">{{ row.rule_id }}</span> {{ row.rule_name }}</template>
          </el-table-column>
          <el-table-column label="对象" width="90"><template #default="{ row }">{{ enumLabel('judge_object', row.judge_object) }}</template></el-table-column>
          <el-table-column label="区域" width="110"><template #default="{ row }">{{ row.area_name || '全部' }}</template></el-table-column>
          <el-table-column label="数据窗" min-width="200">
            <template #default="{ row }"><span class="small">{{ row.data_start.slice(0, 16) }} ~ {{ row.data_end.slice(0, 16) }}</span></template>
          </el-table-column>
          <el-table-column label="版本" width="130"><template #default="{ row }"><span class="mono small">{{ row.version_id }}</span></template></el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }"><StatusTag type="run_status" :value="running === row.batch_id ? 1 : row.run_status" /></template>
          </el-table-column>
          <el-table-column label="对象/线索" width="95" align="center"><template #default="{ row }">{{ row.object_cnt }} / {{ row.clue_cnt }}</template></el-table-column>
          <el-table-column label="耗时" width="85" align="right"><template #default="{ row }">{{ row.duration_ms ? `${row.duration_ms} ms` : '—' }}</template></el-table-column>
          <el-table-column label="操作人" prop="operator_name" width="100" />
          <el-table-column v-if="auth.can('batch.run')" label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button v-if="[0, 3].includes(row.run_status)" link type="primary" :loading="running === row.batch_id" :disabled="!!running && running !== row.batch_id" @click="run(row)">
                {{ row.run_status === 3 ? '重新执行' : '执行研判' }}
              </el-button>
              <span v-else class="muted small">—</span>
            </template>
          </el-table-column>
        </el-table>
      </AsyncState>
    </el-card>

    <el-dialog v-model="createOpen" title="创建研判批次" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="批次编号" prop="batch_id"><el-input v-model="form.batch_id" class="mono" /></el-form-item>
        <el-form-item label="研判规则" prop="rule_id">
          <el-select v-model="form.rule_id" style="width: 100%">
            <el-option v-for="r in dicts?.rules || []" :key="r.rule_id" :label="`${r.rule_id} ${r.rule_name}`" :value="r.rule_id" />
          </el-select>
          <div v-if="selectedRule" class="muted small">研判对象：{{ enumLabel('judge_object', selectedRule.judge_object) }} · 权重版本 {{ selectedRule.version_id }}</div>
        </el-form-item>
        <el-form-item v-if="selectedRule?.judge_object !== 2" label="限定区域">
          <el-select v-model="form.area_id" placeholder="全部区域" clearable style="width: 100%">
            <el-option v-for="a in dicts?.areas || []" :key="a.area_id" :label="`${a.area_id} ${a.area_name}`" :value="a.area_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据窗" prop="window">
          <el-date-picker v-model="form.window" type="datetimerange" value-format="YYYY-MM-DD HH:mm:ss" start-placeholder="起（含）" end-placeholder="止（不含）" style="width: 100%" />
          <div class="muted small">半开区间 [起, 止)。数据窗必须在观察段（≥ {{ dicts?.history_cutoff || 'history_cutoff' }}），研判不读历史段。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { api, API_MODE } from '@/api'
import { enumLabel, enumOptions } from '@/constants/enums'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/composables/useAsync'
import { useDicts } from '@/composables/useDicts'
import AsyncState from '@/components/AsyncState.vue'
import StatusTag from '@/components/StatusTag.vue'

const auth = useAuthStore()
const dicts = useDicts()
const runStatus = ref('')
const versions = useAsync(() => api.versions())
const batches = useAsync(() => api.batches({ run_status: runStatus.value, size: 100 }))
const recalcing = ref(null)
const running = ref(null)

const confirm = (msg, title, type = 'warning') =>
  ElMessageBox.confirm(msg, title, { type, confirmButtonText: '确定', cancelButtonText: '取消' }).then(() => true, () => false)

async function publish(row) {
  const warn = row.weight_cnt === 0 ? '\n注意：该版本尚未计算任何权重，发布后使用该版本的批次将无法研判。' : ''
  if (!(await confirm(`发布 v${row.version_no} 后，当前已发布版本会自动归档（同一风险类型只能有一个已发布版本）。${warn}`, '发布版本'))) return
  try {
    await api.publishVersion(row.version_id, { publish_status: 1 })
    ElMessage.success('已发布')
    versions.run()
  } catch (e) { ElMessage.error(e.message) }
}

async function archive(row) {
  if (!(await confirm(`归档 v${row.version_no} 后将没有已发布版本，特征清单不再显示权重。`, '归档版本'))) return
  try {
    await api.publishVersion(row.version_id, { publish_status: 2 })
    ElMessage.success('已归档')
    versions.run()
  } catch (e) { ElMessage.error(e.message) }
}

async function recalc(row) {
  recalcing.value = row.version_id
  try {
    const r = await api.recalcWeights({ version_id: row.version_id })
    if (r.feature_cnt === 0) ElMessage.warning('该版本没有命中统计记录，无权重可算')
    else ElMessage.success(`已重算 ${r.feature_cnt} 条权重，其中 ${r.changed_cnt} 条发生变化（变化会写入审计日志）`)
    versions.run()
  } catch (e) { ElMessage.error(e.message) } finally { recalcing.value = null }
}

async function run(row) {
  running.value = row.batch_id
  try {
    const r = await api.runBatch(row.batch_id)
    if (r.run_status === 3) {
      ElNotification({ type: 'error', title: `批次 ${row.batch_id} 执行失败`, message: r.message || '研判失败', duration: 6000 })
    } else {
      const skip = r.skipped_cnt ? `，跳过已核查对象 ${r.skipped_cnt} 个` : ''
      ElNotification({ type: 'success', title: `批次 ${row.batch_id} 执行成功`, message: `对象 ${r.object_cnt} 个，生成线索 ${r.clue_cnt} 条${skip}，耗时 ${r.duration_ms} ms${API_MODE === 'mock' ? '（前端模拟引擎）' : ''}`, duration: 6000 })
    }
    batches.run()
  } catch (e) { ElMessage.error(e.message) } finally { running.value = null }
}

// ---- 创建批次 ----
const createOpen = ref(false)
const creating = ref(false)
const formRef = ref(null)
const form = reactive({ batch_id: '', rule_id: 'R001', area_id: '', window: [] })
const rules = {
  batch_id: [{ required: true, pattern: /^B\d{10}$/, message: '格式为 B + 10 位数字，如 B2026111101', trigger: 'blur' }],
  rule_id: [{ required: true, message: '请选择研判规则' }],
  window: [{ required: true, type: 'array', len: 2, message: '请选择数据窗', trigger: 'change' }],
}
const selectedRule = computed(() => dicts.value?.rules.find((r) => r.rule_id === form.rule_id))

function openCreate() {
  const ids = (batches.data.value?.list || []).map((b) => b.batch_id)
  let seq = 1
  while (ids.includes(`B20261111${String(seq).padStart(2, '0')}`)) seq++
  Object.assign(form, { batch_id: `B20261111${String(seq).padStart(2, '0')}`, rule_id: 'R001', area_id: '', window: ['2026-11-06 00:00:00', '2026-11-09 00:00:00'] })
  createOpen.value = true
}

async function create() {
  if (!(await formRef.value.validate().catch(() => false))) return
  creating.value = true
  try {
    await api.createBatch({
      batch_id: form.batch_id,
      rule_id: form.rule_id,
      area_id: selectedRule.value?.judge_object === 2 ? null : form.area_id || null,
      data_start: form.window[0],
      data_end: form.window[1],
    })
    ElMessage.success('批次已创建，状态为"待执行"')
    createOpen.value = false
    batches.run()
  } catch (e) { ElMessage.error(e.message) } finally { creating.value = false }
}
</script>

<style scoped>
.batch-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.small { font-size: 12px; }
</style>
