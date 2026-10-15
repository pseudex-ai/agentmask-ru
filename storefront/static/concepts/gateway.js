/* Fixed illustrative data, never a detector or an executing tool loop.
 * No fetch/LLM/provider/clipboard call. Only one local, user-started cycle.
 * A datum changes identity while occluded INSIDE the gateway, not on either
 * recipient. Context structure/order id stays unchanged on both legs. */
(function(){
  'use strict';
  const scene=document.querySelector('.gateway-scene'),core=document.querySelector('.gateway-core');
  const parcel=scene.querySelector('.data-parcel'),svg=scene.querySelector('svg.circuit');
  const name=scene.querySelector('[data-parcel-name]'),email=scene.querySelector('[data-parcel-email]');
  const status=scene.querySelector('.scene-status'),action=core.querySelector('.core-action');
  const nodes=Object.fromEntries(['input','model','call','tool'].map(k=>[k,scene.querySelector('[data-node="'+k+'"]')]));
  const reduce=matchMedia('(prefers-reduced-motion: reduce)'),narrow=matchMedia('(max-width: 800px)');
  let busy=false,epoch=0,active=null,points;
  function rect(el){const s=scene.getBoundingClientRect(),r=el.getBoundingClientRect();return {x:r.left-s.left,y:r.top-s.top,w:r.width,h:r.height};}
  function geometry(){
    const input=rect(nodes.input),model=rect(nodes.model),call=rect(nodes.call),tool=rect(nodes.tool),gate=rect(core);
    svg.setAttribute('viewBox','0 0 '+scene.clientWidth+' '+scene.clientHeight);
    const y1=input.y+input.h*.62,y2=model.y+model.h*.64;
    const y3=call.y+call.h*.6,y4=tool.y+tool.h*.6;
    points={forward:[{x:input.x+input.w-65,y:y1},{x:gate.x+gate.w/2,y:(y1+y2)/2},{x:model.x+65,y:y2}],
      return:[{x:call.x+65,y:y3},{x:gate.x+gate.w/2,y:(y3+y4)/2},{x:tool.x+tool.w-65,y:y4}]};
    Object.entries(points).forEach(([key,p])=>svg.querySelector('[data-route="'+key+'"]').setAttribute('d','M'+p[0].x+','+p[0].y+' L'+p[1].x+','+p[1].y+' L'+p[2].x+','+p[2].y));
    for(const [cls,y]of [['.top-direction',points.forward[1].y],['.bottom-direction',points.return[1].y]]){
      const el=core.querySelector(cls);el.style.top=(y-gate.y-15)+'px';el.style.bottom='auto';
    }
  }
  function identity(protectedValue){
    name.textContent=protectedValue?'Елена Волкова':'Анна Орлова';email.textContent=protectedValue?'elena@client.example':'anna@client.example';
    parcel.classList.toggle('is-protected',protectedValue);parcel.classList.toggle('is-original',!protectedValue);
  }
  function transform(p){return 'translate3d('+(p.x-parcel.offsetWidth/2)+'px,'+(p.y-parcel.offsetHeight/2)+'px,0)';}
  async function fly(a,b){
    parcel.style.transform=transform(a);
    const anim=parcel.animate([{transform:transform(a)},{transform:transform(b)}],{duration:900,easing:'linear',fill:'forwards'});active=anim;
    await anim.finished;parcel.style.transform=transform(b);anim.cancel();if(active===anim)active=null;
  }
  function receive(node){node.classList.remove('is-waiting');node.classList.add('is-received');}
  function complete(){
    busy=false;core.setAttribute('aria-busy','false');scene.dataset.phase='complete';parcel.style.visibility='hidden';
    Object.values(nodes).forEach(n=>n.classList.remove('is-waiting'));
    status.textContent='Модель работала с подменами. Разрешённый инструмент получил оригиналы.';action.textContent='ПОВТОРИТЬ ЦИКЛ ↗';
  }
  async function run(){
    if(busy)return;
    if(reduce.matches||narrow.matches){complete();return;}
    busy=true;const token=++epoch;geometry();core.setAttribute('aria-busy','true');
    Object.values(nodes).forEach(n=>n.classList.remove('is-received'));
    [nodes.model,nodes.call,nodes.tool].forEach(n=>n.classList.add('is-waiting'));
    action.textContent='КОНТЕКСТ → МОДЕЛЬ';status.textContent='Чувствительное значение меняется только внутри шлюза.';scene.dataset.phase='forward';
    identity(false);parcel.style.visibility='visible';
    try{
      const f=points.forward;await fly(f[0],f[1]);if(token!==epoch)return;
      identity(true);await fly(f[1],f[2]);if(token!==epoch)return;
      parcel.style.visibility='hidden';receive(nodes.model);receive(nodes.call);
      status.textContent='Модель выбрала действие. Подмена возвращается в локальный контур.';action.textContent='ИНСТРУМЕНТ ← ОРИГИНАЛ';scene.dataset.phase='return';
      identity(true);parcel.style.visibility='visible';
      const r=points.return;await fly(r[0],r[1]);if(token!==epoch)return;
      identity(false);await fly(r[1],r[2]);if(token!==epoch)return;
      receive(nodes.tool);complete();
    }catch(_){if(token===epoch)complete();}
  }
  function cancel(){epoch++;if(active){active.cancel();active=null;}if(busy)complete();geometry();}
  core.addEventListener('click',run);
  addEventListener('resize',cancel,{passive:true});reduce.addEventListener('change',cancel);narrow.addEventListener('change',cancel);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});addEventListener('pagehide',cancel);
  geometry();if(document.fonts)document.fonts.ready.then(geometry);
}());
