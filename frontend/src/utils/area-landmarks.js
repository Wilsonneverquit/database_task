// Visual teaching scenarios, not surveyed buildings or store-level coordinates.
export const AREA_LANDMARKS = [
  {id:'A01',name:'中心商务区',kind:'business',short:'写字楼群 · 商务广场',ground:'#dce2df',features:['玻璃塔楼','入口广场']},
  {id:'A02',name:'老城餐饮街',kind:'oldstreet',short:'坡屋顶老街 · 连续餐饮店面',ground:'#e3ddcb',features:['低层坡屋顶','窄巷与门店']},
  {id:'A03',name:'东门居住区',kind:'residential',short:'住宅组团 · 庭院绿化',ground:'#dfe6d5',features:['成组住宅','小区庭院']},
  {id:'A04',name:'南站交通区',kind:'station',short:'站房雨棚 · 站前广场',ground:'#e0e3dc',features:['站房与站台','接驳车道']},
  {id:'A05',name:'大学生活区',kind:'campus',short:'操场跑道 · 教学楼',ground:'#d9e5cd',features:['田径操场','校园教学楼']},
  {id:'A06',name:'滨河休闲区',kind:'riverside',short:'河岸步道 · 滨水绿带',ground:'#d7e4c8',features:['连续河道','滨水步道与小桥']},
  {id:'A07',name:'西城工业区',kind:'industrial',short:'厂房仓库 · 装卸场地',ground:'#dce0da',features:['大跨度厂房','装卸场地']},
  {id:'A08',name:'北高速出入口',kind:'highway',short:'高速主线 · 弯曲匝道',ground:'#dce4d1',features:['高速主线','出入口匝道与门架']},
  {id:'A09',name:'城南社区',kind:'community',short:'低层社区 · 活动绿地',ground:'#dce7ce',features:['低层住宅','社区活动绿地']},
  {id:'A10',name:'东城商业街',kind:'commercial',short:'沿街商业 · 步行空间',ground:'#e5e1d4',features:['沿街商铺','商业步行空间']},
  {id:'A11',name:'夜市步行街',kind:'nightmarket',short:'摊棚街带 · 步行市集',ground:'#e9e0cb',features:['成排摊棚','步行街与店面']},
  {id:'A12',name:'近郊乡镇',kind:'rural',short:'乡间低屋 · 不规则田块',ground:'#d8e4bf',features:['低层房屋','农田与乡间道路']},
]
const aliases={'中心商圈':'business','大学城':'campus','火车站片区':'station','城南客运站':'station','滨江路沿线':'riverside','西郊乡镇':'rural','高新工业园':'industrial','城北老街':'oldstreet'}
export function areaLandmark(area){
  const exact=AREA_LANDMARKS.find(p=>p.name===area?.area_name)
  const alias=aliases[area?.area_name]
  return exact || (alias?AREA_LANDMARKS.find(p=>p.kind===alias):null) || {kind:'generic',short:'城市街区',features:['区域级位置示意'],ground:'#dfe3d6'}
}
export function landmarkSites(nodes){
  return nodes.map(node=>{
    const distances=nodes.filter(n=>n.area_id!==node.area_id).map(n=>Math.hypot(n.cityLon-node.cityLon,n.cityLat-node.cityLat))
    const radius=Math.max(3,Math.min(6.9,(Math.min(...distances)||16)*.43))
    return {node,profile:areaLandmark(node),radius,scale:radius*4.887/31}
  }).filter(s=>s.profile.kind!=='generic')
}
// Solve the gentle street warp so the river can be anchored at the actual display site.
export function inverseCityWarp(lon,lat,warp){
  let x=lon,y=lat
  for(let i=0;i<12;i++){const [a,b]=warp(x,y);x+=lon-a;y+=lat-b}
  return [x,y]
}
export function anchoredRiver(sites,warp){
  const site=sites.find(s=>s.profile.kind==='riverside')
  const base=lat=>-17+4*Math.sin(lat*.075)+1.8*Math.sin(lat*.21)
  if(!site)return base
  const [x,y]=inverseCityWarp(site.node.cityLon-site.radius*.58,site.node.cityLat,warp),shift=x-base(y)
  return lat=>base(lat)+shift
}
