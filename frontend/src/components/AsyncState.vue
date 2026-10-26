<template>
  <div v-if="loading && !hasData" class="state" v-loading="true" element-loading-text="加载中…" />
  <el-result v-else-if="error" icon="error" title="接口报错" :sub-title="error.message">
    <template #extra>
      <el-button type="primary" @click="$emit('retry')">重试</el-button>
    </template>
  </el-result>
  <el-empty v-else-if="isEmpty" :description="emptyText" />
  <div v-else v-loading="loading">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

// 统一的"加载中 / 接口报错 / 空数据"展示
const props = defineProps({
  loading: Boolean,
  error: { type: Object, default: null },
  data: { type: [Object, Array], default: null },
  empty: { type: Boolean, default: undefined },
  emptyText: { type: String, default: '暂无数据' },
})
defineEmits(['retry'])

const hasData = computed(() => props.data !== null && props.data !== undefined)
const isEmpty = computed(() => {
  if (props.empty !== undefined) return props.empty
  if (!hasData.value) return true
  if (Array.isArray(props.data)) return props.data.length === 0
  if (Array.isArray(props.data.list)) return props.data.list.length === 0
  return false
})
</script>

<style scoped>
.state { min-height: 160px; }
</style>
