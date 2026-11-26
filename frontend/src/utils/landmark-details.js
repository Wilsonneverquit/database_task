// Physical street furniture and close-range district detail, in the landmark's local coordinates.
export function landmarkDetails(kind,plan){
  const fixtures=[],fine=[],paths=[],signs=[],poles=[]
  const box=(x,z,w,d,h,color,base=0,level=1)=> (level===2?fine:fixtures).push({x,z,w,d,h,color,base})
  const line=(points,width=.14,color='#f3f1db')=>paths.push({points,width,color})
  const bench=(x,z)=>{box(x,z,3.6,1,.25,'#a88b65',.8);for(const dx of [-1.3,1.3])box(x+dx,z,.22,.65,.8,'#657b79');box(x,z+.5,3.6,.18,.7,'#ac916a',.9)}
  const lamp=(x,z)=>{poles.push({x,z,h:7.5,r:.1,color:'#687e7a'});box(x+.7,z,1.8,.5,.2,'#cad7cf',7.4)}
  for(const b of plan.boxes.filter(b=>b.h>=6&&b.w>=7&&b.d>=7)){
    // Roof parapets, ventilation equipment, entry doors and balconies are actual geometry.
    box(b.x,b.z-b.d/2+.18,b.w,.32,.65,'#c4cec5',b.base+b.h,2)
    box(b.x-b.w/2+.18,b.z,.32,b.d,.65,'#c4cec5',b.base+b.h,2)
    box(b.x+b.w*.2,b.z,Math.min(2.5,b.w*.25),Math.min(2,b.d*.25),.8,'#a9b9b3',b.base+b.h,2)
    box(b.x,b.z+b.d/2+.08,Math.min(2.8,b.w*.25),.15,2.6,'#516e78',b.base,2)
    if(['residential','community'].includes(kind))for(let y=3;y<b.h-1;y+=3.1)for(const x of [-1,1]){
      box(b.x+x*b.w*.25,b.z+b.d/2+.45,b.w*.27,.85,.2,'#d6dbd1',b.base+y,2)
      box(b.x+x*b.w*.25,b.z+b.d/2+.85,b.w*.27,.1,.65,'#91aaa5',b.base+y+.2,2)
    }
    if(kind==='business')for(let y=4;y<b.h;y+=4)box(b.x,b.z+b.d/2+.08,b.w,.12,.15,'#d6e3df',y,2)
  }
  if(kind==='campus'){
    for(let lane=0;lane<4;lane++){
      const pts=[];for(let i=0;i<=100;i++){const a=i/100*Math.PI*2;pts.push([-10+Math.cos(a)*(10.6+lane*.7),-5+Math.sin(a)*(20.6+lane*.7)])}line(pts,.1,'#f4e6d2')
    }
    line([[-18,-21],[-2,-21],[-2,11],[-18,11],[-18,-21]],.18)
    line([[-18,-5],[-2,-5]],.18)
    for(const z of [-21,11]){box(-10,z,5,.18,.16,'#e8ede0',1.92);for(const x of [-12.5,-7.5])box(x,z,.18,.18,2,'#e8ede0')}
    for(let i=0;i<3;i++)box(-25,-10+i*5,3,4,.5+i*.2,'#c6c5b8')
    signs.push({x:17,z:6,y:8,text:'教学楼',color:'#3b6863'})
  }else if(kind==='nightmarket'){
    for(const side of [-1,1])for(let i=0;i<5;i++){
      const x=side*10,z=-20+i*10
      box(x-side*2.1,z,.75,4,1.1,'#b49470');box(x-side*2.1,z,1,4.4,.14,'#e7ddc5',1.1)
      for(let j=0;j<3;j++){box(x-side*2.1,z-1.3+j*1.3,.45,.55,.22,['#bd8054','#92ad6d','#d5b671'][j],1.25,2)}
      for(const dx of [-1.7,0,1.7])box(x+dx,z, .7,6.5,.07,'#f6ebce',4.76,2)
      if(i%2===0)signs.push({x,z:z-3.1,y:3.2,text:['小食','茶饮','鲜果'][i/2],color:'#84614b'})
    }
    lamp(-5,-27);lamp(5,27);bench(-21,18)
  }else if(kind==='oldstreet'||kind==='commercial'){
    for(const b of plan.boxes.filter(b=>b.h>=6&&b.w>=7)){
      signs.push({x:b.x,z:b.z+b.d/2+.2,y:3.3,text:kind==='oldstreet'?'街坊餐饮':'沿街商铺',color:kind==='oldstreet'?'#9c6a48':'#4d7d77'})
      for(let i=0;i<3;i++)box(b.x-b.w*.3+i*b.w*.3,b.z+b.d/2+.1,b.w*.2,.12,2,'#7f9e9c',.5,2)
    }
    lamp(-3,-23);lamp(3,23);bench(-23,3)
  }else if(kind==='station'){
    for(const z of [-26,-23]){
      line([[-31,z-.6],[31,z-.6]],.16,'#6e8586');line([[-31,z+.6],[31,z+.6]],.16,'#6e8586')
      for(let x=-28;x<29;x+=2)line([[x,z-1],[x,z+1]],.25,'#a1aaa1')
    }
    for(let i=0;i<4;i++){box(-16+i*10,-24.5,9,2.6,2.6,'#e7eee4');box(-16+i*10,-23.15,7,.08,.8,'#668995',1.3,2)}
    for(const x of [-20,-10,10,20]){line([[x,17],[x,23]],.12,'#f2edcb');box(x,22,3,6,2,'#8faeb5')}
    signs.push({x:0,z:-8.8,y:8.6,text:'南站',color:'#4b727e'});lamp(-24,15);lamp(24,15)
  }else if(kind==='industrial'){
    for(const b of plan.boxes.filter(b=>b.w===20)){
      for(const x of [-5,5]){box(b.x+x,b.z+b.d/2+.08,6,.18,4.4,'#7c9d9f');for(let y=1;y<4;y+=.6)box(b.x+x,b.z+b.d/2+.2,5.9,.08,.07,'#bdc9c4',y,2)}
      signs.push({x:b.x,z:b.z+b.d/2+.3,y:6,text:'厂房',color:'#54757f'})
    }
    for(let i=0;i<4;i++)line([[7+i*4,7],[7+i*4,20]],.18,'#e4d49d')
    box(23,8,3.2,5.5,3,'#d0b77b');lamp(1,-26)
  }else if(kind==='highway'){
    for(const x of [-18,-12])line([[x,-31],[x,31]],.18,'#e9e7cc')
    for(let z=-28;z<30;z+=3){box(-22,z,.25,2.7,.25,'#c1ccc6',1);box(-8.8,z,.25,2.7,.25,'#c1ccc6',1)}
    signs.push({x:17.5,z:16.7,y:6.8,text:'高速出口',color:'#45856c'})
    for(const z of [-23,0,23])lamp(-24,z)
    box(-18,-7,2.4,5,1.8,'#f3ecdf');box(-12,22,2.4,4.4,1.8,'#8ba9b6')
  }else if(kind==='riverside'){
    for(let z=-27;z<29;z+=3){poles.push({x:-13,z,h:1.2,r:.08,color:'#73938d'});box(-13,z,.12,3,.12,'#8aa49b',1.2,2)}
    for(const z of [-18,1,20])bench(9,z)
    lamp(-5,-22);lamp(-5,22);signs.push({x:12,z:-12.7,y:3.3,text:'滨水驿站',color:'#648b78'})
  }else if(kind==='residential'||kind==='community'){
    bench(10,9);bench(-7,12);lamp(-5,-19);lamp(5,20)
    if(kind==='community'){
      line([[3,-6],[17,-6],[17,8],[3,8],[3,-6]],.2,'#f5efd5');line([[3,1],[17,1]],.18,'#f5efd5')
      poles.push({x:10,z:-5,h:3.4,r:.1,color:'#759388'});box(10,-5,2.7,.16,1.4,'#d2e0d0',2.3)
    }
  }else if(kind==='rural'){
    for(let x=-20;x<-4;x+=2)for(let z=12;z<24;z+=3)box(x,z,.5,1.3,.35,'#91b061',0,2)
    line([[-25,8],[-22,28],[22,27]],.7,'#94b8af');bench(-4,7)
    signs.push({x:-4,z:-17,y:2.8,text:'乡间小店',color:'#8f8361'})
  }else if(kind==='business'){
    bench(-12,13);bench(-12,19);lamp(-24,-20);lamp(25,20)
    signs.push({x:1,z:-14.2,y:8,text:'商务中心',color:'#447383'})
  }
  return {fixtures,fine,paths,signs,poles}
}
