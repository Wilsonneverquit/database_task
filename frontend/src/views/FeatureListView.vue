<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>特征清单</h2>
        <p class="sub">
          双口径：<b>训练源</b>（src_table）只用来统计 P1/P0 提炼权重，<b>研判源</b>（match_src）才是扫描日常数据时读的表。
          两者分开，保证研判时不会"拿答案猜答案"。
        </p>
      </div>
      <div class="toolbar">
        <el-select v-model="filters.cat" placeholder="全部分类" clearable style="width: 120px" @change="load">
          <el-option v-for="o in enumOptions('feature_cat')" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px" @change="load">
          <el-option v-for="o in enumOptions('enable_status')" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="card-title">权重取自当前已发布版本 <span class="mono hint">{{ data?.version_id || '—' }}</span></div>
      </template>
      <AsyncState :loading="loading" :error="error" :data="data" empty-text="没有符合条件的特征" @retry="load">
        <el-table v-if="data" :data="data.list" class="clickable-rows" @row-click="(r) => router.push({ name: 'feature-detail', params: { featureId: r.feature_id } })">
          <el-table-column label="编号" width="80"><template #default="{ row }"><span class="mono">{{ row.feature_id }}</span></template></el-table-column>
          <el-table-column label="名称" min-width="200">
            <template #default="{ row }">
              {{ row.feature_name }}
              <el-tag v-if="row.direction === 2" size="small" type="info">反例</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="分类" width="70"><template #default="{ row }">{{ enumLabel('feature_cat', row.feature_cat) }}</template></el-table-column>
          <el-table-column label="对象" width="100"><template #default="{ row }">{{ enumLabel('object_scope', row.object_scope) }}</template></el-table-column>
          <el-table-column label="训练源" width="130" class-name="col-train">
            <template #default="{ row }"><SrcCell :table="row.src_table" /></template>
          </el-table-column>
          <el-table-column label="研判源" width="140" class-name="col-match">
            <template #default="{ row }"><SrcCell :table="row.match_src" strong /></template>
          </el-table-column>
          <el-table-column label="权重" width="95" align="right">
            <template #default="{ row }">
              <span class="num mono" :class="row.weight < 0 ? 'neg' : ''">{{ signed(row.weight) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="提升度" width="80" align="right"><template #default="{ row }"><span class="num">{{ fixed(row.lift) }}</span></template></el-table-column>
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">
              <el-switch v-if="auth.can('feature.status')" :model-value="row.status === 1" inline-prompt active-text="启用" inactive-text="停用"
                :loading="toggling === row.feature_id" @click.stop @change="(v) => toggle(row, v)" />
              <StatusTag v-else type="enable_status" :value="row.status" />
            </template>
          </el-table-column>
        </el-table>
      </AsyncState>
    </el-card>
  </div>
</template>

<script setup>
import { h, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { SRC_TABLE_LABEL, enumLabel, enumOptions } from '@/constants/enums'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/composables/useAsync'
import { fixed, signed } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import StatusTag from '@/components/StatusTag.vue'

const SrcCell = (props) => h('div', { class: 'src' }, [
  h('div', { class: ['mono', props.strong ? 'src-strong' : 'muted'] }, props.table),
  h('div', { class: 'src-label' }, SRC_TABLE_LABEL[props.table] || ''),
])
SrcCell.props = ['table', 'strong']

const router = useRouter()
const auth = useAuthStore()
const filters = reactive({ cat: '', status: '' })
const toggling = ref(null)
const { data, loading, error, run: load } = useAsync(() => api.features(filters))

async function toggle(row, enabled) {
  if (!enabled) {
    const confirmed = await ElMessageBox.confirm(`停用后，新的研判批次将不再评估「${row.feature_name}」。`, '停用特征', { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' })
      .then(() => true, () => false)
    if (!confirmed) return
  }
  toggling.value = row.feature_id
  try {
    await api.setFeatureStatus(row.feature_id, { status: enabled ? 1 : 0 })
    ElMessage.success(enabled ? '已启用' : '已停用')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    toggling.value = null
  }
}
</script>

<style scoped>
.clickable-rows :deep(tr) { cursor: pointer; }
/* 用一条竖线把训练源与研判源分开，视觉上强调双口径（《前端交接文档》D1 原型要点） */
:deep(.col-match) { border-left: 3px solid var(--el-color-primary) !important; }
:deep(th.col-train), :deep(th.col-match) { background: #f0f5ff !important; }
:deep(.src-strong) { color: var(--el-color-primary); font-weight: 600; }
:deep(.src-label) { font-size: 12px; color: var(--text-muted); }
.neg { color: #529b2e; }
</style>
