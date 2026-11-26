export const MAP_QUALITY = Object.freeze({
  smooth: {label:'流畅',pixelRatio:1,textureSize:1024,shadowSize:512,shadows:false,detail:1,environment:false},
  standard: {label:'标准',pixelRatio:1.5,textureSize:2048,shadowSize:1024,shadows:true,detail:2,environment:true},
  fine: {label:'精细',pixelRatio:1.75,textureSize:4096,shadowSize:2048,shadows:true,detail:2,environment:true},
})
export function initialMapQuality({width=1280,memory=8,cores=8,saved}={}) {
  if(Object.hasOwn(MAP_QUALITY,saved))return saved
  return width<700||memory<4||cores<4?'smooth':'standard'
}
// A screen-space layout: current landing first, then selection, then stable area ID.
export function placeMapLabels(rows,{width,height,selected='',landing='',detail=0,preview=false}) {
  if(preview)return []
  const placed=[]
  const priority=n=>n.area_id===landing?2:n.area_id===selected?1:0
  const candidates=rows.slice().sort((a,b)=>priority(b)-priority(a)||a.area_id.localeCompare(b.area_id))
  for(const n of candidates){
    if(!n.visible||detail===0&&priority(n)===0&&placed.length>=7)continue
    const labelWidth=n.area_name.length*12+24+(priority(n)?40:0)
    for(const offset of priority(n)?[18,-40,42,-66]:[14,-34,38]){
      const box={left:n.left-labelWidth/2,right:n.left+labelWidth/2,top:n.top+offset,bottom:n.top+offset+26}
      if(box.left<8||box.right>width-8||box.top<8||box.bottom>height-10)continue
      if(placed.some(p=>box.left<p.box.right+5&&box.right>p.box.left-5&&box.top<p.box.bottom+4&&box.bottom>p.box.top-4))continue
      placed.push({...n,top:box.top,box});break
    }
  }
  return placed
}
// Translation needed to keep a ground hit at the same pixel during a camera dolly.
export function zoomAnchorShift(before,after,maximum=40){
  if(!before||!after)return {x:0,y:0,z:0}
  const x=before.x-after.x,y=before.y-after.y,z=before.z-after.z,length=Math.hypot(x,y,z)
  if(!Number.isFinite(length))return {x:0,y:0,z:0}
  const scale=length>maximum?maximum/length:1
  return {x:x*scale,y:y*scale,z:z*scale}
}
