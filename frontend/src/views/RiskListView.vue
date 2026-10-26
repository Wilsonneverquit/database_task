<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>区域时段风险</h2>
        <p class="sub">研判对象 = 区域 + 日期类型 + 小时。数据来自视图 v_region_risk，点击行查看逐条特征判定明细。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="filters.batch_id" placeholder="全部批次" clearable filterable style="width: 190px" @change="reload">
          <el-option v-for="b in batchOptions" :key="b.batch_id" :label="b.batch_id" :value="b.batch_id">
            <span class="mono">{{ b.batch_id }}</span> <span class="muted">{{ b.area_name || '全部区域' }}</span>
          </el-option>
        </el-select>
        <el-select v-model="filters.area_id" placeholder="全部区域" clearable style="width: 150px" @change="reload">
          <el-option v-for="a in dicts?.areas || []" :key="a.area_id" :label="a.area_name" :value="a.area_id" />
        </el-select>
        <el-select v-model="filters.risk_level" placeholder="全部等级" clearable style="width: 120px" @change="reload">
          <el-option v-for="o in enumOptions('risk_level')" :key="o.value" :label="`${o.label}风险`" :value="o.value" />
        </el-select>
      </div>
    </div>

    <el-card shadow="never">
      <AsyncState :loading="loading" :error="error" :data="data" empty-text="没有符合条件的研判对象" @retry="load">
        <el-table v-if="data" :data="data.list" class="clickable-rows" @row-click="(r) => router.push({ name: 'risk-detail', params: { scoreId: r.score_id } })">
          <el-table-column label="区域" min-width="130">
            <template #default="{ row }">{{ row.area_name }} <span class="muted mono">{{ row.area_id }}</span></template>
          </el-table-column>
          <el-table-column label="日期类型" prop="day_type_name" width="90" />
          <el-table-column label="时段" width="120"><template #default="{ row }"><span class="num">{{ hourLabel(row.hour_slot) }}</span></template></el-table-column>
          <el-table-column label="样本量" prop="sample_size" width="80" align="right" />
          <el-table-column label="命中数" prop="hit_cnt" width="80" align="right" />
          <el-table-column label="总分" width="90" align="right" sortable :sort-method="(a, b) => a.total_score - b.total_score">
            <template #default="{ row }"><b class="num">{{ fixed(row.total_score) }}</b></template>
          </el-table-column>
          <el-table-column label="等级" width="100"><template #default="{ row }"><LevelTag :level="row.risk_level" /></template></el-table-column>
          <el-table-column label="命中理由" min-width="220">
            <template #default="{ row }">
              <el-tag v-for="h in parseHitFeatures(row.hit_features)" :key="h.id" size="small" effect="plain" class="mr">{{ h.id }} {{ signed(h.weight) }}</el-tag>
              <span v-if="!row.hit_features" class="muted">无命中</span>
            </template>
          </el-table-column>
          <el-table-column label="是否出线索" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_clue === 1" type="danger" size="small">已出线索</el-tag>
              <span v-else class="muted">否</span>
            </template>
          </el-table-column>
          <el-table-column label="批次" width="130"><template #default="{ row }"><span class="mono muted">{{ row.batch_id }}</span></template></el-table-column>
        </el-table>
        <el-pagination v-if="data && data.total > filters.size" class="pager" layout="total, prev, pager, next" :total="data.total"
          :page-size="filters.size" v-model:current-page="filters.page" @current-change="load" />
      </AsyncState>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { enumOptions } from '@/constants/enums'
import { useAsync } from '@/composables/useAsync'
import { useDicts } from '@/composables/useDicts'
import { fixed, hourLabel, parseHitFeatures, signed } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import LevelTag from '@/components/LevelTag.vue'

const router = useRouter()
const dicts = useDicts()
const filters = reactive({ batch_id: '', area_id: '', risk_level: '', page: 1, size: 20 })

const { data, loading, error, run: load } = useAsync(() => api.regionRisk(filters))
const batches = useAsync(() => api.batches({ size: 100 }))
const batchOptions = computed(() => (batches.data.value?.list || []).filter((b) => b.judge_object === 1))

function reload() {
  filters.page = 1
  load()
}
</script>

<style scoped>
.clickable-rows :deep(tr) { cursor: pointer; }
.mr { margin-right: 4px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
