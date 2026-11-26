<template>
  <div class="page"><div class="page-head"><div><h2>数据管理</h2><p class="sub">维护当前数据库中的记录。已引用记录受外键和证据快照保护，导入失败整批回滚。</p></div></div>
    <el-collapse v-if="quality.data.value?.length"><el-collapse-item title="数据来源与清洗记录" name="quality">
      <div v-for="r in quality.data.value" :key="r.report_id" class="small">
        <template v-if="r.report_json.kind==='public_snapshot'">
          <p v-for="s in r.report_json.manifest.sources" :key="s.publisher">{{ s.publisher }} · {{ s.license }} · 采集于 {{ s.retrieved_utc }} · {{ s.tables.join('、') }}</p>
          <p>剑桥场所和奥斯汀订单独立入库。德州财政部门的统计按月汇总，仅供城市背景参考。</p>
          <p v-for="m in r.report_json.receipt_summary" :key="m.obligation_end_date">{{ m.obligation_end_date.slice(0,7) }} · {{ m.reports }} 份申报 · 销售总额 {{ m.sales_usd }} 美元</p>
        </template>
        <p v-else>原种子 {{ r.report_json.rows }} 行，{{ r.report_json.completed_orders_without_completion_time }} 条完成订单缺少完成时间，{{ r.report_json.region_scores_without_calendar_window }} 条区域评分缺少具体日期窗。</p>
      </div></el-collapse-item></el-collapse>
    <AsyncState :data="catalog.data.value" :loading="catalog.loading.value" :error="catalog.error.value" @retry="catalog.run"><template v-if="catalog.data.value"><div class="toolbar"><el-select v-model="resource" aria-label="数据类型" style="width:190px" @change="reload"><el-option v-for="c in catalog.data.value" :key="c.resource" :value="c.resource" :label="c.title" /></el-select><el-input v-model="search" placeholder="按编号或名称搜索" clearable style="width:240px" @change="reload" /><el-button @click="load">刷新</el-button><template v-if="meta?.can_write"><el-button type="primary" @click="edit()">新增记录</el-button><label class="import-button">导入 CSV<input type="file" accept=".csv" :disabled="importing" @change="importFile" /></label></template></div>
      <p class="muted small">{{ meta?.title }} · {{ rows?.total || 0 }} 条 · CSV 表头：<span class="mono">{{ fields.filter(f=>!f.extra.includes('auto_increment')).map(f=>f.name).join(',') }}</span></p>
      <el-card shadow="never"><AsyncState :data="rows" :loading="loading" :error="error" @retry="load"><el-table v-if="rows" :data="rows.list" stripe><el-table-column v-for="f in fields" :key="f.name" :prop="f.name" :label="labels[f.name] || f.name" :min-width="f.name.includes('time')||f.name.includes('_at')?170:130" show-overflow-tooltip /><el-table-column v-if="meta?.can_write" label="操作" width="145" fixed="right"><template #default="{row}"><el-button link type="primary" @click="edit(row)">更正</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column></el-table><el-pagination v-if="rows" v-model:current-page="currentPage" :total="rows.total" :page-size="20" layout="total,prev,pager,next" @current-change="load" /></AsyncState></el-card>
    </template></AsyncState>
    <el-dialog v-model="open" :title="editingId==null?'新增记录':'更正记录'" width="min(680px,95vw)"><el-form label-position="top" @submit.prevent="save"><div class="data-form"><el-form-item v-for="f in fields.filter(f=>!f.extra.includes('auto_increment'))" :key="f.name" :label="`${labels[f.name] || f.name}${f.nullable==='NO' && f.default_value==null && f.name!==meta.primary_key?' *':''}`"><el-input v-model="form[f.name]" :disabled="editingId!=null&&f.name===meta.primary_key" :type="f.type==='json'?'textarea':'text'" :rows="f.type==='json'?5:undefined" :placeholder="f.name===meta.primary_key?'留空自动生成编号':f.type==='datetime'?'YYYY-MM-DD HH:mm:ss':f.default_value!=null?`默认 ${f.default_value}`:''" /></el-form-item></div><template v-if="resource==='users'"><el-form-item label="口令（新增必填，更正留空保持）"><el-input v-model="password" type="password" show-password /></el-form-item><el-form-item label="角色"><el-checkbox-group v-model="userRoles"><el-checkbox v-for="(name,key) in roleNames" :key="key" :value="key">{{ name }}</el-checkbox></el-checkbox-group></el-form-item></template><p class="muted small">* 为必填。JSON 规则需填写 weights 与 version_id；只允许调整草稿规则。</p><el-button native-type="submit" type="primary" :loading="saving">保存</el-button></el-form></el-dialog>
  </div>
</template>
<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {api} from '@/api'
import {useRoute} from 'vue-router'
import {useAsync} from '@/composables/useAsync'
import AsyncState from '@/components/AsyncState.vue'
const route=useRoute()
const quality=useAsync(()=>api.dataQuality())
const catalog=useAsync(()=>api.dataCatalog()),resource=ref(''),search=ref(''),currentPage=ref(1)
const meta=computed(()=>catalog.data.value?.find(c=>c.resource===resource.value)),fields=computed(()=>meta.value?.fields||[])
const {data:rows,loading,error,run:load}=useAsync(()=>resource.value?api.dataRows(resource.value,{q:search.value,page:currentPage.value,size:20}):Promise.resolve(null),{immediate:false})
watch(()=>catalog.data.value,c=>{if(c?.length&&!resource.value){resource.value=c.find(x=>x.resource===route.query.resource)?.resource||c[0].resource;load()}})
const open=ref(false),form=reactive({}),editingId=ref(null),saving=ref(false),importing=ref(false),password=ref(''),userRoles=ref([])
const roleNames={R_ANALYST:'研判员',R_DATA:'数据管理员',R_FEATURE:'特征管理员',R_ADMIN:'系统管理员',R_TEACHER:'教师'}
const labels={source_type:'源：consume/order/track',window_start:'覆盖起始时间',window_end:'覆盖结束时间',available_at:'覆盖信息入库时间',coverage:'覆盖率：0–1',area_id:'区域编号',area_name:'区域名称',area_type:'区域类型',person_id:'人员编号',person_name:'人员显示名',place_id:'场所编号',place_name:'场所名称',consume_id:'消费编号',record_no:'业务流水号',consume_time:'消费时间',amount:'金额（元）',has_alcohol:'含酒水：1是/0否',recorded_at:'入库时间',is_active:'有效：1是/0否',order_time:'下单时间',completed_at:'完成时间',order_status:'状态：1完成/2取消/3进行中',order_type:'类型：1网约车/2代驾',vehicle_id:'车辆编号',owner_person_id:'车主编号',plate_mask:'车牌展示值',pass_time:'过车时间',direction:'方向：1驶入/2驶出',gate_id:'卡口编号',version_id:'版本编号',version_no:'版本号',rule_id:'规则编号',rule_name:'规则名称',config_json:'因子配置 JSON',user_id:'用户编号',username:'用户名',real_name:'显示名称',status:'状态',remark:'说明'}
function reload(){currentPage.value=1;load()}
function edit(row){Object.keys(form).forEach(k=>delete form[k]);editingId.value=row?.[meta.value.primary_key]??null;for(const f of fields.value){form[f.name]=row?.[f.name]??'';if(typeof form[f.name]==='object'&&form[f.name]!=null)form[f.name]=JSON.stringify(form[f.name])}password.value='';userRoles.value=row?.roles||[];open.value=true}
async function save(){saving.value=true;try{const value={};for(const f of fields.value){const v=form[f.name];if(v===''||v==null){if(editingId.value!=null&&f.nullable==='YES')value[f.name]=null;continue}value[f.name]=['int','bigint','smallint','tinyint','decimal','double'].includes(f.type)?Number(v):v}if(resource.value==='users'){if(password.value)value.password=password.value;value.roles=userRoles.value}if(editingId.value==null)await api.createRow(resource.value,value);else await api.updateRow(resource.value,editingId.value,value);ElMessage.success('已保存到 MySQL');open.value=false;load()}catch(e){ElMessage.error(e.message)}finally{saving.value=false}}
async function remove(row){if(!await ElMessageBox.confirm('删除未引用记录；若已有业务引用，系统将拒绝删除。','删除记录',{type:'warning'}).then(()=>true,()=>false))return;try{await api.deleteRow(resource.value,row[meta.value.primary_key]);ElMessage.success('已删除');load()}catch(e){ElMessage.error(e.message)}}
async function importFile(e){const file=e.target.files?.[0];if(!file)return;importing.value=true;try{const r=await api.importRows(resource.value,file);ElMessage.success(`已导入 ${r.imported} 行`);reload()}catch(e){ElMessage.error(e.message)}finally{importing.value=false;e.target.value=''}}
</script>
<style scoped>
.small{font-size:12px;line-height:1.8;overflow-wrap:anywhere;margin:0}.data-form{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}.el-pagination{margin-top:20px}.import-button{display:inline-flex;align-items:center;padding:8px 16px;border:1px solid var(--card-border);border-radius:8px;cursor:pointer;background:var(--surface)}.import-button input{width:1px;height:1px;opacity:0;position:absolute}@media(max-width:600px){.data-form{grid-template-columns:1fr}}
</style>
