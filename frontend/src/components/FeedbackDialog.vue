<template>
  <el-dialog :model-value="modelValue" :title="title" width="560px" @update:model-value="$emit('update:modelValue', $event)" @open="reset">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="核查结论" prop="check_result">
        <el-radio-group v-model="form.check_result">
          <el-radio-button v-for="o in enumOptions('check_result')" :key="o.value" :value="o.value" :disabled="lockResult && o.value !== preset">{{ o.label }}</el-radio-button>
        </el-radio-group>
        <div class="tip muted">{{ resultTip }}</div>
      </el-form-item>
      <el-form-item label="核查方式" prop="check_method">
        <el-select v-model="form.check_method" placeholder="请选择" style="width: 200px">
          <el-option v-for="o in enumOptions('check_method')" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="核查说明" prop="check_remark">
        <el-input v-model="form.check_remark" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="如：电话回访，聚餐后由家人接送" />
      </el-form-item>
      <el-form-item v-if="form.check_result === 2" label="被否定的特征">
        <div class="wrong">
          <el-checkbox-group v-model="form.wrong_feature_ids">
            <el-checkbox v-for="f in hitFeatures" :key="f.feature_id" :value="f.feature_id">
              <span class="mono">{{ f.feature_id }}</span> {{ f.feature_name }}
            </el-checkbox>
          </el-checkbox-group>
          <div class="tip muted">勾选核查中被证伪的命中特征。这些记录写入反馈特征明细表，作为下一轮权重调整的输入（闭环回写）。</div>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { enumOptions } from '@/constants/enums'

const props = defineProps({
  modelValue: Boolean,
  clueId: { type: String, required: true },
  features: { type: Array, default: () => [] },
  preset: { type: Number, default: 1 },
  lockResult: Boolean,
  title: { type: String, default: '提交核查结论' },
})
const emit = defineEmits(['update:modelValue', 'submitted'])

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({ check_result: 1, check_method: null, check_remark: '', wrong_feature_ids: [] })
const rules = {
  check_result: [{ required: true, message: '请选择核查结论' }],
  check_method: [{ required: true, message: '请选择核查方式', trigger: 'change' }],
  check_remark: [{ required: true, message: '请填写核查说明', trigger: 'blur' }],
}

const hitFeatures = computed(() => props.features.filter((f) => f.is_hit === 1))
const resultTip = computed(() => ({
  1: '提交后线索自动变为"已确认"（由触发器推进状态并写关闭时间）',
  2: '提交后线索自动变为"已排除"；请勾选被否定的特征',
  3: '无法核实不改变线索状态，线索保持当前状态等待后续处理',
})[form.check_result])

function reset() {
  Object.assign(form, { check_result: props.preset, check_method: null, check_remark: '', wrong_feature_ids: [] })
  formRef.value?.clearValidate()
}

async function submit() {
  if (!(await formRef.value.validate().catch(() => false))) return
  if (form.check_result === 2 && !form.wrong_feature_ids.length) {
    const confirmed = await ElMessageBox.confirm('没有勾选被否定的特征，这条误报将无法回写到特征权重。仍要提交吗？', '提示', { type: 'warning', confirmButtonText: '仍然提交', cancelButtonText: '返回勾选' })
      .then(() => true, () => false)
    if (!confirmed) return
  }
  submitting.value = true
  try {
    const res = await api.submitFeedback(props.clueId, {
      check_result: form.check_result,
      check_method: form.check_method,
      check_remark: form.check_remark,
      wrong_feature_ids: form.check_result === 2 ? form.wrong_feature_ids : [],
    })
    ElMessage.success('核查结论已提交')
    emit('update:modelValue', false)
    emit('submitted', res)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.tip { font-size: 12px; line-height: 1.6; margin-top: 4px; width: 100%; }
.wrong { display: flex; flex-direction: column; }
.wrong :deep(.el-checkbox) { display: flex; margin-right: 0; }
</style>
