<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>审计日志</h2>
        <p class="sub">关键操作留痕：谁 + 什么时候 + 改了什么。线索状态与权重变更由触发器自动写入（操作人取会话变量，取不到记 system）。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="filters.user_id" placeholder="全部人员" clearable style="width: 140px" @change="reload">
          <el-option v-for="u in users.data.value || []" :key="u.user_id" :label="u.real_name" :value="u.user_id" />
        </el-select>
        <el-select v-model="filters.op_type" placeholder="全部操作" clearable style="width: 120px" @change="reload">
          <el-option v-for="o in enumOptions('op_type')" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 250px" @change="reload" />
      </div>
    </div>

    <el-card shadow="never">
      <AsyncState :loading="loading" :error="error" :data="data" empty-text="没有符合条件的记录" @retry="load">
        <el-table v-if="data" :data="data.list">
          <el-table-column label="时间" prop="op_time" width="170" />
          <el-table-column label="操作人" width="130">
            <template #default="{ row }">{{ row.user_name || '—' }} <span class="muted mono small">{{ row.operator_tag }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="80"><template #default="{ row }"><el-tag size="small" effect="plain">{{ enumLabel('op_type', row.op_type) }}</el-tag></template></el-table-column>
          <el-table-column label="对象表" width="140"><template #default="{ row }"><span class="mono small">{{ row.table_name || '—' }}</span></template></el-table-column>
          <el-table-column label="记录" width="170"><template #default="{ row }"><span class="mono small">{{ row.record_pk || '—' }}</span></template></el-table-column>
          <el-table-column label="描述" prop="op_desc" min-width="240" />
        </el-table>
        <el-pagination v-if="data && data.total > filters.size" class="pager" layout="total, prev, pager, next" :total="data.total"
          :page-size="filters.size" v-model:current-page="filters.page" @current-change="load" />
      </AsyncState>
      <p class="muted small">日期筛选按半开区间传参：选 11-01 ~ 11-08 实际查询 [11-01 00:00:00, 11-09 00:00:00)，不会漏掉最后一天。</p>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { api } from '@/api'
import { enumLabel, enumOptions } from '@/constants/enums'
import { useAsync } from '@/composables/useAsync'
import { halfOpenRange } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'

const filters = reactive({ user_id: '', op_type: '', page: 1, size: 20 })
const range = ref(null)
const users = useAsync(() => api.users())
const { data, loading, error, run: load } = useAsync(() => api.audit({ ...filters, ...halfOpenRange(range.value) }))

function reload() {
  filters.page = 1
  load()
}
</script>

<style scoped>
.small { font-size: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
