<template>
  <section class="overview-city" aria-label="区域态势预览">
    <header><div><h3>城市区域态势</h3><p>{{selectedArea?.area_name || '选择区域查看当前时段风险'}} · {{currentDate || '读取观察时段…'}}</p></div><router-link to="/risk-map">打开完整地图 <el-icon><ArrowRight /></el-icon></router-link></header>
    <AsyncState :data="data" :loading="loading" :error="error" @retry="run">
      <RiskStreetMap v-if="data?.areas.length" preview class="city-preview" :areas="data.areas" :risk="risk" :selected="selected" :show-links="false" @select="selected=$event" />
      <div v-if="selectedArea" class="preview-detail"><span>{{selectedArea.area_name}}</span><LevelTag :level="risk[selected]?.risk_level" :status="risk[selected]?.risk_status" /><span v-if="risk[selected]?.total_score!=null" class="num">{{fixed(risk[selected].total_score)}} 分</span><span v-else class="muted">该时段未评分</span><router-link :to="{name:'risk-map',query:{area:selected}}">在地图中查看</router-link></div>
      <nav class="preview-regions" aria-label="预览区域选择"><button v-for="a in data?.areas||[]" :key="a.area_id" :aria-pressed="selected===a.area_id" @click="selected=a.area_id">{{a.area_name}}</button></nav>
    </AsyncState>
  </section>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {fixed} from '@/utils/format'
import AsyncState from './AsyncState.vue'
import RiskStreetMap from './RiskStreetMap.vue'
import LevelTag from './LevelTag.vue'
const {data,loading,error,run}=useAsync(()=>api.riskMap({aggregation:'hour'}))
const selected=ref('')
const currentDate=computed(()=>data.value?.dates.at(-1)||'')
const risk=computed(()=>Object.fromEntries((data.value?.risk.find(r=>r.date===currentDate.value)?.areas||[]).map(r=>[r.area_id,r])))
const selectedArea=computed(()=>data.value?.areas.find(a=>a.area_id===selected.value))
watch(data,d=>{if(!d?.areas.some(a=>a.area_id===selected.value))selected.value=d?.areas[0]?.area_id||''})
defineExpose({refresh:run})
</script>
<style scoped>
.overview-city{min-width:0;background:var(--surface);border:1px solid var(--card-border);border-radius:14px;overflow:hidden}.overview-city>header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:20px 22px}.overview-city h3{font-size:18px;font-weight:500;margin:0}.overview-city header p{font-size:12px;color:var(--text-muted);margin:8px 0 0}.overview-city header a{font-size:12px;white-space:nowrap;display:flex;gap:8px;align-items:center}.city-preview{height:360px;border-radius:0}.preview-detail{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:16px 20px;border-bottom:1px solid var(--border-soft);font-size:13px}.preview-detail>a{margin-left:auto;font-size:12px}.preview-regions{display:flex;gap:6px;flex-wrap:wrap;padding:14px 20px}.preview-regions button{border:1px solid transparent;background:transparent;color:var(--text-muted);font:12px var(--font-ui);border-radius:5px;padding:6px 8px;cursor:pointer}.preview-regions button:hover{background:var(--surface-raised);color:var(--text-primary)}.preview-regions button[aria-pressed=true]{border-color:#35577d;background:var(--accent-soft);color:var(--accent-ink)}
@media(max-width:600px){.overview-city>header{padding:16px;flex-wrap:wrap}.city-preview{height:300px}.preview-detail{padding:14px 16px}.preview-regions{padding:12px;max-height:120px;overflow:auto}}
</style>
