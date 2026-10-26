<template>
  <el-popover placement="top-end" :width="300" trigger="hover">
    <template #reference>
      <span class="health">
        <span class="dot" :class="state" />
        数据健康{{ state === 'ok' ? '正常' : state === 'bad' ? '异常' : state === 'error' ? '未知' : '检查中' }}
      </span>
    </template>
    <div v-if="error" class="muted">{{ error.message }}</div>
    <div v-else-if="data">
      <div class="row"><span>表 / 行</span><span class="num">{{ data.tables }} 张 / {{ data.rows }} 行</span></div>
      <div v-for="c in CHECKS" :key="c.key" class="row">
        <span>{{ c.label }}</span>
        <span class="num" :class="{ bad: data[c.key] !== 0 }">{{ data[c.key] }}</span>
      </div>
      <div class="muted tip">四项都应为 0，非 0 说明数据有问题（接口 24）</div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed } from 'vue'
import { api } from '@/api'
import { useAsync } from '@/composables/useAsync'

const CHECKS = [
  { key: 'orphan_person', label: '孤儿人员' },
  { key: 'orphan_area', label: '孤儿区域' },
  { key: 'case_after_cutoff', label: '观察段案件混入案例库' },
  { key: 'feature_bad_match_src', label: '研判口径指向案件原表' },
]

const { data, loading, error } = useAsync(() => api.health())

const state = computed(() => {
  if (loading.value) return 'loading'
  if (error.value) return 'error'
  return CHECKS.every((c) => data.value?.[c.key] === 0) ? 'ok' : 'bad'
})
</script>

<style scoped>
.health { display: inline-flex; align-items: center; gap: 6px; cursor: default; white-space: nowrap; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: #c0c4cc; }
.dot.ok { background: #67c23a; box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.2); }
.dot.bad { background: #f56c6c; box-shadow: 0 0 0 3px rgba(245, 108, 108, 0.2); }
.row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; }
.bad { color: #f56c6c; font-weight: 600; }
.tip { font-size: 12px; margin-top: 6px; }
</style>
