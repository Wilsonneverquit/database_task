<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>线索列表</h2>
        <p class="sub">线索只存状态机：待核查 → 核查中 → 已确认 / 已排除。分数与命中理由通过 score_id 追溯到评分与明细（视图 v_clue_list）。</p>
      </div>
      <div class="toolbar">
        <el-radio-group v-model="filters.status" @change="reload">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="o in enumOptions('clue_status')" :key="o.value" :value="o.value">{{ o.label }}</el-radio-button>
        </el-radio-group>
        <el-select v-model="filters.risk_level" placeholder="全部等级" clearable style="width: 120px" @change="reload">
          <el-option v-for="o in enumOptions('risk_level')" :key="o.value" :label="`${o.label}风险`" :value="o.value" />
        </el-select>
      </div>
    </div>

    <el-card shadow="never">
      <AsyncState :loading="loading" :error="error" :data="data" empty-text="没有符合条件的线索" @retry="load">
        <el-table v-if="data" :data="data.list" class="clickable-rows" :row-class-name="({ row }) => (row.clue_id === route.params.clueId ? 'current-row' : '')" @row-click="open">
          <el-table-column label="编号" width="140"><template #default="{ row }"><span class="mono">{{ row.clue_id }}</span></template></el-table-column>
          <el-table-column label="研判对象" min-width="150">
            <template #default="{ row }">
              <template v-if="row.object_type === 2"><el-tag size="small" type="info">个人</el-tag> <span class="mono">{{ row.object_id }}</span></template>
              <template v-else>{{ row.area_name }}</template>
            </template>
          </el-table-column>
          <el-table-column label="时段" width="120"><template #default="{ row }"><span class="num">{{ hourLabel(row.hour_slot) }}</span></template></el-table-column>
          <el-table-column label="等级" width="100"><template #default="{ row }"><LevelTag :level="row.risk_level" /></template></el-table-column>
          <el-table-column label="分数" width="80" align="right"><template #default="{ row }"><b class="num">{{ fixed(row.total_score) }}</b></template></el-table-column>
          <el-table-column label="命中理由" min-width="200" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono small">{{ row.hit_features || '—' }}</span></template>
          </el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><StatusTag type="clue_status" :value="row.clue_status" /></template></el-table-column>
          <el-table-column label="承办人" prop="assignee_name" width="100" />
          <el-table-column label="生成时间" prop="create_at" width="165" />
        </el-table>
        <el-pagination v-if="data && data.total > filters.size" class="pager" layout="total, prev, pager, next" :total="data.total"
          :page-size="filters.size" v-model:current-page="filters.page" @current-change="load" />
      </AsyncState>
    </el-card>

    <ClueDrawer :clue-id="route.params.clueId || null" @close="close" @changed="load" />
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { enumOptions } from '@/constants/enums'
import { useAsync } from '@/composables/useAsync'
import { fixed, hourLabel } from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import LevelTag from '@/components/LevelTag.vue'
import StatusTag from '@/components/StatusTag.vue'
import ClueDrawer from '@/components/ClueDrawer.vue'

const route = useRoute()
const router = useRouter()
const filters = reactive({
  status: route.query.status !== undefined ? Number(route.query.status) : '',
  risk_level: '',
  page: 1,
  size: 20,
})

const { data, loading, error, run: load } = useAsync(() => api.clues(filters))

function reload() {
  filters.page = 1
  load()
}

// C2 用抽屉打开，同时保留 /clues/:clueId 路由，便于直接分享与从概览页跳入
const open = (row) => router.push({ name: 'clue-detail', params: { clueId: row.clue_id } })
const close = () => router.push({ name: 'clues' })
</script>

<style scoped>
.clickable-rows :deep(tr) { cursor: pointer; }
.small { font-size: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
