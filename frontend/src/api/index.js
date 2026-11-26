// 请求封装：照《前端交接文档》附录 C 的写法，返回 body.data，code≠0 抛错，401 统一跳登录。
export const API_MODE = 'real'
const BASE = import.meta.env.VITE_API_BASE || ''
function selectSource() {
  const requested = new URLSearchParams(location.search).get('source')
  if (requested === 'demo' || requested === 'real') {
    sessionStorage.setItem('risk_data_source', requested)
    return requested
  }
  if (requested !== null) return 'invalid'
  return sessionStorage.getItem('risk_data_source') || import.meta.env.VITE_DATA_SOURCE || window.RISK_DEFAULT_SOURCE || 'demo'
}
export const DATA_SOURCE = selectSource()
export const sourceKey = key => DATA_SOURCE === 'demo' ? key : key + '_' + DATA_SOURCE
const TOKEN_KEY = sourceKey('risk_alert_token')

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(t) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* 忽略 */ }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

export class RequestError extends Error {
  constructor(message, status, code) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request(method, path, body) {
  const token = getToken()
  let status
  let payload
  {
    let res
    try {
      res = await fetch(BASE + path, {
        method,
        headers: { 'X-Data-Source': DATA_SOURCE, ...(body instanceof FormData ? {} : {'Content-Type': 'application/json'}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      })
    } catch {
      throw new RequestError(`无法连接后端 ${BASE}，请确认服务已启动并开启 CORS`, 0, -1)
    }
    status = res.status
    payload = await res.json().catch(() => ({ code: -1, message: `接口返回的不是 JSON（HTTP ${status}）` }))
  }
  if (status === 401 && !path.startsWith('/api/login')) {
    onUnauthorized()
    throw new RequestError('未登录或登录已过期', 401, payload?.code)
  }
  if (!payload || payload.code !== 0) throw new RequestError(payload?.message || '请求失败', status, payload?.code)
  return payload.data
}

// 把对象拼成查询串，空值不传
function qs(params = {}) {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString()
  return s ? `?${s}` : ''
}

const get = (path, params) => request('GET', path + qs(params))
const patch = (path, body) => request('PATCH', path, body)
const post = (path, body) => request('POST', path, body)

export const api = {
  login: (body) => post('/api/login', body),
  logout: () => request('DELETE', '/api/auth/sessions/current'),
  chain: (id) => get(`/api/clues/${id}/chain`),
  evidenceSubjects: (p) => get('/api/evidence/subjects',p),
  evidenceEvents: (p) => get('/api/evidence/events',p),
  people: (p) => get('/api/person-risks', p),
  personTimeline: (id,p) => get(`/api/persons/${id}/timeline`,p),
  trends: (p) => get('/api/risk-trends',p),
  dataCatalog: () => get('/api/data'),
  dataQuality: () => get('/api/data-quality'),
  dataRows: (resource,p) => get(`/api/data/${resource}`,p),
  createRow: (resource,b) => post(`/api/data/${resource}`,b),
  updateRow: (resource,id,b) => patch(`/api/data/${resource}/${id}`,b),
  deleteRow: (resource,id) => request('DELETE',`/api/data/${resource}/${id}`),
  importRows: (resource,file) => { const form=new FormData();form.append('file',file);return post(`/api/data/${resource}/imports`,form) },
  dicts: () => get('/api/dicts'),
  overview: () => get('/api/overview'), //                                    1
  regionRisk: (p) => get('/api/region-risk', p), //                           2
  scoreFeatures: (id) => get(`/api/scores/${id}/features`), //                3
  clues: (p) => get('/api/clues', p), //                                      4
  clueDetail: (id) => get(`/api/clues/${id}`), //                             5
  setClueStatus: (id, body) => patch(`/api/clues/${id}/status`, body), //     6
  submitFeedback: (id, body) => post(`/api/clues/${id}/feedback`, body), //   7
  features: (p) => get('/api/features', p), //                                8
  featureDetail: (id) => get(`/api/features/${id}`), //                       9
  setFeatureStatus: (id, body) => patch(`/api/features/${id}/status`, body), // 10
  versions: () => get('/api/versions'), //                                    11
  publishVersion: (id, body) => patch(`/api/versions/${id}/publish`, body), // 12
  recalcWeights: (body) => post('/api/weights/recalc', body), //              13
  batches: (p) => get('/api/batches', p), //                                  14
  createBatch: (body) => post('/api/batches', body), //                       15
  runBatch: (id) => post(`/api/batches/${id}/run`), //                        16
  confusion: (p) => get('/api/eval/confusion', p), //                         17
  evalSamples: (p) => get('/api/eval/samples', p),
  labels: () => get('/api/eval/labels'), //                                   18
  audit: (p) => get('/api/audit', p), //                                      19
  users: () => get('/api/users'), //                                          20
  params: () => get('/api/params'), //                                        21
  setParam: (key, body) => patch(`/api/params/${key}`, body), //              22
  cases: (p) => get('/api/cases', p), //                                      23
  health: () => get('/api/health'), //                                        24
  riskMap: (p) => get('/api/risk-map',p), //                                   25 风险地图
}
