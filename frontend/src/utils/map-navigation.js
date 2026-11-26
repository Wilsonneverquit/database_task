export function dragBindings(mode){return mode==='rotate'?{left:'ROTATE',right:'PAN',touch:'ROTATE'}:{left:'PAN',right:'ROTATE',touch:'PAN'}}
export function clampMapTarget(target,radius){
  return {x:Math.max(-235,Math.min(235,target.x)),y:Math.max(radius-85,Math.min(radius+25,target.y)),z:Math.max(-160,Math.min(160,target.z))}
}
// Hysteresis prevents fine detail flashing on/off near a zoom threshold.
export function mapDetailLevel(distance,previous=0){
  if(distance<215)return 2
  if(distance>365)return 0
  if(previous===2&&distance<245)return 2
  if(previous===0&&distance>330)return 0
  return 1
}
