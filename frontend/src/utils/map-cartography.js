// Local fictional cartography. Same world-space texture in 3D and SVG fallback.
const parks = [[-160,-95,65,55],[-32,-132,55,34],[95,35,72,42],[20,115,58,60],[-186,120,70,50]]
export const mapBuildings=[]
function createMap() {
  const parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-360 -360 720 720" width="2048" height="2048"><rect x="-360" y="-360" width="720" height="720" fill="#e9ece5"/>']
  const roadX=[-330,-285,-240,-197,-154,-119,-86,-53,-21,15,48,82,119,162,209,263,320]
  const roadZ=[-330,-274,-225,-181,-140,-104,-70,-39,-5,30,66,107,150,201,258,320]
  const river='M -158 -380 C -112 -244 -170 -151 -136 -70 S -98 58 -130 145 S -102 278 -70 380'
  parts.push(`<path d="${river}" fill="none" stroke="#cadccf" stroke-width="32"/><path d="${river}" fill="none" stroke="#b4ccd0" stroke-width="23"/>`)
  parts.push('<ellipse cx="70" cy="165" rx="38" ry="27" fill="#c7dacb"/><ellipse cx="70" cy="165" rx="31" ry="22" fill="#b8d0d2"/>')
  for(const [x,z,w,h] of parks)parts.push(`<rect x="${x}" y="${z}" width="${w}" height="${h}" rx="12" fill="#cedcc6"/>`)
  for(let i=0;i<roadX.length-1;i++)for(let j=0;j<roadZ.length-1;j++){
    const x=roadX[i]+5,z=roadZ[j]+5,w=roadX[i+1]-x-5,h=roadZ[j+1]-z-5
    const seed=(i*73+j*37)%101
    if(x < -108 && x+w > -150 || parks.some(([px,pz,pw,ph])=>x<px+pw&&x+w>px&&z<pz+ph&&z+h>pz))continue
    parts.push(`<rect x="${x}" y="${z}" width="${w}" height="${h}" rx="2" fill="${seed%3?'#dce1d7':'#e2ded3'}"/>`)
    const cols=w>32?3:2,rows=h>32?3:2
    for(let c=0;c<cols;c++)for(let r=0;r<rows;r++){
      if((seed+c*5+r*3)%7===0)continue
      const bw=w/cols-3,bh=h/rows-3,bx=x+c*w/cols+1,bz=z+r*h/rows+1
      mapBuildings.push({x:bx+bw/2,z:bz+bh/2,w:bw,d:bh,h:1+seed%4*.5})
      parts.push(`<rect x="${bx+.5}" y="${bz+.8}" width="${bw}" height="${bh}" rx=".6" fill="#c9d0c4"/><rect x="${bx}" y="${bz}" width="${bw}" height="${bh}" rx=".6" fill="${seed%2?'#e8e8dd':'#eff0e7'}" stroke="#d3d8cd" stroke-width=".35"/>`)
    }
  }
  const roads=[]
  roadX.forEach((x,i)=>roads.push({d:`M ${x} -360 Q ${x+8} -90 ${x} 40 T ${x+5} 360`,w:i%4===0?5.6:2.8}))
  roadZ.forEach((z,i)=>roads.push({d:`M -360 ${z} Q -100 ${z+9} 45 ${z} T 360 ${z-4}`,w:i%4===0?5.6:2.8}))
  roads.push({d:'M -360 150 Q -110 120 20 -25 T 330 -220',w:7})
  for(const {d,w} of roads)parts.push(`<path d="${d}" fill="none" stroke="#cbd1c5" stroke-width="${w+1.6}"/><path d="${d}" fill="none" stroke="${w>5?'#f5edda':'#fafaf5'}" stroke-width="${w}"/>`)
  parts.push('<g fill="#60745d" font-family="Microsoft YaHei,sans-serif" font-size="5" text-anchor="middle"><text x="-130" y="-66">滨水绿地</text><text x="129" y="59">东部公园</text><text x="64" y="166">南湖</text></g></svg>')
  return parts.join('')
}
export const mapTextureUrl = 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(createMap())
