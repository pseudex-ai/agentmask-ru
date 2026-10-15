/* A real, persistent stack, not a content swap in one window. All 18 public
 * fixture sheets (3 existing orders x 6 phases) are built once. The front sheet
 * follows a real pointer grab/throw in any direction and returns behind the queue. No clones,
 * fades, model/tool calls, customer input or fake empty backing screens. */
(function () {
  'use strict';
  const stage=document.getElementById('hero-dialog'),panel=document.getElementById('hero-panel');
  if(!stage||!panel||typeof HERO_CASES==='undefined')return;
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  let cursor=media.matches?5:0,shown=cursor,focusAfter=false;
  let animations=[],motion=0,drag=null,dragFrame=0,suppressUntil=0,cancelledPointer=-1;
  panel.classList.add('hero-stack-shell');stage.classList.add('hero-deck-stage','hero-real-stack');
  const prose=(text,cls)=>node('p',cls||'hero-sheet-note',text);
  const values=ex=>ex.text.filter(p=>p.length>1).map(p=>p[1]).join('\n');
  function message(ex,phase){
    const text=node('div','hero-sheet-message');
    ex.text.forEach(([real,fake])=>{
      if(!fake){text.appendChild(document.createTextNode(real));return;}
      const token=heroToken(real,fake);
      if(phase>=2)token.classList.add('is-found');if(phase>=3)token.classList.add('is-swapped');
      token.firstElementChild.setAttribute('aria-hidden',String(phase>=3));
      token.lastElementChild.setAttribute('aria-hidden',String(phase<3));
      text.appendChild(token);
    });return text;
  }
  function build(order,phase){
    const ex=HERO_CASES[order],card=node('article','hero-stack-card'),body=node('div','hero-deck-sheet');
    card.setAttribute('role','button');card.setAttribute('aria-describedby','hero-stack-help');
    card.dataset.orderSheet=String(phase);card.dataset.orderCase=String(order);
    card.dataset.cardUid='order-'+order+'-phase-'+phase;
    const tag=node('div','hero-sheet-tag');tag.dataset.sheetGrip='';
    tag.append(node('span','',['В ВАШЕМ КОНТУРЕ','ОБНАРУЖЕНИЕ','ПРАВДОПОДОБНАЯ ПОДМЕНА','КОНТЕКСТ МОДЕЛИ','ВЫЗОВ ВАШЕЙ ФУНКЦИИ','ПОЛНЫЙ ЦИКЛ'][phase-1]),node('span','',String(phase).padStart(2,'0')+' / 06 ⋮⋮'));
    body.append(tag,node('h3','hero-sheet-title',['Клиент пишет как привык.','Находим чувствительные значения.','Меняем личность. Не смысл.','Модель решает задачу.','Функция получает оригиналы.','Задача выполнена.'][phase-1]));
    if(phase<=3){
      body.append(node('div','hero-sheet-source',ex.source),message(ex,phase),prose([
        'Переписка остаётся в вашем контуре. До обращения к модели её проверяет Pseudex.',
        'Имена, адреса и контакты отмечены в контексте сообщения — не вырезаны вместе со смыслом.',
        'Род, падеж и формат сохраняются. Модель читает обычное сообщение, но не настоящие значения.'
      ][phase-1]));
    }else if(phase===4){
      const context=node('div','hero-sheet-context');context.append(node('div','hero-sheet-source','ЧТО ВИДИТ МОДЕЛЬ'),node('pre','',values(ex)));
      body.append(context,node('div','hero-sheet-source','ЧТО НУЖНО СДЕЛАТЬ'),prose(ex.decision,'hero-sheet-decision'),prose('Для решения задачи модели достаточно подмен. Доступ к оригиналам ей не требуется.'));
    }else if(phase===5){
      body.append(node('div','hero-sheet-source',ex.system),heroRecord(ex.record),prose('Модель передала подмены. Перед разрешённым вызовом инструмента Pseudex вернул настоящие значения.'));
    }else{
      const compare=node('div','hero-sheet-compare'),model=node('div','hero-sheet-side'),local=node('div','hero-sheet-side hero-sheet-side-local');
      model.append(node('div','hero-sheet-source','МОДЕЛЬ · ПОДМЕНЫ'),node('pre','',values(ex)));
      local.append(node('div','hero-sheet-source','ИНСТРУМЕНТ · ОРИГИНАЛЫ'),heroRecord(ex.record));
      compare.append(model,local);body.append(compare,prose(ex.done));
    }
    card.appendChild(body);return card;
  }
  const cards=HERO_CASES.flatMap((_,i)=>Array.from({length:6},(_,p)=>build(i,p+1)));
  const help=node('span','hero-stack-help','Потяните лист в любую сторону и отпустите. Малый жест возвращает его на место. На телефоне зажимайте верхнюю кромку для вертикального жеста. Enter, пробел и стрелка вправо — вперёд, стрелка влево — назад.');
  help.id='hero-stack-help';stage.replaceChildren(...cards,help);
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const depth=(i,front)=>(i-front+cards.length)%cards.length;
  function position(n){
    if(n===0)return 'translate3d(0,0,0) rotateZ(0deg) scale(1)';
    const d=Math.min(n,2);return 'translate3d('+(d===1?11:-12)+'px,'+(-d*27)+'px,'+(-Math.min(n,8)*34)+'px) rotateZ('+(d===1?2.2:-2.5)+'deg) scale('+(1-d*.016)+')';
  }
  function place(){
    cards.forEach((card,i)=>{const n=depth(i,cursor);card.style.transform=position(n);card.style.zIndex='auto';card.style.visibility=n<3?'visible':'hidden';card.classList.toggle('is-front',n===0);card.classList.remove('is-grabbed');card.dataset.stackDepth=String(n);card.inert=n!==0;card.tabIndex=n===0?0:-1;card.setAttribute('aria-hidden',String(n!==0));card.setAttribute('aria-disabled','false');});
  }
  function paint(){panel.dataset.heroCurrentPhase=String(cursor%6+1);panel.dataset.heroCase=String(Math.floor(cursor/6));}
  function release(g){try{if(g.card.hasPointerCapture(g.id))g.card.releasePointerCapture(g.id);}catch(_){}}
  function stopMotion(){const g=drag;drag=null;if(g){if(g.moved)cancelledPointer=g.id;release(g);}cancelAnimationFrame(dragFrame);dragFrame=0;motion++;animations.forEach(a=>a.cancel());animations=[];stage.classList.remove('is-dealing','is-dragging');place();}
  function focusFront(){if(focusAfter)cards[cursor].focus({preventScroll:true});focusAfter=false;if(window.__landingEdge)window.__landingEdge.refresh();}
  function render(turn,gesture){
    const previous=shown;shown=cursor;motion++;animations.forEach(a=>a.cancel());animations=[];
    const from=cards.map(c=>getComputedStyle(c).transform);place();paint();
    if(!turn||previous===cursor||media.matches||typeof cards[0].animate!=='function'){stage.classList.remove('is-dealing');focusFront();return;}
    stage.classList.add('is-dealing');cards[cursor].setAttribute('aria-disabled','true');
    const token=motion,out=cards[previous];
    const x=gesture?gesture.x:0,y=gesture?gesture.y:Math.min(120,out.offsetHeight*.3);
    const rx=gesture?gesture.rx:-8,ry=gesture?gesture.ry:0,rz=gesture?gesture.rz:2;
    const end='translate3d('+x+'px,'+y+'px,36px) rotateX('+rx+'deg) rotateY('+ry+'deg) rotateZ('+rz+'deg) scale(.99)';
    out.style.visibility='visible';out.inert=true;out.setAttribute('aria-hidden','true');
    cards.forEach((card,i)=>{if(i!==previous)card.style.transform=from[i];});
    const leave=out.animate([{transform:from[previous]},{transform:end}],{duration:gesture?gesture.duration:330,easing:'cubic-bezier(.2,.65,.3,1)',fill:'forwards'});animations.push(leave);
    (async()=>{try{
      await leave.finished;if(token!==motion)return;leave.cancel();
      cards.forEach((card,i)=>{if(i===previous)return;const start=card.style.transform,target=position(depth(i,cursor));card.style.transform=target;if(depth(i,cursor)<3)animations.push(card.animate([{transform:start},{transform:target}],{duration:430,easing:'cubic-bezier(.3,0,.2,1)'}));});
      const back=out.animate([{transform:end},{transform:'translate3d('+(x*.76)+'px,'+(y*.76)+'px,-135px) rotateX('+(rx*.5)+'deg) rotateY('+(ry*.5)+'deg) rotateZ('+(rz*.5)+'deg) scale(.98)',offset:.43},{transform:position(depth(previous,cursor))}],{duration:650,easing:'cubic-bezier(.3,0,.2,1)',fill:'forwards'});animations.push(back);await back.finished;
    }catch(_){/* A cancel/media change owns final placement. */}finally{if(token===motion){animations.forEach(a=>a.cancel());animations=[];place();stage.classList.remove('is-dealing');focusFront();}}})();
  }
  function advance(delta,keyboard,gesture){if(stage.classList.contains('is-dealing')||drag)return;focusAfter=keyboard||document.activeElement===cards[cursor];cursor=(cursor+delta+cards.length)%cards.length;render(true,gesture);}
  function dragPose(g){const distance=Math.hypot(g.x,g.y),z=media.matches?0:Math.min(16,distance*.3);return 'translate3d('+g.x.toFixed(2)+'px,'+g.y.toFixed(2)+'px,'+z+'px) rotateX('+(media.matches?0:clamp(-g.y/35,-6,6))+'deg) rotateY('+(media.matches?0:clamp(g.x/45,-5,5))+'deg) rotateZ('+(media.matches?0:clamp(g.x/55,-4,4))+'deg)';}
  function drawDrag(){dragFrame=0;if(drag&&drag.moved)drag.card.style.transform=dragPose(drag);}
  function rollback(g){
    const from=getComputedStyle(g.card).transform;stage.classList.remove('is-dragging');g.card.classList.remove('is-grabbed');
    if(media.matches){place();return;}
    const token=++motion;stage.classList.add('is-dealing');const a=g.card.animate([{transform:from},{transform:position(0)}],{duration:300,easing:'cubic-bezier(.2,.8,.25,1)'});animations=[a];
    a.finished.then(()=>{if(token===motion){animations=[];place();stage.classList.remove('is-dealing');if(window.__landingEdge)window.__landingEdge.refresh();}},()=>{});
  }
  function cancelDrag(){if(!drag)return;const g=drag;drawDrag();drag=null;cancelledPointer=g.id;cancelAnimationFrame(dragFrame);dragFrame=0;release(g);suppressUntil=performance.now()+200;if(g.moved)rollback(g);else place();}
  function pointerDown(event,card){
    if(!event.isPrimary||event.button!==0||!card.classList.contains('is-front')||stage.classList.contains('is-dealing')||drag)return;
    if(event.target.closest('a,input,textarea,select,button'))return;
    suppressUntil=0;card.focus({preventScroll:true});const now=performance.now();
    drag={card,id:event.pointerId,startX:event.clientX,startY:event.clientY,x:0,y:0,lastX:event.clientX,lastY:event.clientY,last:now,vx:0,vy:0,moved:false,w:card.offsetWidth,h:card.offsetHeight};
    try{card.setPointerCapture(event.pointerId);}catch(_){}
  }
  function pointerMove(event){
    const g=drag;if(!g||event.pointerId!==g.id)return;const now=performance.now(),dt=Math.max(8,now-g.last);
    g.x=event.clientX-g.startX;g.y=event.clientY-g.startY;
    if(event.clientX!==g.lastX||event.clientY!==g.lastY){g.vx=(event.clientX-g.lastX)/dt;g.vy=(event.clientY-g.lastY)/dt;g.last=now;g.lastX=event.clientX;g.lastY=event.clientY;}
    if(Math.hypot(g.x,g.y)>6){g.moved=true;stage.classList.add('is-dragging');g.card.classList.add('is-grabbed');if(event.cancelable)event.preventDefault();if(!dragFrame)dragFrame=requestAnimationFrame(drawDrag);}
  }
  function pointerUp(event){
    const g=drag;if(!g||event.pointerId!==g.id)return;drawDrag();drag=null;cancelAnimationFrame(dragFrame);dragFrame=0;release(g);stage.classList.remove('is-dragging');g.card.classList.remove('is-grabbed');
    if(!g.moved)return; // A stationary tap retains the click fallback.
    suppressUntil=performance.now()+200;
    const distance=Math.hypot(g.x,g.y),speed=Math.hypot(g.vx,g.vy)*Math.exp(-(performance.now()-g.last)/100),threshold=clamp(g.w*.16,54,96);
    if(distance<threshold&&!(distance>32&&speed>.65)){rollback(g);return;}
    const extra=clamp(80+speed*45,80,155),nx=g.x/distance,ny=g.y/distance;
    advance(1,false,{x:clamp(g.x+nx*extra,-g.w*.9,g.w*.9),y:clamp(g.y+ny*extra,-g.h*.8,g.h*.8),rx:clamp(-g.y/30,-8,8),ry:clamp(g.x/40,-7,7),rz:clamp(g.x/50,-5,5),duration:clamp(270-speed*35,170,270)});
  }
  cards.forEach(card=>{
    card.addEventListener('pointerdown',e=>pointerDown(e,card));card.addEventListener('pointermove',pointerMove);card.addEventListener('pointerup',pointerUp);
    card.addEventListener('pointercancel',cancelDrag);card.addEventListener('lostpointercapture',e=>{if(drag&&drag.id===e.pointerId)cancelDrag();});
    card.addEventListener('click',()=>{if(card.classList.contains('is-front')&&performance.now()>=suppressUntil)advance(1,false);});
    card.addEventListener('keydown',e=>{if(!card.classList.contains('is-front'))return;if(e.key==='Escape'&&drag){e.preventDefault();cancelDrag();return;}if(['Enter',' ','ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();advance(e.key==='ArrowLeft'?-1:1,true);}});
  });
  // Never turn a completed drag into an accidental CTA click at its release point.
  document.addEventListener('click',e=>{if(e.detail>0&&performance.now()<suppressUntil){e.preventDefault();e.stopImmediatePropagation();}},true);
  document.addEventListener('pointerdown',()=>{if(!drag){suppressUntil=0;cancelledPointer=-1;}},true);
  document.addEventListener('pointerup',e=>{if(e.pointerId===cancelledPointer){suppressUntil=performance.now()+200;cancelledPointer=-1;}},true);
  addEventListener('scroll',()=>{if(drag)cancelDrag();},{passive:true});addEventListener('resize',stopMotion,{passive:true});
  if('IntersectionObserver' in window)new IntersectionObserver(es=>{if(!es[0].isIntersecting)stopMotion();}).observe(panel);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stopMotion();});addEventListener('pagehide',stopMotion);
  media.addEventListener('change',()=>{stopMotion();paint();});render(false);
}());
