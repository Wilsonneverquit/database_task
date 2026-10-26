import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 12 个页面 / 5 个模块，路由与《前端交接文档》第四节一致；C2 以抽屉形式挂在 C1 上
const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, bare: true } },
  { path: '/', name: 'overview', component: () => import('@/views/OverviewView.vue'), meta: { page: 'overview', title: '首页概览', code: 'A1' } },
  { path: '/risk', name: 'risk', component: () => import('@/views/RiskListView.vue'), meta: { page: 'risk', title: '区域时段风险', code: 'B1' } },
  { path: '/risk/:scoreId', name: 'risk-detail', component: () => import('@/views/RiskDetailView.vue'), meta: { page: 'risk', title: '风险详情', code: 'B2', parent: 'risk' } },
  { path: '/clues', name: 'clues', component: () => import('@/views/ClueListView.vue'), meta: { page: 'clues', title: '线索列表', code: 'C1' } },
  { path: '/clues/:clueId', name: 'clue-detail', component: () => import('@/views/ClueListView.vue'), meta: { page: 'clues', title: '线索详情', code: 'C2', parent: 'clues' } },
  { path: '/features', name: 'features', component: () => import('@/views/FeatureListView.vue'), meta: { page: 'features', title: '特征清单', code: 'D1' } },
  { path: '/features/:featureId', name: 'feature-detail', component: () => import('@/views/FeatureDetailView.vue'), meta: { page: 'features', title: '特征详情', code: 'D2', parent: 'features' } },
  { path: '/ops', name: 'ops', component: () => import('@/views/OpsView.vue'), meta: { page: 'ops', title: '版本与批次', code: 'D3' } },
  { path: '/eval', name: 'eval', component: () => import('@/views/EvalView.vue'), meta: { page: 'eval', title: '评估报告', code: 'E1' } },
  { path: '/audit', name: 'audit', component: () => import('@/views/AuditView.vue'), meta: { page: 'audit', title: '审计日志', code: 'E2' } },
  { path: '/admin', name: 'admin', component: () => import('@/views/AdminView.vue'), meta: { page: 'admin', title: '系统管理', code: 'E3' } },
  { path: '/cases', name: 'cases', component: () => import('@/views/CasesView.vue'), meta: { page: 'cases', title: '历史案件', code: 'E4' } },
  { path: '/403', name: 'forbidden', component: () => import('@/views/ForbiddenView.vue'), meta: { title: '无权访问' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/ForbiddenView.vue'), meta: { title: '页面不存在', notFound: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) return auth.loggedIn && to.name === 'login' ? { name: 'overview' } : true
  if (!auth.loggedIn) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.page && !auth.canPage(to.meta.page)) return { name: 'forbidden' }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title ? to.meta.title + ' · ' : ''}多风险特征预警系统`
})

export default router
