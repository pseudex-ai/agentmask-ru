/* The existing order examples become six actual sheets. Fixture data and DOM
 * helpers come from landing.js, loaded first. All values are illustrative.
 * Only the public demo screen body is cloned for the turn — never forms, account
 * content or actual customer traffic. No command/model/network call is made. */
(function () {
  'use strict';
  const stage = document.getElementById('hero-dialog');
  const panel = document.getElementById('hero-panel');
  const rail = document.getElementById('hero-rail');
  const phaseLabel = document.getElementById('hero-phase');
  const pause = document.querySelector('[data-hero-pause]');
  if (!stage || !panel || typeof HERO_CASES === 'undefined') return;
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const wide = matchMedia('(min-width: 900px)');
  const dwell = {1:2600,2:1900,3:2300,4:2500,5:2700,6:3400};
  const steps = ['КЛИЕНТ','НАХОДИМ','ПОДМЕНЯЕМ','МОДЕЛЬ','ИНСТРУМЕНТ','ГОТОВО'];
  let index = 0, phase = media.matches ? 6 : 1, timer = 0;
  let hovered = false, focused = false, explicitPause = false, inView = true, manualUntil = 0;
  let animations = [], ghost;
  stage.classList.add('hero-deck-stage');

  function prose(text, cls) { return node('p', cls || 'hero-sheet-prose', text); }
  function values(example) { return example.text.filter(pair => pair.length > 1).map(pair => pair[1]).join('\n'); }
  function message(example, mode) {
    const text = node('div','hero-sheet-message');
    example.text.forEach(([real,fake]) => {
      if (!fake) { text.appendChild(document.createTextNode(real)); return; }
      const token = heroToken(real,fake);
      if (mode >= 2) token.classList.add('is-found');
      if (mode >= 3) token.classList.add('is-swapped');
      text.appendChild(token);
    });
    return text;
  }
  function build() {
    const example = HERO_CASES[index];
    const sheet = node('div','hero-deck-sheet');
    sheet.dataset.orderSheet = String(phase);
    const tag = node('div','hero-sheet-tag');
    tag.append(node('span','', ['В ВАШЕМ КОНТУРЕ','ОБНАРУЖЕНИЕ','ПРАВДОПОДОБНАЯ ПОДМЕНА','КОНТЕКСТ МОДЕЛИ','ВЫЗОВ ВАШЕЙ ФУНКЦИИ','ПОЛНЫЙ ЦИКЛ'][phase-1]), node('span','', String(phase).padStart(2,'0')));
    sheet.appendChild(tag);
    const titles = ['Клиент пишет как привык.','Находим чувствительные значения.','Меняем личность. Не смысл.','Модель решает задачу.','Функция получает оригиналы.','Задача выполнена.'];
    sheet.appendChild(node('h3','hero-sheet-title',titles[phase-1]));
    if (phase <= 3) {
      sheet.append(node('div','hero-sheet-source',example.source), message(example,phase));
      sheet.appendChild(prose([
        'Переписка остаётся в вашем контуре. До обращения к модели её проверяет Pseudex.',
        'Имена, адреса и контакты отмечены в контексте сообщения — не вырезаны вместе со смыслом.',
        'Род, падеж и формат сохраняются. Модель читает обычное сообщение, но не настоящие значения.'
      ][phase-1], 'hero-sheet-note'));
    } else if (phase === 4) {
      const context = node('div','hero-sheet-context');
      context.append(node('div','hero-sheet-source','ЧТО ВИДИТ МОДЕЛЬ'),node('pre','',values(example)));
      sheet.append(context, node('div','hero-sheet-source','ЧТО НУЖНО СДЕЛАТЬ'),prose(example.decision,'hero-sheet-decision'));
      sheet.appendChild(prose('Для решения задачи модели достаточно подмен. Доступ к оригиналам ей не требуется.','hero-sheet-note'));
    } else if (phase === 5) {
      const record = heroRecord(example.record);
      sheet.append(node('div','hero-sheet-source',example.system),record);
      sheet.appendChild(prose('Модель передала подмены. Перед разрешённым вызовом инструмента Pseudex вернул настоящие значения.','hero-sheet-note'));
    } else {
      const compare = node('div','hero-sheet-compare');
      const model = node('div','hero-sheet-side');
      model.append(node('div','hero-sheet-source','МОДЕЛЬ · ПОДМЕНЫ'),node('pre','',values(example)));
      const local = node('div','hero-sheet-side hero-sheet-side-local');
      local.append(node('div','hero-sheet-source','ИНСТРУМЕНТ · ОРИГИНАЛЫ'),heroRecord(example.record));
      compare.append(model,local); sheet.append(compare,prose(example.done,'hero-sheet-note'));
    }
    return sheet;
  }
  const segments = rail ? Array.from({length:6},(_,i) => {
    const button = node('button',''); button.type='button'; button.dataset.heroPhase=String(i+1);
    button.setAttribute('aria-label','Этап '+(i+1)+': '+steps[i]);
    button.appendChild(node('i','')); rail.appendChild(button);
    button.addEventListener('click',()=>manual(i+1));
    return button;
  }) : [];
  function paint() {
    if (phaseLabel) phaseLabel.textContent = phase+'/6 · '+steps[phase-1];
    panel.dataset.heroCurrentPhase=String(phase); panel.dataset.heroCase=String(index);
    segments.forEach((button,i)=>{
      button.setAttribute('aria-pressed',String(phase===i+1));
      button.firstElementChild.classList.toggle('is-on',phase>i+1);
      button.firstElementChild.classList.toggle('is-current',phase===i+1);
    });
    if (pause) {
      pause.disabled=media.matches;
      pause.setAttribute('aria-pressed',String(explicitPause||media.matches));
      pause.setAttribute('aria-label',media.matches?'Автоматический показ отключён настройкой уменьшенного движения':explicitPause?'Продолжить автоматический показ':'Приостановить автоматический показ');
      pause.textContent=explicitPause?'▷':'Ⅱ';
    }
  }
  function render(turn, direction) {
    animations.forEach(a=>a.cancel()); animations=[];
    if (ghost) { ghost.remove(); ghost=null; }
    const moving=turn&&!media.matches&&typeof stage.animate==='function';
    const base='translate(0px,0px)';
    if (moving) {
      // Navigation stays put: cloning/turning the whole window also moves the
      // tiny arrow hit targets. Only the screen below the controls may turn.
      ghost=stage.cloneNode(true);
      [ghost,...ghost.querySelectorAll('*')].forEach(el=>{
        Array.from(el.attributes).forEach(attr=>{
          if (attr.name==='id'||attr.name.startsWith('data-')||attr.name==='aria-live') el.removeAttribute(attr.name);
        });
      });
      ghost.classList.add('hero-window-ghost'); ghost.inert=true; ghost.setAttribute('aria-hidden','true');
      ghost.style.top=stage.offsetTop+'px'; ghost.style.left=stage.offsetLeft+'px';
      ghost.style.width=stage.offsetWidth+'px'; ghost.style.height=stage.offsetHeight+'px';
      panel.appendChild(ghost);
    }
    stage.replaceChildren(build()); paint();
    if (moving) {
      const old=ghost, sign=direction<0?-1:1;
      const leaveFrames=wide.matches?[{opacity:1,transform:base},{opacity:0,transform:base+' translate3d('+(-sign*38)+'px, -6px, 0) rotateY('+(-sign*8)+'deg) rotateZ('+(-sign*1.3)+'deg) scale(.97)'}]:[{opacity:1},{opacity:0}];
      const enterFrames=wide.matches?[{opacity:.25,transform:base+' translate3d('+(sign*27)+'px, 12px, 0) rotateY('+(sign*5)+'deg) scale(.98)'},{opacity:1,transform:base}]:[{opacity:0},{opacity:1}];
      const leave=old.animate(leaveFrames,{duration:360,easing:'cubic-bezier(.4,0,.2,1)',fill:'both'});
      const enter=stage.animate(enterFrames,{duration:460,easing:'cubic-bezier(.2,.7,.2,1)'});
      animations=[leave,enter];
      leave.finished.then(()=>{old.remove();if(ghost===old)ghost=null;},()=>old.remove());
    }
  }
  function schedule() {
    clearTimeout(timer); timer=0;
    if (media.matches||explicitPause||hovered||focused||!inView||document.hidden) return;
    timer=setTimeout(()=>advance(1,false),Math.max(dwell[phase],manualUntil-performance.now()));
  }
  function advance(delta,byHand) {
    let next=phase+delta;
    if(next<1){index=(index+HERO_CASES.length-1)%HERO_CASES.length;next=6;}
    if(next>6){index=(index+1)%HERO_CASES.length;next=1;}
    phase=next;
    if(byHand)manualUntil=performance.now()+6000;
    render(true,delta);schedule();
  }
  function manual(next) {
    manualUntil=performance.now()+6000;
    if(next===phase){schedule();return;}
    const direction=next<phase?-1:1;phase=next;
    render(true,direction);schedule();
  }
  document.querySelectorAll('[data-hero-step]').forEach(button=>button.addEventListener('click',()=>advance(Number(button.dataset.heroStep),true)));
  if(pause)pause.addEventListener('click',()=>{explicitPause=!explicitPause;if(!explicitPause)focused=false;paint();schedule();});
  panel.addEventListener('mouseenter',()=>{hovered=true;schedule();});
  panel.addEventListener('mouseleave',()=>{hovered=false;schedule();});
  panel.addEventListener('focusin',()=>{focused=true;schedule();});
  panel.addEventListener('focusout',event=>{if(!panel.contains(event.relatedTarget)){focused=false;schedule();}});
  panel.addEventListener('keydown',event=>{
    if(!event.target.closest('.hero-ctl,.hero-rail'))return;
    if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();advance(event.key==='ArrowRight'?1:-1,true);}
  });
  if('IntersectionObserver' in window){new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;schedule();}).observe(panel);}
  document.addEventListener('visibilitychange',schedule);
  addEventListener('pagehide',()=>{clearTimeout(timer);animations.forEach(a=>a.cancel());if(ghost){ghost.remove();ghost=null;}});
  addEventListener('pageshow',schedule);
  media.addEventListener('change',()=>{animations.forEach(a=>a.cancel());if(ghost){ghost.remove();ghost=null;}paint();schedule();});
  render(false,1);schedule();
}());
