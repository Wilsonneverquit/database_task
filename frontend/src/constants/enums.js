// 枚举中文映射。来源：《前端交接文档》5.1 枚举表；表里没有的（标 *）取自建库脚本字段注释。
// 页面上一律通过 enumLabel() 显示，不出现裸数字。

export const ENUMS = {
  risk_level: { 1: '低', 2: '中', 3: '高' },
  clue_status: { 0: '待核查', 1: '核查中', 2: '已确认', 3: '已排除' },
  object_type: { 1: '区域时段', 2: '个人' },
  day_type: { 1: '工作日', 2: '周末' },
  feature_direction: { 1: '正向加分', 2: '反向扣分' },
  track_direction: { 1: '驶入区域', 2: '驶出区域' },
  order_type: { 1: '网约车', 2: '代驾' },
  order_status: { 1: '已完成', 2: '取消', 3: '进行中' },
  check_result: { 1: '属实', 2: '不属实', 3: '无法核实' },
  sample_type: { 1: '正样本', 2: '干扰样本', 3: '对照样本' },
  run_status: { 0: '待执行', 1: '执行中', 2: '成功', 3: '失败' },
  object_scope: { 1: '仅区域时段', 2: '仅个人', 3: '两者' },
  publish_status: { 0: '草稿', 1: '已发布', 2: '已归档' },
  // * 以下取自建库脚本注释
  check_method: { 1: '电话', 2: '现场', 3: '数据复核' },
  feature_cat: { 1: '时空', 2: '消费', 3: '出行', 4: '行为', 5: '反例' },
  value_type: { 1: '布尔', 2: '数值阈值', 3: '枚举', 4: '频次' },
  area_type: { 1: '城市道路', 2: '商圈', 3: '乡镇', 4: '高速出入口' },
  op_type: { 1: '登录', 2: '查询', 3: '新增', 4: '修改', 5: '删除', 6: '导出', 7: '研判', 8: '授权' },
  param_type: { 1: '整型', 2: '小数', 3: '字符串/时间', 4: '布尔' },
  case_type: { 1: '饮酒驾驶', 2: '醉酒驾驶', 3: '酒驾肇事' },
  dispose_status: { 0: '待处置', 1: '已处罚', 2: '已移送' },
  user_status: { 1: '正常', 2: '停用', 3: '锁定' },
  enable_status: { 1: '启用', 0: '停用' },
  judge_object: { 1: '区域时段', 2: '个人' },
  is_valid: { 1: '参与研判', 0: '样本不足' },
}

export function enumLabel(type, value) {
  if (value === null || value === undefined || value === '') return '—'
  const label = ENUMS[type]?.[value]
  return label ?? `未知(${value})`
}

export function enumOptions(type) {
  return Object.entries(ENUMS[type]).map(([value, label]) => ({ value: Number(value), label }))
}

// 训练源 / 研判源 表名的中文说明，用于 D1 双口径展示
export const SRC_TABLE_LABEL = {
  case_info: '案件表',
  consume_record: '消费流水',
  taxi_order: '出行订单',
  vehicle_track: '卡口过车',
  person_info: '人员表',
  place_info: '场所表',
  v_case_history: '历史案件视图',
}

export const ROLE_LABEL = {
  R_ANALYST: '研判员',
  R_DATA: '数据管理员',
  R_FEATURE: '特征管理员',
  R_ADMIN: '系统管理员',
  R_TEACHER: '教师/评审',
}
