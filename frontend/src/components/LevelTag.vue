<template>
  <span class="level" :class="`lv-${lv}`">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { enumLabel } from '@/constants/enums'

// 接受数字等级（1/2/3）或视图里的中文名（低/中/高）
const props = defineProps({ level: { type: [Number, String], default: null },status:{type:String,default:''} })
const NAME_TO_LV = { 低: 1, 中: 2, 高: 3 }
const lv = computed(() => (typeof props.level === 'string' ? NAME_TO_LV[props.level] : props.level))
const label = computed(() => lv.value==null ? ({no_activity:'暂无消费活动',source_gap:'采集覆盖不足',low_sample:'样本不足'}[props.status] || '未评分') : `${enumLabel('risk_level', lv.value)}风险`)
</script>

<style scoped>
.level { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; line-height: 16px; font-weight: 500; white-space: nowrap; }
.level::before { content:""; display:inline-block; width:4px; height:4px; border-radius:50%; margin-right:6px; background:currentColor; vertical-align:2px; }
.lv-1 { color: var(--level-low); background: var(--level-low-bg); }
.lv-2 { color: var(--level-mid); background: var(--level-mid-bg); }
.lv-3 { color: var(--level-high); background: var(--level-high-bg); }
</style>
