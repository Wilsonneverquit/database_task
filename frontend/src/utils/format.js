// 展示用格式化函数

export const pad2 = (n) => String(n).padStart(2, '0')

// 时段：23 → "23:00–23:59"
export const hourLabel = (h) => (h === null || h === undefined ? '—' : `${pad2(h)}:00–${pad2(h)}:59`)

export const fixed = (n, d = 2) => (n === null || n === undefined || Number.isNaN(n) ? '—' : Number(n).toFixed(d))

// 权重带符号：+1.1693 / -1.5918
export const signed = (n, d = 4) => (n === null || n === undefined ? '—' : `${n > 0 ? '+' : ''}${Number(n).toFixed(d)}`)

export const percent = (n, d = 1) => (n === null || n === undefined ? '—' : `${(n * 100).toFixed(d)}%`)

// "F001:+1.1693;F002:+2.9285" → [{ id, weight }]
export function parseHitFeatures(s) {
  if (!s) return []
  return s.split(';').map((p) => {
    const [id, w] = p.split(':')
    return { id, weight: Number(w) }
  })
}

// 研判对象的可读名称；个人对象只显示编号（脱敏，不出现姓名）
export function objectLabel(o, areaName) {
  if (!o) return '—'
  if (o.object_type === 2) return `个人对象 ${o.person_id || o.object_id}`
  const name = areaName || o.area_name || o.area_id
  const day = o.day_type === 1 ? '工作日' : o.day_type === 2 ? '周末' : (o.day_type_name || '')
  return `${name} · ${day} · ${pad2(o.hour_slot)} 点`
}

// 通用脱敏：保留首尾，中间打码（身份证、手机号、车牌等一律不出明文）
export function mask(s, keepStart = 1, keepEnd = 1) {
  if (!s) return '—'
  const str = String(s)
  if (str.length <= keepStart + keepEnd) return '*'.repeat(str.length)
  return str.slice(0, keepStart) + '*'.repeat(str.length - keepStart - keepEnd) + str.slice(-keepEnd)
}

// 本地时间 → 'YYYY-MM-DD HH:mm:ss'
export function toDateTime(d) {
  if (!d) return ''
  const x = d instanceof Date ? d : new Date(d)
  return `${x.getFullYear()}-${pad2(x.getMonth() + 1)}-${pad2(x.getDate())} ${pad2(x.getHours())}:${pad2(x.getMinutes())}:${pad2(x.getSeconds())}`
}

// 日期选择器给的 [起日, 止日] → 半开区间 { from: 起日 00:00:00, to: 止日次日 00:00:00 }
// 原因见《前端交接文档》5.1：BETWEEN '…-31' 会漏掉 31 日当天的记录
export function halfOpenRange(range) {
  if (!range || range.length !== 2) return { from: undefined, to: undefined }
  const [a, b] = range.map((s) => new Date(`${s}T00:00:00`))
  b.setDate(b.getDate() + 1)
  return { from: toDateTime(a), to: toDateTime(b) }
}
