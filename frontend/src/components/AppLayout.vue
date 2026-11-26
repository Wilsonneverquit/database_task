<template>
  <el-container class="layout" :class="{'nav-open': navOpen}">
    <el-aside :width="navExpanded ? '220px' : '72px'" class="aside" :class="{ expanded: navExpanded }" @keydown.esc="navOpen=false">
      <div class="brand">
        <el-tooltip :disabled="navExpanded" content="多风险特征预警系统" placement="right"><router-link to="/" class="brand-link" aria-label="多风险特征预警系统首页"><el-icon :size="24"><Odometer /></el-icon><span v-if="navExpanded">多风险特征预警系统</span></router-link></el-tooltip>
      </div>
      <nav class="rail-menu" aria-label="主导航">
        <div v-for="group in visibleMenu" :key="group.title" class="rail-group" :aria-label="group.title">
          <div v-if="navExpanded" class="group-title">{{ group.title }}</div>
          <el-tooltip v-for="item in group.items" :key="item.path" :content="item.title" :trigger="['hover','focus']" :disabled="navExpanded || navOpen" placement="right">
            <router-link :to="item.path" class="rail-link" :class="{ active: activeMenu===item.path }" :aria-current="activeMenu===item.path ? 'page' : undefined" :aria-label="item.title">
              <el-icon :size="18"><component :is="item.icon" /></el-icon><span class="rail-label">{{ item.title }}</span><span class="code">{{ item.code }}</span>
            </router-link>
          </el-tooltip>
        </div>
      </nav>
      <el-button class="rail-expand" text :aria-label="navExpanded ? '收起文字导航' : '展开文字导航'" :aria-expanded="navExpanded" @click="navExpanded=!navExpanded"><el-icon><component :is="navExpanded ? 'Fold' : 'Expand'" /></el-icon><span v-if="navExpanded">收起导航</span></el-button>
    </el-aside>

    <button v-if="navOpen" class="nav-backdrop" aria-label="关闭导航" @click="navOpen=false" />
    <el-container class="right">
      <el-header class="header">
        <el-button class="nav-toggle" text :aria-expanded="navOpen" aria-label="切换导航" @click="navOpen=!navOpen"><el-icon><Menu /></el-icon></el-button>
        <el-breadcrumb separator="/">
          <el-breadcrumb-item v-if="parentRoute" :to="{ name: parentRoute.name }">{{ parentRoute.meta.title }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta.title }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="header-right">
          <el-tooltip v-if="API_MODE === 'mock'" content="后端未就绪，当前使用前端内置的模拟数据（取自示例库）" placement="bottom">
            <el-tag type="warning" effect="plain">模拟数据模式</el-tag>
          </el-tooltip>
          <el-tag v-else type="success" effect="plain">{{ DATA_SOURCE === 'real' ? '公开数据库' : '模拟数据库' }}</el-tag>
          <el-dropdown trigger="click" @command="onCommand">
            <button type="button" class="user" aria-label="用户菜单">
              <el-icon><User /></el-icon>
              {{ auth.user?.real_name }}
              <el-tag v-for="r in auth.roles" :key="r" size="small" class="role-tag">{{ ROLE_LABEL[r] }}</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="API_MODE === 'mock'" command="reset" :icon="RefreshLeft">重置演示数据</el-dropdown-item>
                <el-dropdown-item command="logout" :icon="SwitchButton" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main" :class="{ 'canvas-main': route.name==='risk-map' }">
        <slot />
      </el-main>

      <el-footer class="footer" height="auto">
        <span>{{ DATA_SOURCE === 'real' ? '公开数据用于课程研究。来源及采集范围见数据管理。' : '模拟数据，仅用于教学演示。' }}所有线索须人工复核。</span>
        <HealthLight />
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshLeft, SwitchButton } from '@element-plus/icons-vue'
import { API_MODE, DATA_SOURCE, api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ROLE_LABEL } from '@/constants/enums'
import HealthLight from './HealthLight.vue'

const navOpen = ref(false)
const navExpanded = ref(true)
const route = useRoute()
watch(() => route.fullPath, () => { navOpen.value = false })
const router = useRouter()
const auth = useAuthStore()

const MENU = [
  { title: '概览', items: [{ path: '/', page: 'overview', title: '研判工作台', code: 'A1', icon: 'Odometer' }] },
  {
    title: '风险研判',
    items: [
      { path: '/risk', page: 'risk', title: '区域时段风险', code: 'B1', icon: 'DataAnalysis' },
      { path: '/risk-map', page: 'risk', title: '风险地图', code: 'B3', icon: 'MapLocation' },
      { path: '/people', page: 'people', title: '人员风险', code: 'B4', icon: 'User' },
    ],
  },
  { title: '线索管理', items: [{ path: '/clues', page: 'clues', title: '线索列表', code: 'C1', icon: 'Tickets' },{path:'/evidence',page:'evidence',title:'证据链浏览',code:'C3',icon:'Connection'}] },
  {
    title: '特征库',
    items: [
      { path: '/features', page: 'features', title: '特征清单', code: 'D1', icon: 'Collection' },
      { path: '/ops', page: 'ops', title: '版本与批次', code: 'D3', icon: 'Operation' },
      { path: '/data', page: 'data', title: '数据管理', code: 'D4', icon: 'Coin' },
    ],
  },
  {
    title: '评估与安全',
    items: [
      { path: '/eval', page: 'eval', title: '评估报告', code: 'E1', icon: 'TrendCharts' },
      { path: '/audit', page: 'audit', title: '审计日志', code: 'E2', icon: 'Document' },
      { path: '/admin', page: 'admin', title: '系统管理', code: 'E3', icon: 'Setting' },
      { path: '/cases', page: 'cases', title: '历史案件', code: 'E4', icon: 'Files' },
    ],
  },
]

// 按角色隐藏菜单（不是禁用）
const visibleMenu = computed(() =>
  MENU.map((g) => ({ ...g, items: g.items.filter((i) => auth.canPage(i.page)) })).filter((g) => g.items.length),
)

const parentRoute = computed(() => (route.meta.parent ? router.getRoutes().find((r) => r.name === route.meta.parent) : null))
const activeMenu = computed(() => (parentRoute.value ? parentRoute.value.path : route.path))

async function onCommand(cmd) {
  if (cmd === 'logout') {
    await api.logout().catch(() => {})
    auth.logout()
    router.replace({ name: 'login' })
  } else if (cmd === 'reset') {
    const confirmed = await ElMessageBox.confirm('将清除本浏览器中对模拟数据的所有改动（核查结论、批次、参数等），恢复为示例库初始状态。', '重置演示数据', { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' })
      .then(() => true, () => false)
    if (!confirmed) return
    ElMessage.success('已恢复为示例库初始数据')
    router.go(0)
  }
}
</script>

<style scoped>
.layout { height:100%; }
.aside { background:var(--rail-bg); color:#fff; display:flex; flex-direction:column; overflow-y:auto; flex-shrink:0; }
.brand { padding:20px 12px; }.brand-link { color:#fff; display:flex; align-items:center; gap:12px; justify-content:center; text-decoration:none; }.brand-link span { font-size:14px; font-weight:600; }.brand-link small { display:block; margin-top:6px; font-size:12px; color:#9da9ae; font-weight:400; }
.rail-menu { flex:1; padding:0 12px; }.rail-group { padding:10px 0; }.rail-group + .rail-group { border-top:1px solid #394148; }.group-title { font-size:12px; color:#9da9ae; padding:0 12px 8px; }
.rail-link { display:flex; align-items:center; justify-content:center; min-height:40px; padding:8px; margin:4px 0; gap:10px; color:#b7c0c4; border-radius:8px; text-decoration:none; }.rail-link:hover { background:var(--rail-raised); color:#fff; }.rail-link.active { background:#354048; color:#fff; box-shadow:inset 0 1px 0 #ffffff0d; }.rail-link.active .el-icon { color:#adc0ee; }.rail-label,.code { display:none; }.expanded .rail-link { justify-content:flex-start; }.expanded .rail-label,.expanded .code { display:inline; }.code { margin-left:auto; font-size:11px; font-family:Consolas,monospace; color:#9da9ae; }
.rail-expand { color:#b7c0c4; min-height:48px; margin:12px; }.rail-expand:hover { color:#fff; background:var(--rail-raised); }
.right { min-width:0; }.header { height:56px; display:flex; align-items:center; justify-content:space-between; background:#fbfcfa; border-bottom:1px solid var(--card-border); gap:12px; }.header-right { display:flex; align-items:center; gap:12px; }.user { display:flex; align-items:center; gap:6px; cursor:pointer; background:transparent; border:0; font:inherit; color:inherit; padding:6px; }.role-tag { margin-left:2px; }
.main { padding:24px; overflow-y:auto; }.main.canvas-main { padding:0; overflow:auto; }.footer { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:8px 24px; font-size:12px; color:var(--text-muted); border-top:1px solid var(--card-border); background:#fff; flex-wrap:wrap; }
.nav-toggle,.nav-backdrop { display:none; }
@media(max-width:900px) {
  .aside { width:220px!important; position:fixed; inset:0 auto 0 0; z-index:2100; transform:translateX(-100%); transition:transform .18s ease-out; }.nav-open .aside { transform:translateX(0); }.rail-link { justify-content:flex-start; }.rail-label,.code { display:inline; }.rail-expand { display:none; }
  .nav-toggle { display:inline-flex; }.nav-backdrop { display:block; position:fixed; inset:0 0 0 220px; background:rgba(15,23,42,.35); border:0; z-index:2099; }.header { padding:0 12px; }.header-right { gap:6px; margin-left:auto; }.role-tag { display:none; }.main { padding:16px; }.footer { padding:10px 16px; }
}
@media(max-width:480px) { .header :deep(.el-breadcrumb) { display:none; }.header-right :deep(.el-tag) { font-size:11px; } }
@media(prefers-reduced-motion:reduce) { .aside { transition:none; } }
</style>
