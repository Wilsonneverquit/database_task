<template>
  <div class="login">
    <div class="panel">
      <div class="intro">
        <h1>多风险特征预警系统</h1>
        <p class="lead">以酒驾为例 · 数据库原理课程设计 · 第 6 组</p>
        <ul>
          <li>从历史案件统计风险特征，扫描日常数据，按"区域 + 时段"打分</li>
          <li>达到阈值生成<strong>待核查线索</strong>，交人工核实</li>
          <li>核查结论回流，标记被否定的特征，修正下一轮权重</li>
        </ul>
        <p class="boundary">{{ DATA_SOURCE === 'real' ? '公开数据包含场所名录、匿名网约车订单和城市月度销售统计。' : '演示数据由业务规则生成，可用于体验完整的研判流程。' }}</p>
      </div>

      <el-card class="form-card" shadow="never">
        <h3>{{ DATA_SOURCE === 'real' ? '公开数据库' : '模拟数据库' }}登录</h3>
        <a :href="DATA_SOURCE === 'real' ? '/login?source=demo' : '/login?source=real'">切换到{{ DATA_SOURCE === 'real' ? '模拟' : '公开' }}数据库</a>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="如 analyst1" :prefix-icon="User" autocomplete="username" />
          </el-form-item>
          <el-form-item label="口令" prop="password">
            <el-input v-model="form.password" type="password" show-password :prefix-icon="Lock" autocomplete="current-password" />
          </el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="full">登录</el-button>
        </el-form>

        <div v-if="DATA_SOURCE === 'demo'" class="demo">
          <div class="muted small">演示账号（取自示例库，口令均为 123456），点击填入：</div>
          <div class="accounts">
            <el-button v-for="a in DEMO" :key="a.username" size="small" @click="fill(a.username)">
              {{ a.label }}<span class="muted mono">&nbsp;{{ a.username }}</span>
            </el-button>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { DATA_SOURCE } from '@/api'
import { useAuthStore } from '@/stores/auth'

const DEMO = [
  { username: 'analyst1', label: '研判员（兼教师）' },
  { username: 'analyst2', label: '研判员' },
  { username: 'featop', label: '特征管理员' },
  { username: 'admin', label: '系统管理员' },
  { username: 'teacher', label: '教师/评审' },
  { username: 'dataop', label: '数据管理员' },
]

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入口令', trigger: 'blur' }],
}

function fill(username) {
  form.username = username
  form.password = '123456'
}

async function submit() {
  if (!(await formRef.value.validate().catch(() => false))) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    router.replace(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login { min-height: 100%; display: flex; align-items: center; justify-content: center; padding: 24px; background: var(--page-bg); }
.panel { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 40px; max-width: 980px; width: 100%; align-items: center; }
@media (max-width: 860px) { .panel { grid-template-columns: minmax(0, 1fr); } }
.intro { color: var(--text-primary); }
.intro h1 { font-size: 32px; font-weight:500; margin: 0 0 8px; }
.lead { color: var(--text-secondary); margin: 0 0 20px; }
.intro ul { padding-left: 18px; line-height: 2; color: var(--text-secondary); }
.boundary { margin-top: 20px; font-size: 13px; color: var(--text-muted); border-left: 1px solid var(--card-border); padding-left: 16px; line-height: 1.7; }
.form-card { border-radius:16px; }
.form-card h3 { margin: 0 0 16px; }
.full { width: 100%; }
.demo { margin-top: 20px; border-top: 1px dashed var(--card-border); padding-top: 14px; }
.small { font-size: 12px; }
.accounts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.accounts .el-button { margin-left: 0; }
</style>
