// Display-only expansion of the fictional city; never writes geographic data.
export const GLOBE_RADIUS = 700
const radians = Math.PI / 180
export function spherePoint(lon, lat, radius = GLOBE_RADIUS) {
  const a = lon * radians, b = lat * radians
  return {x:radius*Math.cos(b)*Math.sin(a),y:radius*Math.cos(b)*Math.cos(a),z:-radius*Math.sin(b)}
}
export function globeLayout(nodes) {
  return nodes.map(n=>{
    const hash=[...n.area_id].reduce((v,c)=>(v*31+c.charCodeAt(0))>>>0,17)
    const spread=[.58,.92,.73,1.04,.84][hash%5]
    const cityLon=n.x/82*40*spread+((hash>>>4)%7-3)*.65,cityLat=-n.z/82*28*spread+((hash>>>7)%7-3)*.55
    return {...n,cityLon,cityLat,displayLon:cityLon*.4,displayLat:cityLat*.4,...spherePoint(cityLon*.4,cityLat*.4)}
  })
}
export function angularDistance(a,b) {
  const la=Math.hypot(a.x,a.y,a.z),lb=Math.hypot(b.x,b.y,b.z)
  return Math.acos(Math.max(-1,Math.min(1,(a.x*b.x+a.y*b.y+a.z*b.z)/(la*lb))))
}
export function globeJump(a,b,progress,clearance=0) {
  const t=Math.max(0,Math.min(1,progress)),p=Math.min(1,t/.76)
  // Rise over the open landing plaza before crossing nearby tall buildings;
  // reverse that movement on approach, without moving the destination.
  const travel=Math.max(0,Math.min(1,(p-.12)/.76)),ease=travel**3*(travel*(travel*6-15)+10)
  const angle=angularDistance(a,b),sin=Math.sin(angle)
  let x,y,z
  if(angle<1e-5){x=b.x;y=b.y;z=b.z}
  else {const u=Math.sin((1-ease)*angle)/sin,v=Math.sin(ease*angle)/sin;x=a.x*u+b.x*v;y=a.y*u+b.y*v;z=a.z*u+b.z*v}
  const lift=t<.76?Math.pow(Math.max(0,Math.sin(p*Math.PI)),.45)*(angle<1e-5?7:Math.max(Math.min(65,24+angle*60),clearance*1.3+14)):Math.sin((t-.76)/.24*Math.PI)*1.5
  const radius=GLOBE_RADIUS+3+lift,scale=radius/Math.hypot(x,y,z)
  return {x:x*scale,y:y*scale,z:z*scale,landed:t>=.76,pulse:t>=.76?(t-.76)/.24:0}
}
export function jumpDuration(a,b){return a&&b?Math.min(2600,1400+angularDistance(a,b)*650):1800}
export function wheelDistance(distance,delta,minimum=130,maximum=650){return Math.max(minimum,Math.min(maximum,distance*Math.exp(Math.max(-160,Math.min(160,delta))*.002)))}
