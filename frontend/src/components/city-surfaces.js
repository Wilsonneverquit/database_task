import {landmarkSites,anchoredRiver} from '@/utils/area-landmarks'
// Fictional city cartography. Every footprint, road and tree shares the curved surface.
export const CITY_ANGLE_SCALE=.4
export const cityWarp=(lon,lat)=>[lon+1.8*Math.sin(lat*.065+lon*.035)+.6*Math.sin(lat*.19),lat+1.7*Math.sin(lon*.07-lat*.04)]
export const CITY_BOUNDS={lon:60,lat:42}
const xs=[-60,-49,-39,-30,-22,-14,-6,2,10,19,29,40,50,60]
const ys=[-42,-34,-27,-20,-13,-6,2,10,18,26,34,42]
export const cityRoadLatitudes=ys
export const riverLongitude=lat=>-17+4*Math.sin(lat*.075)+1.8*Math.sin(lat*.21)
export function createCitySurfaces(nodes,{textureSize}={}){
  const sites=landmarkSites(nodes),riverLongitude=anchoredRiver(sites,cityWarp)
  const width=textureSize||(window.innerWidth<700?2048:4096),height=width/2,canvas=()=>{const c=document.createElement('canvas');c.width=width;c.height=height;return c}
  const color=canvas(),detail=canvas(),relief=canvas(),ctx=color.getContext('2d'),ink=detail.getContext('2d')
  const xy=(lon,lat)=>{const [l,t]=cityWarp(lon,lat);return [(l+60)/120*width,(42-t)/84*height]}
  ctx.fillStyle='#c8d6ae';ctx.fillRect(0,0,width,height)
  const blocks=[],buildings=[],trees=[],cars=[]
  const clear=(lon,lat,r=3)=>{const [l,t]=cityWarp(lon,lat);return sites.some(s=>Math.hypot((s.node.cityLon-l)*Math.cos(lat*Math.PI/180),s.node.cityLat-t)<s.radius+.7)||nodes.some(n=>Math.hypot((n.cityLon-l)*Math.cos(lat*Math.PI/180),n.cityLat-t)<r)}
  const diagonal=lon=>lon*.48+5*Math.sin(lon*.06)
  const park=(lon,lat)=>((lon+29)**2/90+(lat-15)**2/55<1)||((lon-16)**2/95+(lat+24)**2/65<1)||((lon-35)**2/100+(lat-27)**2/60<1)
  for(let i=0;i<xs.length-1;i++)for(let j=0;j<ys.length-1;j++){
    const lon=(xs[i]+xs[i+1])/2,lat=(ys[j]+ys[j+1])/2,seed=(i*73+j*37)%101,isPark=park(lon,lat),[x,y]=xy(xs[i]+.5,ys[j+1]-.5),w=(xs[i+1]-xs[i]-1)/120*width,h=(ys[j+1]-ys[j]-1)/84*height
    ctx.fillStyle=isPark?'#9cbd7c':seed%3?'#dedfd1':'#e7e2d3';ctx.beginPath();[[xs[i]+.5,ys[j]+.5],[xs[i+1]-.5,ys[j]+.5],[xs[i+1]-.5,ys[j+1]-.5],[xs[i]+.5,ys[j+1]-.5]].forEach(([l,t],k)=>{const [px,py]=xy(l,t);k?ctx.lineTo(px,py):ctx.moveTo(px,py)});ctx.closePath();ctx.fill();blocks.push({lon,lat,isPark})
    const cols=3+seed%3,rows=2+seed%3
    for(let a=0;a<cols;a++)for(let b=0;b<rows;b++){
      const s=(seed+a*17+b*11)%101,l=xs[i]+1.4+(a+.5)*(xs[i+1]-xs[i]-2.8)/cols+(s%7-3)*.12,t=ys[j]+1.2+(b+.5)*(ys[j+1]-ys[j]-2.4)/rows+(s%9-4)*.09
      if(Math.abs(l-riverLongitude(t))<2.7||Math.abs(t-diagonal(l))<1.1||clear(l,t))continue
      if(isPark){trees.push({lon:l+(s%5-2)*.25,lat:t+(s%7-3)*.2,h:3.5+s%6,r:1.2+s%4*.35});continue}
      if(s%7===0){trees.push({lon:l,lat:t,h:4+s%3,r:1.3});continue}
      const tall=Math.hypot(l-18,t+3)<18
      buildings.push({lon:l,lat:t,w:Math.min(4+s%7,(xs[i+1]-xs[i]-2.8)*4.8/cols*.77),d:Math.min(4+s%6,(ys[j+1]-ys[j]-2.4)*4.8/rows*.77),h:4+s%10+Math.max(0,1-Math.hypot(l-18,t+3)/25)*(7+s%23),yaw:(s%7-3)*.035,shade:s})
      const [bx,by]=xy(l-.6,t+.6);ctx.fillStyle='#acb1a2';ctx.fillRect(bx+3,by+5,16+s%9,11+s%7);ctx.fillStyle='#dfddd1';ctx.fillRect(bx,by,16+s%9,11+s%7)
    }
  }
  function path(points,color,lineWidth,dash=[]){ctx.beginPath();points.forEach(([l,t],i)=>{const [x,y]=xy(l,t);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle=color;ctx.lineWidth=lineWidth*width/4096;ctx.setLineDash(dash.map(v=>v*width/4096));ctx.stroke();ctx.setLineDash([])}
  const river=Array.from({length:181},(_,i)=>{const lat=-45+i*.5;return [riverLongitude(lat),lat]})
  path(river,'#91b27c',145);path(river,'#e1ddbf',93);path(river,'#6bb4c5',79)
  // Fine banks and a second stream add readable landscape scale without external tiles.
  path(river,'#8ac9d5',48)
  for(const [i,lon] of xs.entries()){
    const major=i%4===1,p=Array.from({length:46},(_,k)=>[lon,-45+k*2])
    path(p,'#ede9dd',major?49:32);path(p,'#9ca7a6',major?31:18);if(major)path(p,'#e5d4a0',1.6,[14,11])
    for(let lat=-39;lat<40;lat+=5)if(Math.abs(lon-riverLongitude(lat))>3&&!clear(lon+1,lat,2))trees.push({lon:lon+1.1,lat,h:4,r:1.1})
  }
  for(const [j,lat] of ys.entries()){
    const major=j%4===1,p=Array.from({length:64},(_,k)=>[-63+k*2,lat])
    path(p,'#ede9dd',major?48:30);path(p,'#9ca7a6',major?30:17);if(major)path(p,'#e7dfc8',1.3,[12,10])
    // Zebra crossings are aligned with the same road intersections.
    for(const lon of xs.slice(1,-1)){const [x,y]=xy(lon+.55,lat);ctx.fillStyle='#f5f1e5';for(let k=0;k<5;k++)ctx.fillRect(x+k*3,y-9,1.6,18)}
  }
  const avenue=Array.from({length:61},(_,i)=>{const l=-60+i*2;return [l,diagonal(l)]});path(avenue,'#ede9dd',43);path(avenue,'#9ca7a6',25);path(avenue,'#f5ebc7',1.5,[13,10])
  for(let lat=-39;lat<=39;lat+=1.8)for(const side of [-1,1]){const lon=riverLongitude(lat)+side*(2.4+.4*Math.sin(lat));if(!clear(lon,lat))trees.push({lon,lat,h:4+Math.abs(Math.round(lat))%4,r:1.3})}
  for(let i=0;i<xs.length;i+=2)for(let j=1;j<ys.length-1;j+=3){const lon=xs[i]+.16,lat=ys[j]+2;if(!clear(lon,lat,2))cars.push({lon,lat,shade:i+j})}
  // Replace the generic street fabric at each regional landmark, with soft irregular lots.
  for(const site of sites){
    ctx.beginPath()
    for(let i=0;i<=20;i++){const t=i/20*Math.PI*2,r=site.radius*(1+.06*Math.sin(t*3));const x=(site.node.cityLon+Math.cos(t)*r+60)/120*width,y=(42-site.node.cityLat-Math.sin(t)*r)/84*height;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}
    ctx.fillStyle=site.profile.ground;ctx.globalAlpha=.94;ctx.fill();ctx.globalAlpha=1
  }
  // The river is anchored to the riverside district and remains continuous across the map.
  path(river,'#91b27c',145);path(river,'#e1ddbf',93);path(river,'#6bb4c5',79);path(river,'#8ac9d5',48)
  // Low-contrast parcel detail can be toggled independently of the road bed.
  ink.strokeStyle='#8e9d8190';ink.lineWidth=1
  for(const b of blocks){const [x,y]=xy(b.lon,b.lat);ink.strokeRect(x-30,y-25,60,50)}
  // Actual local surface relief: pavement joints, verge edges and roof footprints.
  const bump=relief.getContext('2d');bump.fillStyle='#808080';bump.fillRect(0,0,width,height)
  for(const b of blocks){
    const [x,y]=xy(b.lon,b.lat),step=Math.max(3,width/512)
    bump.strokeStyle=b.isPark?'#7b7b7b':'#929292';bump.lineWidth=Math.max(1,width/2048)
    for(let i=-24;i<25;i+=step){bump.beginPath();bump.moveTo(x+i,y-20);bump.lineTo(x+i,y+20);bump.stroke()}
    ink.strokeStyle=b.isPark?'#75966140':'#7b858540';ink.lineWidth=Math.max(.5,width/4096)
    for(let i=-24;i<25;i+=step*2){ink.beginPath();ink.moveTo(x-24,y+i);ink.lineTo(x+24,y+i);ink.stroke()}
  }
  return {color,detail,relief,buildings,sites,riverLongitude,trees:trees.filter(t=>{const [l,p]=cityWarp(t.lon,t.lat);return Math.abs(l)<59&&Math.abs(p)<41}),cars}
}
