<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>历史案件</h2>
        <p class="sub">只读视图 v_case_history。特征提炼的唯一事实来源。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="filters.area_id" placeholder="全部区域" clearable style="width: 150px" @change="reload">
          <el-option v-for="a in dicts?.areas || []" :key="a.area_id" :label="a.area_name" :value="a.area_id" />
        </el-select>
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 250px" @change="reload" />
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon>
      <template #title>
        案例库只保留历史案件，观察段数据不在此表。时间边界 history_cutoff =
        <b class="mono">{{ data?.history_cutoff || '…' }}</b>，全库只在参数表写这一处。
      </template>
    </el-alert>

    <el-card shadow="never">
      <AsyncState :loading="loading" :error="error" :data="data" empty-text="没有符合条件的历史案件" @retry="load">
        <el-table v-if="data" :data="data.list">
          <el-table-column label="案件编号" width="140"><template #default="{ row }"><span class="mono">{{ row.case_id }}</span></template></el-table-column>
          <el-table-column label="发生时间" prop="occur_time" width="165" />
          <el-table-column label="时段" width="70" align="right"><template #default="{ row }">{{ row.occur_hour }} 点</template></el-table-column>
          <el-table-column label="区域" width="110"><template #default="{ row }">{{ row.area_name }}</template></el-table-column>
          <el-table-column label="场所" width="90"><template #default="{ row }"><span class="mono small">{{ row.place_id }}</span></template></el-table-column>
          <el-table-column label="人员编号" width="90"><template #default="{ row }"><span class="mono small">{{ row.person_id }}</span></template></el-table-column>
          <el-table-column label="车辆编号" width="90"><template #default="{ row }"><span class="mono small">{{ row.vehicle_id }}</span></template></el-table-column>
          <el-table-column label="案件类型" width="100"><template #default="{ row }">{{ enumLabel('case_type', row.case_type) }}</template></el-table-column>
          <el-table-column label="酒精含量" width="100" align="right"><template #default="{ row }">{{ row.alcohol_value }} <span class="muted small">mg/100ml</span></template></el-table-column>
          <el-table-column label="离家距离" width="90" align="right"><template #default="{ row }">{{ row.distance_home }} km</template></el-table-column>
          <el-table-column label="驾驶人确认" width="100" align="center"><template #default="{ row }">{{ row.driver_confirmed ? '已确认' : '仅车辆归属' }}</template></el-table-column>
          <el-table-column label="处置" width="90"><template #default="{ row }">{{ enumLabel('dispose_status', row.dispose_status) }}</template></el-table-column>
        </el-table>
        <el-pagination v-if="data && data.total > filters.size" class="pager" layout="total, prev, pager, next" :total="data.total"
          :page-size="filters.size" v-model:current-page="filters.page" @current-change="load" />
        <p v-if="data" class="muted small">
          视图返回 {{ data.total }} 条（case_info 原表共 {{ data.case_info_total }} 条）。人员、车辆只显示编号，不显示姓名与车牌明文。
        </p>
      </AsyncState>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { api } from '@/api'
import { enumLabel } from '@/constants/enums'
import { useAsync } from '@/composables/useAsync'
import { useDicts } from '@/composables/useDicts'
import { halfOpenRange } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'

const dicts = useDicts()
const filters = reactive({ area_id: '', page: 1, size: 20 })
const range = ref(null)
const { data, loading, error, run: load } = useAsync(() => api.cases({ ...filters, ...halfOpenRange(range.value) }))

function reload() {
  filters.page = 1
  load()
}
</script>

<style scoped>
.small { font-size: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
