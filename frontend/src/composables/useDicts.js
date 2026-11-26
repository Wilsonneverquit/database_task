import { ref } from 'vue'
import { api } from '@/api'

// 区域、规则等下拉字典，整个会话只取一次
const dicts = ref(null)
let pending = null

export async function refreshDicts() {
  const value=await api.dicts()
  dicts.value=value
  return value
}

export function useDicts() {
  if (!dicts.value && !pending) {
    pending = api.dicts().then((d) => { dicts.value = d }).catch(() => {}).finally(() => { pending = null })
  }
  return dicts
}
