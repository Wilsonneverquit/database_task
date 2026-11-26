import {Line2} from 'three/addons/lines/Line2.js'
import {LineGeometry} from 'three/addons/lines/LineGeometry.js'
import {LineMaterial} from 'three/addons/lines/LineMaterial.js'

export function createSceneLink(points,{color='#275cba',width=2.5,opacity=.8,dashed=false}={}){
  const geometry=new LineGeometry()
  geometry.setPositions(points.flatMap(p=>[p.x,p.y,p.z]))
  const material=new LineMaterial({color,linewidth:width,transparent:true,opacity,dashed,dashSize:3,gapSize:2,depthWrite:false})
  const line=new Line2(geometry,material)
  line.computeLineDistances()
  line.userData.segments=Math.max(0,points.length-1)
  return line
}
export function revealSceneLink(line,progress){
  line.geometry.instanceCount=Math.ceil(line.userData.segments*Math.max(0,Math.min(1,progress)))
}
