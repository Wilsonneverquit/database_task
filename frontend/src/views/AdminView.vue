<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>系统管理</h2>
        <p class="sub">用户、角色与口径参数。口令哈希与盐值不返回前端。</p>
      </div>
    </div>

    <el-tabs v-model="tab" type="border-card">
      <el-tab-pane label="用户" name="users">
        <AsyncState :loading="users.loading.value" :error="users.error.value" :data="users.data.value" @retry="users.run">
          <el-table v-if="users.data.value" :data="users.data.value">
            <el-table-column label="用户编号" width="100"><template #default="{ row }"><span class="mono">{{ row.user_id }}</span></template></el-table-column>
            <el-table-column label="用户名" prop="username" width="120" />
            <el-table-column label="姓名" prop="real_name" width="130" />
            <el-table-column label="角色" min-width="220">
              <template #default="{ row }">
                <el-tag v-for="r in row.roles" :key="r" size="small" class="mr">{{ ROLE_LABEL[r] || r }}</el-tag>
                <span v-if="!row.roles.length" class="muted">未分配</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90"><template #default="{ row }"><StatusTag type="user_status" :value="row.status" /></template></el-table-column>
          </el-table>
        </AsyncState>
      </el-tab-pane>

      <el-tab-pane label="角色与权限" name="roles">
        <el-table :data="roleRows" border>
          <el-table-column label="角色" width="150">
            <template #default="{ row }">{{ ROLE_LABEL[row.role] }}<div class="mono muted small">{{ row.role }}</div></template>
          </el-table-column>
          <el-table-column label="可访问页面" min-width="260">
            <template #default="{ row }"><el-tag v-for="p in row.pages" :key="p" size="small" effect="plain" class="mr">{{ p }}</el-tag></template>
          </el-table-column>
          <el-table-column label="可执行操作" min-width="260">
            <template #default="{ row }">
              <el-tag v-for="a in row.actions" :key="a" size="small" type="success" effect="plain" class="mr">{{ a }}</el-tag>
              <span v-if="!row.actions.length" class="muted">只读</span>
            </template>
          </el-table-column>
        </el-table>
        <p class="muted small">依据《前端交接文档》第十节：没有权限的菜单与按钮直接隐藏；教师只读，任何写操作都不给。</p>
      </el-tab-pane>

      <el-tab-pane label="参数配置" name="params">
        <AsyncState :loading="params.loading.value" :error="params.error.value" :data="params.data.value" @retry="params.run">
          <el-table v-if="params.data.value" :data="params.data.value">
            <el-table-column label="参数名" width="190"><template #default="{ row }"><span class="mono">{{ row.param_key }}</span></template></el-table-column>
            <el-table-column label="参数值" width="190"><template #default="{ row }"><b class="mono">{{ row.param_value }}</b></template></el-table-column>
            <el-table-column label="类型" width="110"><template #default="{ row }">{{ enumLabel('param_type', row.param_type) }}</template></el-table-column>
            <el-table-column label="含义" prop="param_desc" min-width="260" />
            <el-table-column label="更新时间" prop="updated_at" width="165" />
            <el-table-column v-if="auth.can('param.update')" label="操作" width="80" fixed="right">
              <template #default="{ row }"><el-button link type="primary" @click="edit(row)">修改</el-button></template>
            </el-table-column>
          </el-table>
        </AsyncState>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="editing.open" :title="`修改参数 ${editing.key}`" width="480px">
      <el-alert v-if="editing.key === 'history_cutoff'" type="warning" :closable="false" show-icon class="mb"
        title="这是全库唯一的时间边界：v_case_history 视图据此过滤历史案件，修改会直接影响特征统计与历史案件页。" />
      <el-input v-model="editing.value" class="mono" />
      <template #footer>
        <el-button @click="editing.open = false">取消</el-button>
        <el-button type="primary" :loading="editing.saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { ROLE_LABEL, enumLabel } from '@/constants/enums'
import { ACTION_ROLES, PAGE_ROLES } from '@/constants/permissions'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/composables/useAsync'
import AsyncState from '@/components/AsyncState.vue'
import StatusTag from '@/components/StatusTag.vue'

const PAGE_NAMES = { overview: 'A1 概览', risk: 'B 风险研判', clues: 'C 线索管理', features: 'D1/D2 特征库', ops: 'D3 版本与批次', eval: 'E1 评估', audit: 'E2 审计', admin: 'E3 管理', cases: 'E4 历史案件' }
const ACTION_NAMES = { 'clue.status': '线索状态流转', 'clue.feedback': '提交核查结论', 'feature.status': '启停特征', 'version.publish': '发布/归档版本', 'weight.recalc': '重算权重', 'batch.create': '创建批次', 'batch.run': '执行研判', 'param.update': '修改参数' }

const auth = useAuthStore()
const tab = ref('users')
const users = useAsync(() => api.users())
const params = useAsync(() => api.params())

const roleRows = computed(() => Object.keys(ROLE_LABEL).map((role) => ({
  role,
  pages: Object.entries(PAGE_ROLES).filter(([, rs]) => rs.includes(role)).map(([p]) => PAGE_NAMES[p]),
  actions: Object.entries(ACTION_ROLES).filter(([, rs]) => rs.includes(role)).map(([a]) => ACTION_NAMES[a]),
})))

const editing = reactive({ open: false, key: '', value: '', saving: false })
function edit(row) {
  Object.assign(editing, { open: true, key: row.param_key, value: row.param_value })
}
async function save() {
  editing.saving = true
  try {
    await api.setParam(editing.key, { param_value: editing.value })
    ElMessage.success('参数已更新，并写入审计日志')
    editing.open = false
    params.run()
  } catch (e) { ElMessage.error(e.message) } finally { editing.saving = false }
}
</script>

<style scoped>
.mr { margin: 2px 6px 2px 0; }
.small { font-size: 12px; }
.mb { margin-bottom: 12px; }
</style>
