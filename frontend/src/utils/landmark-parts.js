// Shared local metre-scale plans. The origin is the unobstructed regional landing plaza.
export function landmarkParts(kind){
  const boxes=[],roofs=[],trees=[],patches=[],paths=[],rings=[]
  const box=(x,z,w,d,h,color='#e7deca',base=0,glass=false)=>boxes.push({x,z,w,d,h,color,base,glass})
  const house=(x,z,w,d,h,color='#e8d6bd')=>{box(x,z,w,d,h,color);roofs.push({x,z,w:w+1,d:d+1,h:2.4,base:h,color:'#777c79'})}
  const tree=(x,z,h=5)=>trees.push({x,z,h,r:1.6})
  const patch=(x,z,w,d,color)=>patches.push({x,z,w,d,color})
  const path=(points,width=3,color='#c6c9be',dashed=false)=>paths.push({points,width,color,dashed})
  const rowTrees=(x,z,dx,dz,count)=>{for(let i=0;i<count;i++)tree(x+i*dx,z+i*dz,4+i%3)}
  if(kind==='business'){
    box(-15,-12,10,10,44,'#9fbcc5',0,true);box(1,-19,10,9,34,'#b8ced1',0,true);box(17,-9,9,12,51,'#8aaebc',0,true);box(15,14,13,9,20,'#d4ded7',0,true)
    for(const [x,z] of [[-15,-12],[1,-19],[17,-9]])box(x,z,11,11,2,'#d7dcd5')
    patch(-5,7,20,16,'#d5dcd7');path([[-24,24],[0,18],[26,23]],4);rowTrees(-23,6,0,7,3)
  }else if(kind==='oldstreet'){
    for(const side of [-1,1])for(let i=0;i<5;i++){const z=-19+i*9,x=side*(11+(i%2)*.6);house(x,z,8,8,6+i%3);box(x-side*4.1,z,1.3,6,1,'#c99770',4)}
    path([[0,-28],[1,-12],[-1,9],[0,28]],5,'#c6c1af');rowTrees(-23,-17,0,12,4)
  }else if(kind==='residential'){
    for(const [x,z,h] of [[-15,-16,23],[13,-17,28],[-15,15,21],[16,13,25]])box(x,z,10,8,h,'#e1dfd2')
    patch(0,0,18,18,'#abd091');path([[-25,0],[0,0],[25,1]],3);path([[0,-25],[0,25]],3);box(-4,26,2,2,4,'#e5dfce');box(4,26,2,2,4,'#e5dfce');box(0,26,10,2,1,'#8faaa3',4)
    for(const [x,z] of [[-6,-7],[7,-6],[-7,7],[7,7]])tree(x,z)
  }else if(kind==='station'){
    box(0,-16,38,13,11,'#c8d9db',0,true);box(0,-16,42,16,1.2,'#e6e8e1',11)
    for(const x of [-18,-10,0,10,18])box(x,-8,1,6,6,'#eef0e8')
    box(0,-8,43,6,1,'#d2dfe0',6)
    patch(0,10,42,20,'#d7dcd5');path([[-28,24],[-9,20],[12,20],[29,24]],5,'#a2aeae',true)
    for(const z of [-26,-23])path([[-30,z],[30,z]],.5,'#687e83');rowTrees(-25,0,0,8,3)
  }else if(kind==='campus'){
    // An oval running track and football pitch remain recognisable at overview scale.
    rings.push({x:-10,z:-5,a:13,b:23,innerA:10,innerB:20,color:'#c98068'})
    patch(-10,-5,18,34,'#87b46d');path([[-19,-5],[-1,-5]],.35,'#f0f3dc');rings.push({x:-10,z:-5,a:3.5,b:3.5,innerA:3.2,innerB:3.2,color:'#eef3db'})
    for(const z of [-18,0,18])box(17,z,11,10,11+Math.abs(z)/6,'#e9dec3')
    // Move the regional marker to the open campus approach, not into a building.
    patch(0,0,9,11,'#dce4d0');path([[0,28],[0,10],[3,-16]],3);rowTrees(27,-23,0,9,6)
  }else if(kind==='riverside'){
    path([[-8,-29],[-9,-15],[-8,0],[-10,16],[-8,29]],4,'#dfceac')
    for(const z of [-19,0,19]){patch(8,z,13,11,'#b5ce93');tree(17,z,6)}
    box(-13,10,13,5,1,'#b7a483',.3);box(12,-17,10,8,4,'#e4d8bd');roofs.push({x:12,z:-17,w:12,d:10,h:3,base:4,color:'#8caaa0'})
    path([[0,0],[-8,0]],3,'#dfceac');rowTrees(1,-26,0,10,6)
  }else if(kind==='industrial'){
    for(const [x,z] of [[-14,-15],[11,-15],[-14,14]]){
      box(x,z,20,15,8,'#c9d6d5')
      for(let k=0;k<3;k++)roofs.push({x:x-6+k*6,z,w:6.5,d:16,h:3,base:8,color:'#879da5'})
    }
    patch(14,13,18,18,'#bfcac6');for(let i=0;i<4;i++)box(9+i*4,17,3,9,3,['#a8b8b6','#839eae'][i%2]);box(24,-23,2,2,19,'#c4bcb0')
    path([[-28,0],[0,0],[28,1]],5,'#a9b5b3')
  }else if(kind==='highway'){
    path([[-16,-32],[-15,-13],[-15,10],[-16,32]],11,'#929f9f');path([[-16,-32],[-15,32]],.55,'#e6ddbc',true)
    const loop=[];for(let i=0;i<=32;i++){const t=i/32*Math.PI*1.65-.7;loop.push([6+17*Math.cos(t),1+18*Math.sin(t)])}path(loop,5,'#9eaaaa');path([[-15,-9],[-3,-20],[12,-16]],5,'#9eaaaa')
    box(12,17,2,2,6,'#d2dcd8');box(23,17,2,2,6,'#d2dcd8');box(17.5,17,15,4,1.3,'#b6cfd0',6)
    rowTrees(-25,-25,0,10,6);patch(0,0,10,10,'#d7e1c7')
  }else if(kind==='community'){
    for(const [x,z] of [[-17,-17],[-4,-21],[13,-18],[-19,0],[-17,17],[15,17]])house(x,z,9,8,6)
    patch(10,1,18,19,'#a9ca85');path([[-25,5],[0,6],[25,5]],3);box(6,-16,9,7,5,'#e1d4bc');rowTrees(17,-6,-1,7,4)
  }else if(kind==='commercial'){
    box(-14,-13,20,15,12,'#d5d3c5');box(14,-13,18,15,9,'#e7dac2')
    for(const x of [-21,-11,11,21]){box(x,14,8,10,7,'#e3d6bd');box(x,8.6,7,1.3,1.5,['#9cbbb0','#bd9675'][Math.abs(x)%2],4)}
    path([[0,-27],[0,0],[0,28]],7,'#d8cfb8');rowTrees(-27,2,0,8,3);rowTrees(27,2,0,8,3)
  }else if(kind==='nightmarket'){
    for(const side of [-1,1])for(let i=0;i<5;i++){
      const x=side*10,z=-20+i*10,color=['#b96b48','#6d9a70','#c9a14f','#a87766','#6d9baf'][i]
      box(x,z,5.8,5.7,1,'#e2d8ba');box(x,z,6.8,6.7,.7,color,4);roofs.push({x,z,w:6.8,d:6.7,h:1.6,base:4,color})
      for(const dx of [-2.5,2.5])box(x+dx,z, .22,5,4,'#d1c8b3')
    }
    path([[0,-30],[0,30]],7,'#e0d4b7');box(-23,-10,9,18,7,'#decfb9');box(23,10,9,18,7,'#decfb9');rowTrees(23,-23,0,8,3)
  }else if(kind==='rural'){
    for(const [x,z] of [[-18,-18],[-4,-21],[14,-15],[-19,0]])house(x,z,7,7,4.5,'#e6d9be')
    patch(-12,17,19,17,'#b8cf7d');patch(12,12,20,26,'#d2d28d');patch(20,-6,12,9,'#a8c581')
    for(let i=0;i<6;i++)path([[-20,10+i*2.5],[-4,10+i*2.5]],.6,'#8eae62')
    for(let i=0;i<7;i++)path([[5+i*2,1],[5+i*2,23]],.6,'#b4b567')
    path([[-28,-7],[-9,-5],[0,0],[4,28]],3,'#cbbf99');rowTrees(-27,-25,0,10,6)
  }
  return {boxes,roofs,trees:trees.filter(t=>Math.hypot(t.x,t.z)>9),patches,paths,rings}
}
