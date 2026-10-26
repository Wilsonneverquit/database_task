<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <div class="brand-title">多风险特征预警系统</div>
        <div class="brand-sub">以酒驾为例 · 第 6 组</div>
      </div>
      <el-menu :default-active="activeMenu" router class="menu">
        <template v-for="group in visibleMenu" :key="group.title">
          <el-menu-item-group :title="group.title">
            <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
              <span class="code">{{ item.code }}</span>
            </el-menu-item>
          </el-menu-item-group>
        </template>
      </el-menu>
    </el-aside>

    <el-container class="right">
      <el-header class="header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item v-if="parentRoute" :to="{ name: parentRoute.name }">{{ parentRoute.meta.title }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta.title }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="header-right">
          <el-tooltip v-if="API_MODE === 'mock'" content="后端未就绪，当前使用前端内置的模拟数据（取自示例库）" placement="bottom">
            <el-tag type="warning" effect="plain">模拟数据模式</el-tag>
          </el-tooltip>
          <el-tag v-else type="success" effect="plain">已连接后端</el-tag>
          <el-dropdown trigger="click" @command="onCommand">
            <span class="user">
              <el-icon><User /></el-icon>
              {{ auth.user?.real_name }}
              <el-tag v-for="r in auth.roles" :key="r" size="small" class="role-tag">{{ ROLE_LABEL[r] }}</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="API_MODE === 'mock'" command="reset" :icon="RefreshLeft">重置演示数据</el-dropdown-item>
                <el-dropdown-item command="logout" :icon="SwitchButton" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <slot />
      </el-main>

      <el-footer class="footer" height="auto">
        <span>模拟数据，仅用于教学演示，不作执法依据。系统只输出风险等级、待核查线索与命中理由，不作定性结论，所有线索须人工复核。</span>
        <HealthLight />
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshLeft, SwitchButton } from '@element-plus/icons-vue'
import { API_MODE } from '@/api'
import { resetMockDb } from '@/api/mock/server'
import { useAuthStore } from '@/stores/auth'
import { ROLE_LABEL } from '@/constants/enums'
import HealthLight from './HealthLight.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const MENU = [
  { title: '概览', items: [{ path: '/', page: 'overview', title: '首页概览', code: 'A1', icon: 'Odometer' }] },
  { title: '风险研判', items: [{ path: '/risk', page: 'risk', title: '区域时段风险', code: 'B1', icon: 'DataAnalysis' }] },
  { title: '线索管理', items: [{ path: '/clues', page: 'clues', title: '线索列表', code: 'C1', icon: 'Tickets' }] },
  {
    title: '特征库',
    items: [
      { path: '/features', page: 'features', title: '特征清单', code: 'D1', icon: 'Collection' },
      { path: '/ops', page: 'ops', title: '版本与批次', code: 'D3', icon: 'Operation' },
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
    auth.logout()
    router.replace({ name: 'login' })
  } else if (cmd === 'reset') {
    const confirmed = await ElMessageBox.confirm('将清除本浏览器中对模拟数据的所有改动（核查结论、批次、参数等），恢复为示例库初始状态。', '重置演示数据', { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' })
      .then(() => true, () => false)
    if (!confirmed) return
    resetMockDb()
    ElMessage.success('已恢复为示例库初始数据')
    router.go(0)
  }
}
</script>

<style scoped>
.layout { height: 100%; }
.aside { background: #001529; color: #fff; display: flex; flex-direction: column; overflow-y: auto; }
.brand { padding: 18px 20px 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }
.brand-title { font-size: 16px; font-weight: 600; }
.brand-sub { font-size: 12px; color: rgba(255, 255, 255, 0.55); margin-top: 4px; }
.menu {
  border-right: none;
  --el-menu-bg-color: #001529;
  --el-menu-text-color: rgba(255, 255, 255, 0.75);
  --el-menu-hover-bg-color: #0c2a47;
  --el-menu-active-color: #fff;
  --el-menu-item-height: 44px;
}
.menu :deep(.el-menu-item.is-active) { background: var(--el-color-primary); }
.menu :deep(.el-menu-item-group__title) { color: rgba(255, 255, 255, 0.4); padding-left: 20px !important; }
.code { margin-left: auto; font-size: 11px; opacity: 0.5; font-family: Consolas, monospace; }
.right { min-width: 0; }
.header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid var(--card-border); gap: 12px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user { display: flex; align-items: center; gap: 6px; cursor: pointer; outline: none; }
.role-tag { margin-left: 2px; }
.main { padding: 20px; overflow-y: auto; }
.footer { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 10px 20px; font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--card-border); background: #fff; flex-wrap: wrap; }
</style>
