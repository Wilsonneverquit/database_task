<template>
  <el-tag :type="TYPES[type]?.[value] ?? 'info'" size="small" effect="light">{{ enumLabel(type, value) }}</el-tag>
</template>

<script setup>
import { enumLabel } from '@/constants/enums'

defineProps({
  type: { type: String, required: true },
  value: { type: [Number, String], default: null },
})

const TYPES = {
  clue_status: { 0: 'warning', 1: 'primary', 2: 'danger', 3: 'info' },
  run_status: { 0: 'info', 1: 'primary', 2: 'success', 3: 'danger' },
  publish_status: { 0: 'info', 1: 'success', 2: 'warning' },
  check_result: { 1: 'danger', 2: 'success', 3: 'info' },
  enable_status: { 1: 'success', 0: 'info' },
  user_status: { 1: 'success', 2: 'info', 3: 'danger' },
}
</script>
