// Native fullscreen when available; the same mounted map uses viewport fullscreen otherwise.
export function createMapFullscreen({getElement,onChange,document:doc=globalThis.document}){
  let active=false,native=false,pending=false,disposed=false,overflow=''
  function apply(value,isNative=false){
    if(disposed)return
    const changed=active!==value
    if(changed){if(value){overflow=doc.body.style.overflow;doc.body.style.overflow='hidden'}else doc.body.style.overflow=overflow}
    active=value;native=value&&isNative;onChange({active,native,changed})
  }
  function change(){const element=getElement();if(element&&doc.fullscreenElement===element)apply(true,true);else if(native)apply(false)}
  function key(event){if(event.key==='Escape'&&active&&!native){event.preventDefault();apply(false)}}
  doc.addEventListener('fullscreenchange',change);doc.addEventListener('keydown',key)
  return {
    async toggle(){
      if(pending||disposed)return
      pending=true
      try{
        if(active){if(doc.fullscreenElement===getElement())await doc.exitFullscreen();apply(false)}
        else{
          const element=getElement();if(!element)return
          let entered=false,rejected=false
          try{if(!element.requestFullscreen)throw new Error('unavailable');await element.requestFullscreen();entered=doc.fullscreenElement===element}catch{rejected=true}
          if(disposed){if(entered)await doc.exitFullscreen();return}
          // A successful request followed by an immediate user exit must stay exited.
          apply(entered||rejected,entered)
        }
      }finally{pending=false}
    },
    dispose(){disposed=true;doc.removeEventListener('fullscreenchange',change);doc.removeEventListener('keydown',key);if(active)doc.body.style.overflow=overflow;const element=getElement();if(element&&doc.fullscreenElement===element&&doc.exitFullscreen)doc.exitFullscreen().catch(()=>{})},
  }
}
