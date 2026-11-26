<template><section><div class="card-title">风险随时间变化<span class="hint">同一版本 · 每小时最新成功批次</span></div><AsyncState :data="data" :loading="loading" :error="error" @retry="load"><EChart v-if="data?.length" :option="option" height="250px" /></AsyncState><p class="muted small">横轴为北京时间，纵轴为 0–100 风险指数；缺失数据保留断点。</p></section></template>
<script setup>
import {computed,watch} from 'vue'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import EChart from './EChart.vue'
import AsyncState from './AsyncState.vue'
const props=defineProps({areaId:String,personId:String,versionId:String})
const {data,loading,error,run:load}=useAsync(()=>api.trends({area_id:props.areaId,person_id:props.personId,version_id:props.versionId}),{immediate:false})
watch(()=>[props.areaId,props.personId,props.versionId],()=>load(),{immediate:true})
const option=computed(()=>({tooltip:{trigger:'axis'},grid:{left:45,right:25,top:30,bottom:60},dataZoom:[{type:'slider',height:18,bottom:4}],xAxis:{type:'category',name:'时间',data:(data.value||[]).map(r=>r.window_start.slice(5,16))},yAxis:{type:'value',name:'风险指数',min:0,max:100},series:[{name:'风险指数',type:'line',showSymbol:false,connectNulls:false,lineStyle:{color:'#78aaff',width:2},data:(data.value||[]).map(r=>r.total_score),markLine:{symbol:'none',silent:true,data:[{yAxis:40},{yAxis:70}],lineStyle:{color:'#e5bb71',type:'dashed'}}}]}))
</script>
<style scoped>.small{font-size:12px;line-height:1.8}</style>
