import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'
import { createSeed } from '../src/api/mock/seed.js'
import { allPages, byNewest, heatCells, nightHours } from '../src/utils/dashboard.js'
import { streetLayout, riskColor } from '../src/utils/street-map.js'

const vite = await createServer({ root:fileURLToPath(new URL('..',import.meta.url)), configFile:fileURLToPath(new URL('../vite.config.js',import.meta.url)), server: { middlewareMode: true }, appType: 'custom' })
try {
  const { mockRequest } = await vite.ssrLoadModule('/src/api/mock/server.js')
  const seed = createSeed()
  // Visual topology must be connected, stable across input order, and leave data intact.
  const source = structuredClone(seed.area_info)
  const street = streetLayout(source)
  assert.equal(street.nodes.length, 12)
  assert.equal(street.edges.length, 15)
  assert.deepEqual(streetLayout([...source].reverse()), street)
  assert.deepEqual(source, seed.area_info)
  const reached = new Set([street.nodes[0].area_id])
  for (let i=0;i<street.nodes.length;i++) for (const edge of street.edges) {
    if(reached.has(edge.a)) reached.add(edge.b)
    if(reached.has(edge.b)) reached.add(edge.a)
  }
  assert.equal(reached.size, street.nodes.length)
  assert.equal(new Set(street.edges.map((e)=>e.id)).size,street.edges.length)
  for(const node of street.nodes) assert.ok(Number.isFinite(node.x)&&Number.isFinite(node.z))
  assert.equal(streetLayout([]).edges.length,0)
  assert.equal(streetLayout([source[0]]).edges.length,0)
  assert.equal(streetLayout([{...source[0],lng:null}]).nodes.length,0)
  assert.notEqual(riskColor(0),riskColor(null))
  assert.notEqual(riskColor(9),riskColor(20))
  const token = 'mock-' + seed.sys_user.find((u) => u.username === 'analyst1').user_id
  const get = async (path, params = {}, as = token) => {
    const response = await mockRequest('GET', path + '?' + new URLSearchParams(params), { token: as })
    assert.equal(response.status, 200, response.body.message)
    return response.body.data
  }
  const batches = (await allPages((p) => get('/api/batches', p), { run_status: 2 }))
    .filter((b) => b.judge_object === 1).sort(byNewest)
  assert.ok(batches.length)
  const scores = await allPages((p) => get('/api/region-risk', p), { batch_id: batches[0].batch_id })
  assert.ok(scores.length)
  assert.ok(scores.every((s) => s.batch_id === batches[0].batch_id))
  assert.equal(scores.length, seed.risk_score.filter((s) => s.object_type === 1 && s.batch_id === batches[0].batch_id).length)
  for (const day of [1, 2]) assert.equal(heatCells(scores, day).length, scores.filter((s) => s.day_type === day).length)
  assert.throws(() => heatCells([scores[0], scores[0]], scores[0].day_type), /重复/)
  assert.equal(nightHours.length, 24)
  assert.equal(nightHours.indexOf(0), nightHours.indexOf(23) + 1)

  const dictionary = await get('/api/dicts')
  assert.ok(dictionary.rules.every((r) => Number.isFinite(r.low_threshold) && Number.isFinite(r.high_threshold)))
  assert.equal(dictionary.features.length, seed.feature_def.length)

  const all = await allPages((p) => get('/api/region-risk', p))
  assert.equal(all.length, seed.risk_score.filter((s) => s.object_type === 1).length)
  const paginated = await allPages(async ({ page }) => ({ list: Array.from({ length: page < 3 ? 200 : 51 }, (_, i) => (page - 1) * 200 + i), size: 200, total: 451 }))
  assert.equal(paginated.length, 451)
  assert.equal(new Set(paginated).size, 451)

  const map = await get('/api/risk-map')
  for (const night of map.risk) for (const area of night.areas) {
    const score = seed.risk_score.find((s) => s.score_id === area.score_id)
    assert.ok(score)
    assert.equal(score.area_id, area.area_id)
    assert.equal(score.total_score, area.total_score)
  }
  const areaId = map.risk.at(-1).areas[0].area_id
  const clues = await allPages((p) => get('/api/clues', p), { area_id: areaId })
  assert.ok(clues.every((c) => c.area_id === areaId))

  for (const name of ['admin', 'dataop', 'featop']) {
    const as = 'mock-' + seed.sys_user.find((u) => u.username === name).user_id
    assert.equal((await mockRequest('GET', '/api/risk-map', { token: as })).status, 403)
    assert.equal((await mockRequest('GET', '/api/region-risk', { token: as })).status, 403)
  }
  const teacher = 'mock-' + seed.sys_user.find((u) => u.username === 'teacher').user_id
  for (const batchId of ['', batches[0].batch_id]) {
    const cm=await get('/api/eval/confusion',{batch_id:batchId},teacher)
    const detail=await get('/api/eval/samples',{batch_id:batchId,size:200},teacher)
    const rows=await allPages((p)=>get('/api/eval/samples',p,teacher),{batch_id:batchId})
    for(const key of ['tp','fp','fn','tn']) {
      assert.equal(detail.result_counts[key],cm[key])
      assert.equal(rows.filter((r)=>r.result===key).length,cm[key])
      const filtered=await get('/api/eval/samples',{batch_id:batchId,result:key},teacher)
      assert.equal(filtered.total,cm[key])
    }
    assert.equal(detail.joined_total,cm.tp+cm.fp+cm.fn+cm.tn)
    assert.equal(new Set(rows.map((r)=>r.row_id)).size,rows.length)
    assert.equal(detail.sample_total,seed.eval_label.length)
    for(const row of rows.filter((r)=>r.score_id===null)) assert.equal(row.prediction,0)
  }
  const board=await allPages((p)=>get('/api/clues',p))
  assert.equal(board.length,seed.risk_clue.length)
  for(const status of [0,1,2,3]) assert.equal(board.filter((r)=>r.clue_status===status).length,seed.risk_clue.filter((r)=>r.clue_status===status).length)
  assert.equal((await mockRequest('GET','/api/eval/samples',{token:'mock-'+seed.sys_user.find((u)=>u.username==='analyst2').user_id})).status,403)
  assert.equal((await mockRequest('PATCH', `/api/clues/${seed.risk_clue[0].clue_id}/status`, { token: teacher, body: { status: 1 } })).status, 403)
  const analystToken='mock-'+seed.sys_user.find((u)=>u.username==='analyst2').user_id
  const openClue=seed.risk_clue.find((c)=>c.clue_status===0)
  assert.equal((await mockRequest('PATCH',`/api/clues/${openClue.clue_id}/status`,{token:analystToken,body:{status:1}})).status,200)
  assert.equal((await get(`/api/clues/${openClue.clue_id}`,{},analystToken)).clue.clue_status,1)
  // 开始核查不会直接关闭线索；结论仍须经过反馈接口。
  assert.equal((await get(`/api/clues/${openClue.clue_id}`,{},analystToken)).clue.close_at,null)
  console.log('PASS: stable street topology, single-batch scope, night hours, rule thresholds, pagination, map links, area filtering, role access, kanban counts, evaluation detail reconciliation')
} finally {
  await vite.close()
}
