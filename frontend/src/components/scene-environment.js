import * as THREE from 'three'

// Locally generated daylight lighting; no remote HDR or map service dependency.
export function daylightEnvironment(renderer){
  const canvas=document.createElement('canvas');canvas.width=256;canvas.height=128
  const context=canvas.getContext('2d'),sky=context.createLinearGradient(0,0,0,128)
  sky.addColorStop(0,'#8daec6');sky.addColorStop(.46,'#e7f1ee');sky.addColorStop(.55,'#e0dbc9');sky.addColorStop(1,'#9ca38b')
  context.fillStyle=sky;context.fillRect(0,0,256,128)
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.mapping=THREE.EquirectangularReflectionMapping
  const generator=new THREE.PMREMGenerator(renderer),target=generator.fromEquirectangular(texture)
  generator.dispose();texture.dispose()
  return target
}
