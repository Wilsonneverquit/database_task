import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as Icons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import './styles/main.css'

import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })
Object.entries(Icons).forEach(([name, comp]) => app.component(name, comp))

// 接口返回 401 时统一退出并跳登录页（《前端交接文档》第十节）
setUnauthorizedHandler(() => {
  useAuthStore(pinia).logout()
  const current = router.currentRoute.value
  if (current.name !== 'login') router.replace({ name: 'login', query: { redirect: current.fullPath } })
})

app.mount('#app')
