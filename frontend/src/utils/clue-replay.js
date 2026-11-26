export function chronological(rows) {
  return rows.slice().sort((a,b)=>a.event_at.localeCompare(b.event_at)||String(a.node_id??a.event_id??a.chain_id).localeCompare(String(b.node_id??b.event_id??b.chain_id),undefined,{numeric:true})||Number(!a.event_id?.endsWith(':start'))-Number(!b.event_id?.endsWith(':start')))
}
export function replaySegments(events, singleChain=false) {
  const lines=[]
  for(let i=1;i<events.length;i++){
    const from=events[i-1],to=events[i]
    // No spatial segment may bridge an unlocated information node.
    if(from.area_id && to.area_id && from.area_id!==to.area_id)lines.push({from:from.area_id,to:to.area_id,index:i,related:singleChain,simultaneous:from.event_at===to.event_at})
  }
  return lines
}
export function jumpPoint(from,to,progress) {
  const t=Math.max(0,Math.min(1,progress))
  const distance=Math.hypot(to.x-from.x,to.z-from.z)
  const travel=Math.min(1,t/.76),ease=travel*travel*(3-2*travel)
  const height=t<.76 ? Math.sin(travel*Math.PI)*(distance<.01?9:Math.min(26,7+distance*.2)) : Math.sin((t-.76)/.24*Math.PI)*1.8
  return {x:from.x+(to.x-from.x)*ease,z:from.z+(to.z-from.z)*ease,y:3.5+height,landed:t>=.76,pulse:t>=.76?(t-.76)/.24:0}
}
