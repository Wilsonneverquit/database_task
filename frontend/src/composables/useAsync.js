import { ref, shallowRef } from 'vue'

// 统一管理"加载中 / 空数据 / 接口报错"三种状态（《前端交接文档》第十三节验收项）
export function useAsync(fn, { immediate = true } = {}) {
  const data = shallowRef(null)
  const loading = ref(false)
  const error = ref(null)

  async function run(...args) {
    loading.value = true
    error.value = null
    try {
      data.value = await fn(...args)
    } catch (e) {
      error.value = e
    } finally {
      loading.value = false
    }
    return data.value
  }

  if (immediate) run()
  return { data, loading, error, run }
}
