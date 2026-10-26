// 前端内置的模拟后端：按《前端交接文档》第五节接口契约返回 { code, message, data }，
// 业务规则照搬建库脚本里的约束、触发器与存储过程，让"闭环"在没有后端时也能完整演示。
// 后端写好后把 .env 里的 VITE_API_MODE 改成 real，这个文件就不再参与。

import { createSeed } from './seed'
import { ACTION_ROLES, PAGE_ROLES, hasAny } from '@/constants/permissions'

const STORAGE_KEY = 'risk_alert_mock_v1'
const DEMO_PASSWORD = '123456'

let db = load()

function load() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved)
  } catch { /* 隐私模式等情况下读不到，退回种子数据 */ }
  return createSeed()
}

function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(db)) } catch { /* 忽略 */ }
}

export function resetMockDb() {
  db = createSeed()
  save()
}

// ---------------------------------------------------------------------------
// 工具
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(status, code, message) {
    super(message)
    this.status = status
    this.code = code
  }
}

const ok = (data) => ({ status: 200, body: { code: 0, message: 'ok', data } })
const bad = (message) => { throw new ApiError(400, 4000, message) }
const notFound = (what) => { throw new ApiError(404, 4040, `${what}不存在`) }

const pad2 = (n) => String(n).padStart(2, '0')
const round = (n, d) => Math.round(n * 10 ** d) / 10 ** d

const fmt = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`

// 演示时钟：示例数据在 2026-11（观察段），若直接用电脑当前时间，新记录会早于示例数据，
// 出现"关闭时间早于生成时间"、新批次排在最后等问题。这里取"当前时间"与"最近一条审计记录之后 1 分钟"中较晚者，
// 保证时间单调递增；每次写操作都会写审计日志，因此不需要额外存状态。
export function nowStr() {
  const latest = db.audit_log.reduce((m, l) => (l.op_time > m ? l.op_time : m), '')
  const real = new Date()
  if (!latest) return fmt(real)
  const next = parseTime(latest)
  next.setMinutes(next.getMinutes() + 1)
  return fmt(real > next ? real : next)
}

const TIME_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/

function parseTime(s) {
  const [date, time] = s.split(' ')
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm, ss] = (time || '00:00:00').split(':').map(Number)
  return new Date(y, m - 1, d, hh, mm, ss)
}

// 时间串同为 'YYYY-MM-DD HH:mm:ss'，字典序即时间序；区间一律半开 [from, to)
const inRange = (t, from, to) => (!from || t >= from) && (!to || t < to)

function paginate(rows, query) {
  const page = Math.max(1, Number(query.page) || 1)
  const size = Math.max(1, Math.min(200, Number(query.size) || 20))
  return { list: rows.slice((page - 1) * size, page * size), total: rows.length, page, size }
}

const empty = (v) => v === undefined || v === null || v === ''

// 生成列：object_id = 区域#日期类型#小时（两位）/ 人员编号
function objectId(s) {
  return s.object_type === 1 ? `${s.area_id}#${s.day_type}#${pad2(s.hour_slot)}` : s.person_id
}

// 生成列：p1 / p0 / lift
function withRates(w) {
  const p1 = round(w.case_hit / w.case_total, 4)
  const p0 = round(w.ctrl_hit / w.ctrl_total, 4)
  return { ...w, p1, p0, lift: p0 > 0 ? round(p1 / p0, 4) : null }
}

const areaName = (id) => db.area_info.find((a) => a.area_id === id)?.area_name ?? null
const userName = (id) => db.sys_user.find((u) => u.user_id === id)?.real_name ?? null
const levelName = (lv) => ({ 1: '低', 2: '中', 3: '高' })[lv]
const statusName = (st) => ({ 0: '待核查', 1: '核查中', 2: '已确认', 3: '已排除' })[st]
const currentVersionId = () => db.feature_version.find((v) => v.publish_status === 1)?.version_id ?? null
const historyCutoff = () => db.param_config.find((p) => p.param_key === 'history_cutoff').param_value
const dayTypeOf = (t) => ([0, 6].includes(parseTime(t).getDay()) ? 2 : 1)

function audit(userId, opType, table, pk, desc, time = nowStr()) {
  const logId = Math.max(0, ...db.audit_log.map((l) => l.log_id)) + 1
  db.audit_log.push({ log_id: logId, user_id: userId, operator_tag: userId || 'system', op_type: opType, table_name: table, record_pk: pk, op_desc: desc, op_time: time })
}

function rolesOf(userId) {
  return db.sys_user_role.filter((r) => r.user_id === userId).map((r) => r.role_id)
}

function requireRole(ctx, allowed) {
  if (!ctx.user) throw new ApiError(401, 4010, '未登录或登录已过期')
  if (!hasAny(ctx.roles, allowed)) throw new ApiError(403, 4030, '当前角色无权执行此操作')
}

// ---------------------------------------------------------------------------
// 视图（与建库脚本中的定义一致）
// ---------------------------------------------------------------------------

function scoreFeatures(scoreId) {
  return db.risk_score_feature
    .filter((x) => x.score_id === scoreId)
    .map((x) => {
      const f = db.feature_def.find((d) => d.feature_id === x.feature_id)
      return { feature_id: x.feature_id, feature_name: f?.feature_name, match_expr: f?.match_expr, direction: f?.direction, is_hit: x.is_hit, weight: x.weight, hit_value: x.hit_value, is_missing: x.is_missing }
    })
    .sort((a, b) => a.feature_id.localeCompare(b.feature_id))
}

function hitFeaturesStr(scoreId) {
  return scoreFeatures(scoreId)
    .filter((x) => x.is_hit === 1)
    .map((x) => `${x.feature_id}:${x.weight > 0 ? '+' : ''}${x.weight.toFixed(4)}`)
    .join(';')
}

// v_region_risk（多带 score_id、risk_level，便于跳转 B2 与按等级筛选，见 README 缺口 #7）
function vRegionRisk() {
  return db.risk_score
    .filter((s) => s.object_type === 1)
    .map((s) => ({
      score_id: s.score_id,
      batch_id: s.batch_id,
      area_id: s.area_id,
      area_name: areaName(s.area_id),
      day_type: s.day_type,
      day_type_name: s.day_type === 1 ? '工作日' : '周末',
      hour_slot: s.hour_slot,
      sample_size: s.sample_size,
      hit_cnt: db.risk_score_feature.filter((x) => x.score_id === s.score_id && x.is_hit === 1).length,
      total_score: s.total_score,
      risk_level: s.risk_level,
      risk_level_name: levelName(s.risk_level),
      hit_features: hitFeaturesStr(s.score_id),
      is_clue: s.is_clue,
    }))
}

// v_clue_list（多带 clue_status、score_id、object_type/object_id，见 README 缺口 #7）
function vClueList() {
  return db.risk_clue.map((c) => {
    const s = db.risk_score.find((x) => x.score_id === c.score_id)
    return {
      clue_id: c.clue_id,
      score_id: s.score_id,
      object_type: s.object_type,
      object_id: objectId(s),
      area_id: s.area_id,
      area_name: areaName(s.area_id),
      hour_slot: s.hour_slot,
      risk_level: s.risk_level,
      risk_level_name: levelName(s.risk_level),
      total_score: s.total_score,
      hit_features: hitFeaturesStr(s.score_id),
      clue_status: c.clue_status,
      status_name: statusName(c.clue_status),
      assignee_name: userName(c.assignee_id),
      create_at: c.create_at,
      close_at: c.close_at,
    }
  })
}

// v_case_history：只返回 history_cutoff 之前的案件
function vCaseHistory() {
  const cutoff = historyCutoff()
  return db.case_info.filter((c) => c.occur_time < cutoff)
}

function confusion(batchId) {
  const scores = db.risk_score.filter((s) => empty(batchId) || s.batch_id === batchId)
  let tp = 0, fp = 0, fn = 0, tn = 0
  for (const l of db.eval_label) {
    // 与第八节 SQL 一致：LEFT JOIN risk_score ON object_type + object_id，IFNULL(is_clue, 0)
    const matched = scores.filter((s) => s.object_type === l.object_type && objectId(s) === l.object_id)
    const rows = matched.length ? matched.map((s) => s.is_clue) : [0]
    for (const isClue of rows) {
      if (l.label === 1 && isClue === 1) tp++
      else if (l.label === 0 && isClue === 1) fp++
      else if (l.label === 1) fn++
      else tn++
    }
  }
  const div = (a, b) => (b === 0 ? null : round(a / b, 4))
  const precision = div(tp, tp + fp)
  const recall = div(tp, tp + fn)
  const f1 = precision === null || recall === null || precision + recall === 0 ? null : round((2 * precision * recall) / (precision + recall), 4)
  const total = db.eval_label.length
  return {
    tp, fp, fn, tn, precision, recall, fpr: div(fp, fp + tn), f1,
    sample_total: total,
    noise_ratio: div(db.eval_label.filter((l) => l.sample_type === 2).length, total),
  }
}

// ---------------------------------------------------------------------------
// 研判引擎（接口 16）：前端模拟版，流程照《前端交接文档》第七节
// ---------------------------------------------------------------------------

function runBatch(batch, ctx) {
  const started = performance.now()
  const rule = db.judge_rule.find((r) => r.rule_id === batch.rule_id)
  const feats = db.rule_feature
    .filter((rf) => rf.rule_id === rule.rule_id)
    .sort((a, b) => a.sort_no - b.sort_no)
    .map((rf) => ({
      ...db.feature_def.find((f) => f.feature_id === rf.feature_id),
      w: db.feature_weight.find((w) => w.version_id === batch.version_id && w.feature_id === rf.feature_id),
    }))
    .filter((f) => f.status === 1)

  if (feats.some((f) => !f.w)) {
    return { failed: true, message: `权重版本 ${batch.version_id} 尚未计算权重，无法研判` }
  }

  const { data_start: from, data_end: to } = batch
  const placeArea = (pid) => db.place_info.find((p) => p.place_id === pid)?.area_id
  const objects = []

  if (batch.judge_object === 1) {
    // 区域时段：按 (area_id, day_type, hour_slot) 聚合信息库流水
    const groups = new Map()
    const bucket = (area, t) => {
      if (batch.area_id && area !== batch.area_id) return null
      const key = `${area}#${dayTypeOf(t)}#${pad2(parseTime(t).getHours())}`
      if (!groups.has(key)) groups.set(key, { area_id: area, day_type: dayTypeOf(t), hour_slot: parseTime(t).getHours(), consumes: [], tracks: [] })
      return groups.get(key)
    }
    db.consume_record.filter((c) => inRange(c.consume_time, from, to)).forEach((c) => bucket(placeArea(c.place_id), c.consume_time)?.consumes.push(c))
    db.vehicle_track.filter((v) => v.direction === 2 && inRange(v.pass_time, from, to)).forEach((v) => bucket(v.area_id, v.pass_time)?.tracks.push(v))

    for (const g of groups.values()) {
      const values = {
        F001: () => new Set(g.consumes.filter((c) => c.has_alcohol === 1).map((c) => c.place_id)).size,
        F002: () => (g.consumes.some((c) => c.has_alcohol === 1) ? 1 : 0),
        F004: () => g.tracks.length,
      }
      const hit = { F001: (v) => v >= 2, F002: (v) => v >= 1, F004: (v) => v >= 5 }
      objects.push({
        object_type: 1, area_id: g.area_id, day_type: g.day_type, hour_slot: g.hour_slot, person_id: null,
        sample_size: g.consumes.length + g.tracks.length,
        features: feats.filter((f) => f.object_scope !== 2).map((f) => {
          if (!values[f.feature_id]) return { f, is_hit: 0, hit_value: 0, is_missing: 1 }
          const v = values[f.feature_id]()
          return { f, is_hit: hit[f.feature_id](v) ? 1 : 0, hit_value: v, is_missing: 0 }
        }),
      })
    }
  } else {
    // 个人：窗口内有消费记录的人员
    const history = vCaseHistory()
    const before90 = (() => { const d = parseTime(from); d.setDate(d.getDate() - 90); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} 00:00:00` })()
    const consumes = db.consume_record.filter((c) => inRange(c.consume_time, from, to))
    const persons = [...new Set(consumes.map((c) => c.person_id))].sort()
    for (const pid of persons) {
      const mine = consumes.filter((c) => c.person_id === pid)
      const orders = db.taxi_order.filter((o) => o.person_id === pid && o.order_status === 1 && inRange(o.order_time, from, to))
      const home = db.person_info.find((p) => p.person_id === pid)?.home_area_id
      const cases = history.filter((c) => c.person_id === pid)
      const values = {
        F002: () => (mine.some((c) => c.has_alcohol === 1) ? 1 : 0),
        F003: () => (orders.some((o) => [1, 2].includes(o.order_type)) ? 0 : 1),
        F005: () => (home ? (mine.some((c) => placeArea(c.place_id) !== home) ? 1 : 0) : null),
        F006: () => (orders.some((o) => o.order_type === 2) ? 1 : 0),
        F008: () => cases.filter((c) => c.occur_time >= before90).length,
        F009: () => cases.filter((c) => c.alcohol_value >= 80).length,
      }
      objects.push({
        object_type: 2, area_id: null, day_type: null, hour_slot: null, person_id: pid,
        sample_size: mine.length + orders.length,
        features: feats.filter((f) => f.object_scope !== 1).map((f) => {
          const v = values[f.feature_id]?.()
          if (v === null || v === undefined) return { f, is_hit: 0, hit_value: 0, is_missing: 1 }
          return { f, is_hit: v >= 1 ? 1 : 0, hit_value: v, is_missing: 0 }
        }),
      })
    }
  }

  let clueCnt = 0
  let skipped = 0
  for (const o of objects) {
    const total = round(o.features.reduce((s, x) => s + x.is_hit * x.f.w.weight, 0), 2)
    const level = total < rule.low_threshold ? 1 : total < rule.high_threshold ? 2 : 3
    const hitCnt = o.features.filter((x) => x.is_hit === 1 && x.f.direction === 1).length
    const blocked = rule.counter_block === 1 && o.features.some((x) => x.is_hit === 1 && x.f.direction === 2)
    const isClue = level >= 2 && hitCnt >= rule.min_hit_cnt && o.sample_size >= rule.min_sample && !blocked ? 1 : 0
    const oid = objectId(o)

    // sp_upsert_score：同批次同对象已有线索且已核查（2/3）则跳过，不覆盖
    let score = db.risk_score.find((s) => s.batch_id === batch.batch_id && s.object_type === o.object_type && objectId(s) === oid)
    const checked = score && db.risk_clue.some((c) => c.score_id === score.score_id && [2, 3].includes(c.clue_status))
    if (checked) { skipped++; continue }

    if (!score) {
      score = { score_id: Math.max(0, ...db.risk_score.map((s) => s.score_id)) + 1, batch_id: batch.batch_id, rule_id: rule.rule_id, version_id: batch.version_id, object_type: o.object_type, area_id: o.area_id, day_type: o.day_type, hour_slot: o.hour_slot, person_id: o.person_id }
      db.risk_score.push(score)
    }
    Object.assign(score, { sample_size: o.sample_size, total_score: total, risk_level: level, is_clue: isClue })
    db.risk_score_feature = db.risk_score_feature.filter((x) => x.score_id !== score.score_id)
    o.features.forEach((x) => db.risk_score_feature.push({ score_id: score.score_id, feature_id: x.f.feature_id, is_hit: x.is_hit, weight: x.f.w.weight, hit_value: x.hit_value, is_missing: x.is_missing }))

    if (isClue && !db.risk_clue.some((c) => c.score_id === score.score_id)) {
      const day = batch.batch_id.slice(1, 9)
      const seq = db.risk_clue.filter((c) => c.clue_id.startsWith(`CL${day}`)).length + 1
      db.risk_clue.push({ clue_id: `CL${day}${pad2(seq)}`, batch_id: batch.batch_id, score_id: score.score_id, version_id: batch.version_id, clue_status: 0, assignee_id: ctx.user.user_id, create_at: nowStr(), close_at: null })
      clueCnt++
    }
  }

  return { failed: false, object_cnt: objects.length, clue_cnt: clueCnt, skipped, duration_ms: Math.max(1, Math.round(performance.now() - started)) }
}

// ---------------------------------------------------------------------------
// 路由
// ---------------------------------------------------------------------------

const routes = []
const route = (method, pattern, handler) => {
  const keys = []
  const re = new RegExp('^' + pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return '([^/]+)' }) + '$')
  routes.push({ method, re, keys, handler })
}

// 登录（接口契约中没有，见 README 缺口 #1）
route('POST', '/api/login', (ctx) => {
  const { username, password } = ctx.body || {}
  const u = db.sys_user.find((x) => x.username === username)
  if (!u || password !== DEMO_PASSWORD) throw new ApiError(401, 4011, '用户名或口令错误')
  if (u.status !== 1) throw new ApiError(403, 4031, '该账号已停用')
  audit(u.user_id, 1, 'sys_user', u.user_id, '用户登录成功')
  save()
  return ok({ token: `mock-${u.user_id}`, user: { user_id: u.user_id, username: u.username, real_name: u.real_name, roles: rolesOf(u.user_id) } })
})

// 下拉字典：区域、规则（接口契约中没有，见 README 缺口 #8）
route('GET', '/api/dicts', () => ok({
  areas: db.area_info.map(({ area_id, area_name, area_type }) => ({ area_id, area_name, area_type })),
  rules: db.judge_rule.map(({ rule_id, rule_name, version_id, judge_object }) => ({ rule_id, rule_name, version_id, judge_object })),
  history_cutoff: historyCutoff(),
}))

// 1. 首页概览
route('GET', '/api/overview', (ctx) => {
  requireRole(ctx, PAGE_ROLES.overview)
  const c = db.risk_clue
  const latest = [...db.judge_batch].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  const e = confusion()
  return ok({
    clue_total: c.length,
    clue_open: c.filter((x) => x.clue_status === 0).length,
    clue_checking: c.filter((x) => x.clue_status === 1).length,
    clue_confirmed: c.filter((x) => x.clue_status === 2).length,
    clue_excluded: c.filter((x) => x.clue_status === 3).length,
    high_risk_cnt: db.risk_score.filter((s) => s.risk_level === 3).length,
    latest_batch: latest && { batch_id: latest.batch_id, rule_id: latest.rule_id, run_status: latest.run_status, duration_ms: latest.duration_ms },
    eval: { tp: e.tp, fp: e.fp, fn: e.fn, tn: e.tn, precision: e.precision, recall: e.recall, fpr: e.fpr },
  })
})

// 2. 区域时段风险列表
route('GET', '/api/region-risk', (ctx) => {
  requireRole(ctx, PAGE_ROLES.risk)
  const q = ctx.query
  const rows = vRegionRisk()
    .filter((r) => (empty(q.batch_id) || r.batch_id === q.batch_id) && (empty(q.area_id) || r.area_id === q.area_id) && (empty(q.risk_level) || r.risk_level === Number(q.risk_level)))
    .sort((a, b) => b.total_score - a.total_score)
  return ok(paginate(rows, q))
})

// 3. 逐条特征判定明细
route('GET', '/api/scores/:id/features', (ctx) => {
  requireRole(ctx, [...PAGE_ROLES.risk, ...PAGE_ROLES.clues])
  const s = db.risk_score.find((x) => x.score_id === Number(ctx.params.id))
  if (!s) notFound('评分')
  return ok({
    score: { ...s, object_id: objectId(s), area_name: areaName(s.area_id), is_clue: s.is_clue },
    features: scoreFeatures(s.score_id),
  })
})

// 4. 线索列表
route('GET', '/api/clues', (ctx) => {
  requireRole(ctx, PAGE_ROLES.clues)
  const q = ctx.query
  const rows = vClueList()
    .filter((r) => (empty(q.status) || r.clue_status === Number(q.status)) && (empty(q.area_id) || r.area_id === q.area_id) && (empty(q.risk_level) || r.risk_level === Number(q.risk_level)))
    .sort((a, b) => (q.order === 'latest' ? b.create_at.localeCompare(a.create_at) : b.total_score - a.total_score))
  return ok(paginate(rows, q))
})

function clueDetail(clueId) {
  const c = db.risk_clue.find((x) => x.clue_id === clueId)
  if (!c) notFound('线索')
  const s = db.risk_score.find((x) => x.score_id === c.score_id)
  return {
    clue: { ...c, assignee_name: userName(c.assignee_id) },
    score: { ...s, object_id: objectId(s), area_name: areaName(s.area_id) },
    features: scoreFeatures(s.score_id),
    feedbacks: db.clue_feedback
      .filter((f) => f.clue_id === clueId)
      .sort((a, b) => a.check_time.localeCompare(b.check_time))
      .map((f) => ({
        ...f,
        checker_name: userName(f.checker_id),
        wrong_features: db.clue_feedback_feature.filter((x) => x.feedback_id === f.feedback_id && x.is_wrong === 1).map((x) => x.feature_id),
      })),
  }
}

// 5. 线索详情
route('GET', '/api/clues/:id', (ctx) => {
  requireRole(ctx, PAGE_ROLES.clues)
  return ok(clueDetail(ctx.params.id))
})

// 6. 线索状态流转（只允许 0→1、0→3、1→2、1→3；关闭时同一次写 close_at，满足 ck_clue_close）
const TRANSITIONS = { 0: [1, 3], 1: [2, 3], 2: [], 3: [] }
route('PATCH', '/api/clues/:id/status', (ctx) => {
  requireRole(ctx, ACTION_ROLES['clue.status'])
  const c = db.risk_clue.find((x) => x.clue_id === ctx.params.id)
  if (!c) notFound('线索')
  const to = Number(ctx.body?.status)
  if (!TRANSITIONS[c.clue_status].includes(to)) bad(`不允许从"${statusName(c.clue_status)}"流转到"${statusName(to) ?? to}"`)
  const from = c.clue_status
  c.clue_status = to
  c.close_at = [2, 3].includes(to) ? nowStr() : null
  audit(ctx.user.user_id, 4, 'risk_clue', c.clue_id, `线索状态变更：${from} → ${to}`) // trg_clue_audit
  save()
  return ok({ clue_id: c.clue_id, clue_status: c.clue_status, close_at: c.close_at })
})

// 7. 提交核查结论（闭环入口）：插入反馈 → 触发器推进状态 → 写被否定的特征
route('POST', '/api/clues/:id/feedback', (ctx) => {
  requireRole(ctx, ACTION_ROLES['clue.feedback'])
  const c = db.risk_clue.find((x) => x.clue_id === ctx.params.id)
  if (!c) notFound('线索')
  if ([2, 3].includes(c.clue_status)) bad('线索已关闭，不能再提交核查结论')
  const b = ctx.body || {}
  const result = Number(b.check_result)
  const method = Number(b.check_method)
  if (![1, 2, 3].includes(result)) bad('核查结论必填')
  if (![1, 2, 3].includes(method)) bad('核查方式必填')
  if (!b.check_remark || !String(b.check_remark).trim()) bad('请填写核查说明')
  const hitIds = db.risk_score_feature.filter((x) => x.score_id === c.score_id && x.is_hit === 1).map((x) => x.feature_id)
  const wrong = [...new Set(b.wrong_feature_ids || [])]
  if (wrong.some((id) => !hitIds.includes(id))) bad('只能否定本线索命中的特征')

  const time = nowStr()
  const feedbackId = Math.max(0, ...db.clue_feedback.map((f) => f.feedback_id)) + 1
  db.clue_feedback.push({ feedback_id: feedbackId, clue_id: c.clue_id, check_result: result, check_method: method, check_remark: String(b.check_remark).trim(), checker_id: ctx.user.user_id, check_time: time, weight_applied: 0 })

  // trg_feedback_close_clue：属实→已确认(2)，不属实→已排除(3)；无法核实不改状态
  if ([1, 2].includes(result)) {
    const from = c.clue_status
    c.clue_status = result === 1 ? 2 : 3
    c.close_at = time
    audit(ctx.user.user_id, 4, 'risk_clue', c.clue_id, `线索状态变更：${from} → ${c.clue_status}`, time) // trg_clue_audit
  }
  wrong.forEach((fid) => db.clue_feedback_feature.push({ feedback_id: feedbackId, feature_id: fid, is_wrong: 1 }))
  save()
  return ok({ feedback_id: feedbackId, clue_status: c.clue_status })
})

function featureRow(f, versionId) {
  const w = db.feature_weight.find((x) => x.version_id === versionId && x.feature_id === f.feature_id)
  const r = w ? withRates(w) : null
  return { ...f, p1: r?.p1 ?? null, p0: r?.p0 ?? null, lift: r?.lift ?? null, weight: r?.weight ?? null, is_valid: r?.is_valid ?? null }
}

// 8. 特征清单（权重取当前已发布版本）
route('GET', '/api/features', (ctx) => {
  requireRole(ctx, PAGE_ROLES.features)
  const q = ctx.query
  const vid = currentVersionId()
  const rows = db.feature_def
    .filter((f) => (empty(q.status) || f.status === Number(q.status)) && (empty(q.cat) || f.feature_cat === Number(q.cat)))
    .map((f) => featureRow(f, vid))
  return ok({ version_id: vid, list: rows })
})

// 9. 特征详情 + 权重历史（另附核查否定记录，见 README 缺口 #9）
route('GET', '/api/features/:id', (ctx) => {
  requireRole(ctx, PAGE_ROLES.features)
  const f = db.feature_def.find((x) => x.feature_id === ctx.params.id)
  if (!f) notFound('特征')
  return ok({
    feature: featureRow(f, currentVersionId()),
    weights: db.feature_version
      .map((v) => {
        const w = db.feature_weight.find((x) => x.version_id === v.version_id && x.feature_id === f.feature_id)
        return w ? { ...withRates(w), version_no: v.version_no, publish_status: v.publish_status } : null
      })
      .filter(Boolean),
    versions: db.feature_version.map(({ version_id, version_no, publish_status }) => ({ version_id, version_no, publish_status })),
    rules: db.rule_feature.filter((rf) => rf.feature_id === f.feature_id).map((rf) => ({ ...rf, rule_name: db.judge_rule.find((r) => r.rule_id === rf.rule_id)?.rule_name })),
    negations: db.clue_feedback_feature
      .filter((x) => x.feature_id === f.feature_id && x.is_wrong === 1)
      .map((x) => {
        const fb = db.clue_feedback.find((b) => b.feedback_id === x.feedback_id)
        return { feedback_id: x.feedback_id, clue_id: fb?.clue_id, check_result: fb?.check_result, check_time: fb?.check_time, check_remark: fb?.check_remark }
      }),
  })
})

// 10. 启停特征
route('PATCH', '/api/features/:id/status', (ctx) => {
  requireRole(ctx, ACTION_ROLES['feature.status'])
  const f = db.feature_def.find((x) => x.feature_id === ctx.params.id)
  if (!f) notFound('特征')
  const st = Number(ctx.body?.status)
  if (![0, 1].includes(st)) bad('状态只能是 0 或 1')
  f.status = st
  audit(ctx.user.user_id, 4, 'feature_def', f.feature_id, `特征${st ? '启用' : '停用'}`)
  save()
  return ok({ feature_id: f.feature_id, status: st })
})

// 11. 版本列表
route('GET', '/api/versions', (ctx) => {
  requireRole(ctx, [...PAGE_ROLES.ops, ...PAGE_ROLES.features])
  return ok([...db.feature_version]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((v) => ({ ...v, weight_cnt: db.feature_weight.filter((w) => w.version_id === v.version_id).length, published_by_name: userName(v.published_by) })))
})

// 12. 发布 / 归档（uk_version_current：同风险类型只能有一个已发布版本，发布前先归档旧版本）
route('PATCH', '/api/versions/:id/publish', (ctx) => {
  requireRole(ctx, ACTION_ROLES['version.publish'])
  const v = db.feature_version.find((x) => x.version_id === ctx.params.id)
  if (!v) notFound('版本')
  const st = Number(ctx.body?.publish_status)
  if (st === 1) {
    if (v.publish_status === 1) bad('该版本已是发布状态')
    db.feature_version.filter((x) => x.risk_type === v.risk_type && x.publish_status === 1).forEach((x) => { x.publish_status = 2 })
    v.publish_status = 1
    v.published_by = ctx.user.user_id
  } else if (st === 2) {
    if (v.publish_status === 2) bad('该版本已归档')
    v.publish_status = 2
  } else bad('publish_status 只能是 1（发布）或 2（归档）')
  audit(ctx.user.user_id, 4, 'feature_version', v.version_id, st === 1 ? '发布版本（旧版本自动归档）' : '归档版本')
  save()
  return ok({ version_id: v.version_id, publish_status: v.publish_status })
})

// 13. 重算权重：sp_calc_feature_weight —— 平滑对数优势比，截断到 ±3，保留 4 位
route('POST', '/api/weights/recalc', (ctx) => {
  requireRole(ctx, ACTION_ROLES['weight.recalc'])
  const vid = ctx.body?.version_id
  const v = db.feature_version.find((x) => x.version_id === vid)
  if (!v) notFound('版本')
  const rows = db.feature_weight.filter((w) => w.version_id === vid)
  const time = nowStr()
  let changed = 0
  for (const w of rows) {
    const next = w.is_valid === 0 ? 0 : Math.min(3, Math.max(-3, round(Math.log(((w.case_hit + 0.5) / (w.case_total - w.case_hit + 0.5)) / ((w.ctrl_hit + 0.5) / (w.ctrl_total - w.ctrl_hit + 0.5))), 4)))
    if (next !== w.weight) {
      audit(ctx.user.user_id, 4, 'feature_weight', `${vid}/${w.feature_id}`, `权重变更：${w.weight} → ${next}`, time) // trg_weight_audit
      w.weight = next
      changed++
    }
    w.calc_at = time
  }
  if (rows.length) {
    v.based_case_cnt = Math.max(...rows.map((w) => w.case_total))
    v.based_ctrl_cnt = Math.max(...rows.map((w) => w.ctrl_total))
    v.calc_at = time
  }
  save()
  return ok({ version_id: vid, feature_cnt: rows.length, changed_cnt: changed })
})

// 14. 批次列表
route('GET', '/api/batches', (ctx) => {
  requireRole(ctx, PAGE_ROLES.ops.concat(PAGE_ROLES.risk))
  const q = ctx.query
  const rows = [...db.judge_batch]
    .filter((b) => empty(q.run_status) || b.run_status === Number(q.run_status))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((b) => ({ ...b, area_name: areaName(b.area_id), operator_name: userName(b.operator_id), rule_name: db.judge_rule.find((r) => r.rule_id === b.rule_id)?.rule_name }))
  return ok(paginate(rows, { size: 100, ...q }))
})

// 15. 创建批次
route('POST', '/api/batches', (ctx) => {
  requireRole(ctx, ACTION_ROLES['batch.create'])
  const b = ctx.body || {}
  if (!/^B\d{10}$/.test(b.batch_id || '')) bad('批次编号格式应为 B + 10 位数字，如 B2026111101')
  if (db.judge_batch.some((x) => x.batch_id === b.batch_id)) bad('批次编号已存在')
  const rule = db.judge_rule.find((r) => r.rule_id === b.rule_id)
  if (!rule) bad('请选择研判规则')
  if (!TIME_RE.test(b.data_start || '') || !TIME_RE.test(b.data_end || '')) bad('数据窗时间格式应为 YYYY-MM-DD HH:mm:ss')
  if (b.data_end <= b.data_start) bad('数据窗止必须晚于数据窗起（ck_batch_window）')
  if (b.data_start < historyCutoff()) bad(`数据窗起必须在观察段（≥ ${historyCutoff()}），研判不读历史段`)
  if (b.area_id && !db.area_info.some((a) => a.area_id === b.area_id)) bad('区域不存在')
  const batch = {
    batch_id: b.batch_id, rule_id: rule.rule_id, version_id: b.version_id || rule.version_id, judge_object: rule.judge_object,
    data_start: b.data_start, data_end: b.data_end, area_id: b.area_id || null, run_status: 0, run_no: 0,
    object_cnt: 0, clue_cnt: 0, duration_ms: null, operator_id: ctx.user.user_id, created_at: nowStr(),
  }
  db.judge_batch.push(batch)
  audit(ctx.user.user_id, 3, 'judge_batch', batch.batch_id, '创建研判批次')
  save()
  return ok({ batch_id: batch.batch_id, run_status: 0 })
})

// 16. 执行研判
route('POST', '/api/batches/:id/run', (ctx) => {
  requireRole(ctx, ACTION_ROLES['batch.run'])
  const batch = db.judge_batch.find((x) => x.batch_id === ctx.params.id)
  if (!batch) notFound('批次')
  if (![0, 3].includes(batch.run_status)) bad('只有"待执行"或"失败"的批次可以执行')
  const r = runBatch(batch, ctx)
  batch.run_no += 1
  if (r.failed) {
    batch.run_status = 3
    batch.duration_ms = 1
    audit(ctx.user.user_id, 7, 'judge_batch', batch.batch_id, `研判失败：${r.message}`)
    save()
    return ok({ batch_id: batch.batch_id, run_status: 3, object_cnt: 0, clue_cnt: 0, duration_ms: 1, message: r.message })
  }
  Object.assign(batch, { run_status: 2, object_cnt: r.object_cnt, clue_cnt: r.clue_cnt, duration_ms: r.duration_ms })
  audit(ctx.user.user_id, 7, 'judge_batch', batch.batch_id, `执行研判，对象 ${r.object_cnt} 个，线索 ${r.clue_cnt} 条`)
  save()
  return ok({ batch_id: batch.batch_id, object_cnt: r.object_cnt, clue_cnt: r.clue_cnt, skipped_cnt: r.skipped, duration_ms: r.duration_ms, run_status: 2 })
})

// 17. 混淆矩阵与指标
route('GET', '/api/eval/confusion', (ctx) => {
  requireRole(ctx, PAGE_ROLES.eval)
  return ok(confusion(ctx.query.batch_id))
})

// 18. 标签分布
route('GET', '/api/eval/labels', (ctx) => {
  requireRole(ctx, PAGE_ROLES.eval)
  const names = { 1: '正样本', 2: '干扰样本', 3: '对照样本' }
  return ok([1, 2, 3].map((t) => ({ sample_type: t, name: names[t], cnt: db.eval_label.filter((l) => l.sample_type === t).length })))
})

// 19. 审计日志（时间按半开区间过滤）
route('GET', '/api/audit', (ctx) => {
  requireRole(ctx, PAGE_ROLES.audit)
  const q = ctx.query
  const rows = db.audit_log
    .filter((l) => (empty(q.user_id) || l.user_id === q.user_id) && (empty(q.op_type) || l.op_type === Number(q.op_type)) && inRange(l.op_time, q.from, q.to))
    .sort((a, b) => b.op_time.localeCompare(a.op_time) || b.log_id - a.log_id)
    .map((l) => ({ ...l, user_name: userName(l.user_id) }))
  return ok(paginate(rows, q))
})

// 20. 用户与角色（不返回 password_hash / salt）
route('GET', '/api/users', (ctx) => {
  requireRole(ctx, PAGE_ROLES.admin.concat(PAGE_ROLES.audit))
  return ok(db.sys_user.map((u) => ({ user_id: u.user_id, username: u.username, real_name: u.real_name, status: u.status, roles: rolesOf(u.user_id) })))
})

// 21. 参数配置
route('GET', '/api/params', (ctx) => {
  requireRole(ctx, PAGE_ROLES.admin)
  return ok([...db.param_config].sort((a, b) => a.param_key.localeCompare(b.param_key)))
})

// 22. 修改参数
route('PATCH', '/api/params/:key', (ctx) => {
  requireRole(ctx, ACTION_ROLES['param.update'])
  const p = db.param_config.find((x) => x.param_key === ctx.params.key)
  if (!p) notFound('参数')
  const v = String(ctx.body?.param_value ?? '').trim()
  if (p.param_type === 1 && !/^-?\d+$/.test(v)) bad('该参数应为整数')
  if (p.param_type === 2 && !/^-?\d+(\.\d+)?$/.test(v)) bad('该参数应为小数')
  if (p.param_key === 'history_cutoff' && !TIME_RE.test(v)) bad('时间边界格式应为 YYYY-MM-DD HH:mm:ss')
  const old = p.param_value
  p.param_value = v
  p.updated_at = nowStr()
  audit(ctx.user.user_id, 4, 'param_config', p.param_key, `参数修改：${old} → ${v}`)
  save()
  return ok(p)
})

// 23. 历史案件（只读 v_case_history，时间半开区间）
route('GET', '/api/cases', (ctx) => {
  requireRole(ctx, PAGE_ROLES.cases)
  const q = ctx.query
  const rows = vCaseHistory()
    .filter((c) => (empty(q.area_id) || c.area_id === q.area_id) && inRange(c.occur_time, q.from, q.to))
    .sort((a, b) => a.occur_time.localeCompare(b.occur_time))
    .map((c) => ({ ...c, area_name: areaName(c.area_id), occur_hour: parseTime(c.occur_time).getHours() }))
  return ok({ ...paginate(rows, q), history_cutoff: historyCutoff(), case_info_total: db.case_info.length })
})

// 24. 数据健康检查（四项都应为 0）
route('GET', '/api/health', () => {
  const rows = Object.values(db).reduce((s, t) => s + (Array.isArray(t) ? t.length : 0), 0)
  const persons = new Set(db.person_info.map((p) => p.person_id))
  const areas = new Set(db.area_info.map((a) => a.area_id))
  const cutoff = historyCutoff()
  return ok({
    tables: Object.keys(db).length,
    rows,
    orphan_person: db.consume_record.filter((c) => !persons.has(c.person_id)).length,
    orphan_area: db.consume_record.filter((c) => !areas.has(db.place_info.find((p) => p.place_id === c.place_id)?.area_id)).length,
    case_after_cutoff: db.case_info.filter((c) => c.occur_time >= cutoff).length,
    feature_bad_match_src: db.feature_def.filter((f) => f.match_src === 'case_info').length,
  })
})

// ---------------------------------------------------------------------------
// 入口
// ---------------------------------------------------------------------------

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

export async function mockRequest(method, url, { body, token } = {}) {
  const [path, qs = ''] = url.split('?')
  const query = Object.fromEntries(new URLSearchParams(qs))
  const userId = token?.startsWith('mock-') ? token.slice(5) : null
  const user = db.sys_user.find((u) => u.user_id === userId && u.status === 1) || null
  const ctx = { query, body, user, roles: user ? rolesOf(user.user_id) : [], params: {} }

  await delay(path.endsWith('/run') ? 900 : 120 + Math.random() * 180)

  for (const r of routes) {
    const m = r.method === method && path.match(r.re)
    if (!m) continue
    r.keys.forEach((k, i) => { ctx.params[k] = decodeURIComponent(m[i + 1]) })
    try {
      return r.handler(ctx)
    } catch (e) {
      if (e instanceof ApiError) return { status: e.status, body: { code: e.code, message: e.message, data: null } }
      console.error(e)
      return { status: 500, body: { code: 5000, message: '模拟服务内部错误', data: null } }
    }
  }
  return { status: 404, body: { code: 4040, message: `接口不存在：${method} ${path}`, data: null } }
}
