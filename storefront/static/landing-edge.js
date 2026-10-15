/* Nearest-cursor-edge highlight for the landing page's surfaces (body.v2 only).
 * Each registered surface gets one aria-hidden overlay SPAN; the side nearest the
 * pointer lights up as a 2px line. The span is pointer-events:none and absolutely
 * positioned, so layout, hit-testing, clicks, focus, native form fields and the
 * approved product-card tilt/entrance are untouched — this only ADDS an edge.
 * Demand-driven: one coalesced RAF per burst of pointer/scroll/resize events and
 * no loop at rest. No timers, no glow, no particles, no remote requests. */
(function () {
  'use strict';
  const body = document.body;
  if (!body || !body.classList.contains('v2')) return;
  if (body.dataset.edge === 'off') return;            /* contract: opt out per page */
  const fine = matchMedia('(hover:hover) and (pointer:fine)');
  /* Hysteresis px: a rival edge must be this much nearer before it takes over,
     so equal distances and the card's own -3px hover lift cannot make it chatter. */
  const HYS = 4;

  /* The template's surfaces; nested ones (a button inside a pricing card) are both
     registered and both lit, because the hit walk visits every registered ancestor. */
  const SELECTORS = [
    '#top .metric', '#demo .cards>div', '#coverage .cards>div', '#how .cards>div',
    '#pricing .cards>div', '#setup .cards>div', '.swap-card', '.product-suite-card',
    '#znaniya .kb-teaser>a', '#faq details>summary', '.planpick>summary', '.pp-item',
    '.hv-btn, .hv-btn-glow, .hv-btn-ghost', '.hv-row, .hv-cell, .kb-list>a', '.hero-stack-card'
  ].join(',');

  const surfaces = new Set();   /* registered targets */
  const overlays = new Map();   /* target -> its overlay span */
  const stretched = new Set(); /* Keep the native full-card ::after link hit area. */
  const lit = new Map();        /* target -> the side currently lit */
  let pointer = null, raf = 0;
  function overlay(el) {
    let o = overlays.get(el);
    if (!o) {
      o = document.createElement('span'); o.className = 'directional-edge'; o.setAttribute('aria-hidden', 'true');
      /* Inline, so even a missing stylesheet cannot move or block the surface. */
      o.style.cssText = 'position:absolute;inset:0;pointer-events:none';
      overlays.set(el, o);
    }
    /* textContent rewrites (button labels, the plan summary) delete children, so a
       detached overlay is simply re-appended on the next interaction. */
    if (o.parentNode !== el) el.appendChild(o);
    return o;
  }
  function collect() {
    if (!fine.matches) return;
    const found = [];
    document.querySelectorAll(SELECTORS).forEach((el) => found.push(el));
    /* :has() would be exact but is newer than the page: the parent of the one <pre>/<video> IS the surface. */
    document.querySelectorAll('#legal pre, #video video').forEach((m) => {
      const p = m.parentElement;
      if (p && p.tagName === 'DIV') found.push(p);
    });
    const fresh = found.filter((el) => !surfaces.has(el));
    /* All reads before any write: a static parent becomes the containing block; absolute/relative is left alone. */
    const anchors = fresh.filter((el) => {
      if (getComputedStyle(el).position !== 'static') return false;
      if (el.tagName === 'A') {
        const pseudo = getComputedStyle(el, '::after');
        if (pseudo.position === 'absolute' && pseudo.content !== 'none' && ['top','right','bottom','left'].every(k => pseudo[k] === '0px')) { stretched.add(el); return false; }
      }
      return true;
    });
    fresh.forEach((el) => surfaces.add(el));
    anchors.forEach((el) => { el.style.position = 'relative'; });
    found.forEach(overlay);
  }

  function schedule() { if (!raf && !document.hidden && fine.matches) raf = requestAnimationFrame(paint); }
  function clear(el) { const o = overlays.get(el); if (o) o.classList.remove('is-on'); lit.delete(el); }
  function clearAll() { Array.from(lit.keys()).forEach(clear); }
  /* A card being dragged or dealt owns its own geometry: skip it entirely, so the
     drag costs no extra rect read and no extra paint. */
  function frozen(el) {
    const stack = el.closest('.hero-real-stack');
    return !!stack && (stack.classList.contains('is-dragging') || stack.classList.contains('is-dealing'));
  }
  function paint() {
    raf = 0;
    if (!pointer || document.hidden || !fine.matches) { clearAll(); return; }
    const hit = new Set();
    for (let n = document.elementFromPoint(pointer.x, pointer.y); n && n !== body; n = n.parentElement) {
      if (surfaces.has(n) && !frozen(n)) hit.add(n);
    }
    const boxes = new Map();
    const box = el => { if (!boxes.has(el)) boxes.set(el,el.getBoundingClientRect()); return boxes.get(el); };
    const readings = Array.from(hit,el=>{
      const r=box(el);
      if(pointer.x<r.left||pointer.x>r.right||pointer.y<r.top||pointer.y>r.bottom)return {el,outside:true};
      let placement;
      if(stretched.has(el)){
        const parent=el.offsetParent;
        if(parent){const p=box(parent),sx=p.width/(parent.offsetWidth||p.width),sy=p.height/(parent.offsetHeight||p.height);
          placement={left:(r.left-p.left)/sx-parent.clientLeft,top:(r.top-p.top)/sy-parent.clientTop,width:r.width/sx,height:r.height/sy};}
      }
      return {el,r,placement};
    });
    lit.forEach((_,el)=>{if(!hit.has(el))clear(el);});
    readings.forEach(({el,r,placement,outside})=>{
      if(outside){clear(el);return;}
      const d={top:pointer.y-r.top,right:r.right-pointer.x,bottom:r.bottom-pointer.y,left:pointer.x-r.left};
      let best='top',gap=d.top;
      for(const side of ['right','bottom','left'])if(d[side]<gap){best=side;gap=d[side];}
      const prev=lit.get(el);if(prev&&prev!==best&&d[prev]-gap<HYS)best=prev;
      const o=overlay(el);
      if(placement){o.style.inset='auto';for(const [k,v]of Object.entries(placement))o.style[k]=v+'px';}
      if(o.dataset.edge!==best)o.dataset.edge=best;o.classList.add('is-on');lit.set(el,best);
    });
  }

  function move(e) {
    if (e.pointerType === 'touch') { pointer = null; clearAll(); return; }   /* touch clears */
    pointer = { x: e.clientX, y: e.clientY };
    schedule();
  }
  function leave(e) { if (!e.relatedTarget) { pointer = null; clearAll(); } }
  function configure() {
    if (!fine.matches) { cancelAnimationFrame(raf); raf = 0; pointer = null; clearAll(); body.classList.remove('edge-ready'); return; }
    collect(); body.classList.add('edge-ready'); schedule();
  }

  document.addEventListener('pointermove', move, { passive: true });
  document.addEventListener('pointerout', leave, { passive: true });
  document.addEventListener('pointerdown', () => { if (fine.matches) collect(); }, { passive: true, capture: true });
  addEventListener('scroll', () => { if (pointer) schedule(); }, { passive: true });   /* one RAF, not one per event */
  addEventListener('resize', () => { if (pointer) schedule(); }, { passive: true });
  addEventListener('blur', () => { pointer = null; clearAll(); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; pointer = null; clearAll(); } else schedule();
  });
  addEventListener('pagehide', () => { cancelAnimationFrame(raf); raf = 0; clearAll(); });
  fine.addEventListener('change', configure);
  addEventListener('load', collect);   /* hero cards are built by a sibling script */
  /* Integration hook: re-register after a surface is rebuilt, e.g. a hero restack. */
  window.__landingEdge = { refresh: () => { collect(); schedule(); }, clear: clearAll };
  configure();
}());
