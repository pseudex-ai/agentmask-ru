/* Local spatial composition. Pure local decoration, no network/data ingestion,
 * scroll hijack, timers or endless render loop. The RAF runs only while
 * pointer/scroll values settle and stops offscreen or in a hidden tab.
 *
 * TWO FEATURES, DECOUPLED. The hero depth scene (`[data-depth-scene]`, the
 * draggable customer-service deck) lives on /ai-service; the product cards live
 * on the landing. One engine drives whichever of them is present on the page, so
 * moving the deck off the landing must NOT switch off the approved card motion. */
(function () {
  'use strict';
  const scene = document.querySelector('[data-depth-scene]');
  const grid = document.querySelector('.product-suite-grid');
  const cards = Array.from(document.querySelectorAll('.product-suite-card'));
  if (!scene && !grid) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const wide = matchMedia('(min-width: 900px)');
  const fine = matchMedia('(hover: hover) and (pointer: fine)');
  const body = document.body;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const smooth = v => v * v * (3 - 2 * v);
  const hero = scene ? { el: scene, x: 0, y: 0, tx: 0, ty: 0, s: 0, visible: true } : null;
  const deck = cards.map((el, index) => ({ el, index, x: 0, y: 0, tx: 0, ty: 0, p: 0 }));
  let deckVisible = grid !== null, enabled = false, raf = 0;
  const dust = scene ? scene.querySelector('[data-depth-dust]') : null;
  // Deterministic sparse field. It never pretends to be live protected traffic.
  if (dust) {
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < 24; i++) {
      const dot = document.createElement('i');
      dot.style.left = ((i * 37 + 7) % 100) + '%';
      dot.style.top = ((i * 23 + 11) % 100) + '%';
      fragment.appendChild(dot);
    }
    dust.appendChild(fragment);
  }
  function schedule() {
    if (enabled && !document.hidden && !raf && ((hero && hero.visible) || deckVisible)) raf = requestAnimationFrame(paintDepth);
  }
  function reset() {
    cancelAnimationFrame(raf); raf = 0;
    const items = hero ? [hero, ...deck] : deck;
    items.forEach(item => {
      item.x = item.y = item.tx = item.ty = 0;
      ['--mx-x', '--mx-y', '--mx-scroll', '--mx-front-x', '--mx-front-y', '--mx-lift', '--mx-roll', '--mx-cx', '--mx-cy', '--mx-spread'].forEach(name => item.el.style.removeProperty(name));
    });
    if (hero) hero.s = 0;
    deck.forEach(item => { item.p = 0; });
  }
  function configure() {
    enabled = !reduce.matches && wide.matches;
    body.classList.toggle('motion-ready', enabled);
    if (!enabled) reset(); else schedule();
  }
  function approach(item, prop, target) {
    const next = item[prop] + (target - item[prop]) * .16;
    item[prop] = Math.abs(target - next) < .001 ? target : next;
    return item[prop] !== target;
  }
  function paintDepth() {
    raf = 0;
    if (!enabled || document.hidden) return;
    let moving = false;
    // Read the untransformed parent geometry BEFORE writing any CSS variables.
    // Reading transformed child rects creates a scroll/transform feedback loop.
    const hr = hero && hero.visible ? scene.getBoundingClientRect() : null;
    const gr = grid && deckVisible ? grid.getBoundingClientRect() : null;
    const vh = Math.max(1, innerHeight);
    if (hr) {
      moving = approach(hero, 'x', hero.tx) || moving;
      moving = approach(hero, 'y', hero.ty) || moving;
      moving = approach(hero, 's', clamp(-hr.top / vh, -.3, 1.3)) || moving;
      scene.style.setProperty('--mx-x', hero.x.toFixed(4));
      scene.style.setProperty('--mx-y', hero.y.toFixed(4));
      scene.style.setProperty('--mx-scroll', hero.s.toFixed(4));
      // The reading surface stays orthographic and on integer pixels. Depth is
      // carried by the decorative planes, not by rasterising tilted body text.
      scene.style.setProperty('--mx-front-x', String(Math.round(hero.x * 3)));
      scene.style.setProperty('--mx-front-y', String(Math.round(hero.y * 3 - hero.s * 10)));
    }
    if (gr) {
      deck.forEach(item => {
        const shown = smooth(clamp((vh * .92 - gr.top - item.index * 32) / (vh * .6), 0, 1));
        moving = approach(item, 'p', 1 - shown) || moving;
        moving = approach(item, 'x', item.tx) || moving;
        moving = approach(item, 'y', item.ty) || moving;
        item.el.style.setProperty('--mx-lift', (item.p * (54 + item.index * 13)).toFixed(3));
        item.el.style.setProperty('--mx-roll', (item.p * (item.index - 1) * 1.3).toFixed(3));
        item.el.style.setProperty('--mx-spread', (item.p * (item.index - 1) * 11).toFixed(3));
        item.el.style.setProperty('--mx-cx', item.x.toFixed(4));
        item.el.style.setProperty('--mx-cy', item.y.toFixed(4));
      });
    }
    if (moving) schedule();
  }
  function pointer(item) {
    item.el.addEventListener('pointermove', event => {
      if (!enabled || !fine.matches || event.pointerType === 'touch') return;
      const r = item.el.getBoundingClientRect();
      item.tx = clamp((event.clientX - r.left) / r.width * 2 - 1, -1, 1);
      item.ty = clamp((event.clientY - r.top) / r.height * 2 - 1, -1, 1);
      schedule();
    }, { passive: true });
    item.el.addEventListener('pointerleave', () => { item.tx = item.ty = 0; schedule(); }, { passive: true });
  }
  // Hero sheets are direct-manipulation objects: entering must not move them.
  // Keep the approved product-card pointer response independent.
  deck.forEach(pointer);
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (scene && entry.target === scene) hero.visible = entry.isIntersecting;
        else if (grid && entry.target === grid) deckVisible = entry.isIntersecting;
      });
      schedule();
    }, { rootMargin: '120px 0px' });
    if (scene) observer.observe(scene);
    if (grid) observer.observe(grid);
  }
  addEventListener('scroll', schedule, { passive: true });
  addEventListener('resize', schedule, { passive: true });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { cancelAnimationFrame(raf); raf = 0; } else schedule(); });
  addEventListener('pagehide', () => { cancelAnimationFrame(raf); raf = 0; });
  addEventListener('pageshow', schedule);
  reduce.addEventListener('change', configure);
  wide.addEventListener('change', configure);
  configure();
}());
