// Visual geometry only. No roads or links are business evidence.
import {mapBuildings} from './map-cartography.js'
export function riskColor(score) {
  if (score == null || !Number.isFinite(Number(score))) return '#dce1dd'
  const t = Math.max(0, Math.min(1, Number(score) / 100))
  return `rgb(${Math.round(244 - 76 * t)},${Math.round(228 - 164 * t)},${Math.round(222 - 165 * t)})`
}

export function streetLayout(areas) {
  const valid = areas.filter((a) => a.lng != null && a.lat != null && Number.isFinite(Number(a.lng)) && Number.isFinite(Number(a.lat)))
    .slice().sort((a, b) => a.area_id.localeCompare(b.area_id))
  if (!valid.length) return { nodes: [], edges: [], roads: [], buildings: [] }
  const lngs = valid.map((a) => Number(a.lng)), lats = valid.map((a) => Number(a.lat))
  const cx = (Math.min(...lngs) + Math.max(...lngs)) / 2, cz = (Math.min(...lats) + Math.max(...lats)) / 2
  const longitudeScale = Math.cos(cz * Math.PI / 180)
  const span = Math.max((Math.max(...lngs) - Math.min(...lngs)) * longitudeScale, Math.max(...lats) - Math.min(...lats), .01)
  const nodes = valid.map((a) => ({ ...a, x: (Number(a.lng) - cx) * longitudeScale / span * 164, z: -(Number(a.lat) - cz) / span * 164 }))
  const candidates = []
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
    const a = nodes[i], b = nodes[j]
    candidates.push({ id: `${a.area_id}:${b.area_id}`, a: a.area_id, b: b.area_id, distance: Math.hypot(a.x - b.x, a.z - b.z) })
  }
  candidates.sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id))
  const parents = new Map(nodes.map((a) => [a.area_id, a.area_id]))
  function root(id) { while (parents.get(id) !== id) id = parents.get(id); return id }
  const edges = []
  // Stable minimum spanning tree, then up to four short neighbouring links.
  for (const edge of candidates) if (root(edge.a) !== root(edge.b)) {
    parents.set(root(edge.a), root(edge.b)); edges.push(edge)
  }
  const backbone = new Set(edges.map((e) => e.id))
  edges.push(...candidates.filter((e) => !backbone.has(e.id)).slice(0, 4))
  return { nodes, edges, roads:[], buildings:mapBuildings.filter(b=>!nodes.some(n=>Math.abs(n.x-b.x)<b.w/2+8&&Math.abs(n.z-b.z)<b.d/2+8)) }
}

export function edgeHeight(distance) { return Math.min(27, 8 + distance * .22) }
