<template>
  <div class="login">
    <div class="panel">
      <div class="intro"><el-icon class="intro-symbol" :size="38"><Odometer /></el-icon>
        <h1>多风险特征预警系统</h1>
        <p class="lead">以酒驾为例 · 数据库原理课程设计 · 第 6 组</p>
        <ul>
          <li>从历史案件统计风险特征，扫描日常数据，按"区域 + 时段"打分</li>
          <li>达到阈值生成<strong>待核查线索</strong>，交人工核实</li>
          <li>核查结论回流，标记被否定的特征，修正下一轮权重</li>
        </ul>
        <p class="boundary">系统只输出风险等级、待核查线索与命中理由，不作定性结论。数据全部由脚本模拟生成，不含真实个人信息。</p>
      </div>

      <el-card class="form-card" shadow="never">
        <h3>登录</h3>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="如 analyst1" :prefix-icon="User" autocomplete="username" />
          </el-form-item>
          <el-form-item label="口令" prop="password">
            <el-input v-model="form.password" type="password" show-password :prefix-icon="Lock" autocomplete="current-password" />
          </el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="full">登录</el-button>
        </el-form>

        <div class="demo">
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
import { API_MODE } from '@/api'
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
.login { min-height: 100%; display: flex; align-items: center; justify-content: center; padding: 24px; background:linear-gradient(135deg,#142740,var(--page-bg) 65%); }
.panel { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 40px; max-width: 1060px; width: 100%; align-items: center; }
@media (max-width: 860px) { .panel { grid-template-columns: minmax(0, 1fr); } }
.intro { color: var(--text-primary); }
.intro h1 { font-size:clamp(28px,3vw,38px); font-weight:600; margin: 0 0 8px; }
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
.intro-symbol{color:var(--accent-ink);margin-bottom:26px}.intro h1{letter-spacing:-.025em;line-height:1.4}.intro .lead{line-height:1.8;margin-bottom:28px}.intro ul{padding-left:20px;font-size:14px;line-height:2.1}.intro .boundary{max-width:48ch}.form-card :deep(.el-card__body){padding:32px}.form-card h3{font-size:22px;font-weight:500;margin-bottom:26px}.full{min-height:42px;margin-top:6px}.accounts .el-button{height:auto;min-height:34px;padding:8px 10px;flex-wrap:wrap}.demo{line-height:1.8}@media(max-width:600px){.login{padding:24px 16px;align-items:flex-start}.panel{gap:24px}.intro-symbol{margin-bottom:16px}.form-card :deep(.el-card__body){padding:22px}.intro .boundary{max-width:none}}
</style>
