/* A snapshot reader with a typographic transition, not a client-side meter.
 * Every accepted total comes from the same-origin API. Timers only FETCH; they
 * never add values. Demo controls alter the synthetic server query, not totals.
 * No customer count, telemetry, storage, provider or licensing-admin requests. */
(function () {
  'use strict';
  const root = document.querySelector('[data-protection-counter]');
  if (!root || root.dataset.pcReady) return;
  root.dataset.pcReady = '1';
  const figures = root.querySelector('[data-pc-figures]');
  const output = root.querySelector('[data-pc-number]');
  const delta = root.querySelector('[data-pc-delta]');
  const changeLabel = root.querySelector('[data-pc-change-label]');
  const change = root.querySelector('[data-pc-change]');
  const stamp = root.querySelector('[data-pc-status]');
  const sweep = root.querySelector('[data-pc-sweep]');
  const toggle = root.querySelector('[data-pc-toggle]');
  const refresh = root.querySelector('[data-pc-refresh]');
  const reset = root.querySelector('[data-pc-reset]');
  const announcement = root.querySelector('[data-pc-announcement]');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const format = new Intl.NumberFormat('ru-RU');
  const endpoint = new URL(root.dataset.endpoint, location.href);
  if (endpoint.origin !== location.origin) return;
  const demo = root.dataset.mode === 'demo';
  const initial = root.dataset.initial;
  let value = initial !== '' && Number.isSafeInteger(Number(initial)) ? Number(initial) : null;
  let visible = !('IntersectionObserver' in window), auto = !reduce.matches;
  let timer = 0, controller = null, busy = false, animations = [], paintVersion = 0;
  let lastSnapshot = null, pollMs = 5000, advance = 0, entered = visible;
  const readable = number => format.format(number).replace(/\u00a0/g, ' ');
  function span(text, className) {
    const node = document.createElement('span');
    if (className) node.className = className;
    node.textContent = text; return node;
  }
  function layout(total, from = total, moving = false) {
    if (total === null) { figures.textContent = '—'; return []; }
    const columns = Math.max(7, String(total).length, from === null ? 0 : String(from).length);
    root.style.setProperty('--pc-scale', String(Math.min(1, 7 / columns)));
    const oldText = from === null ? ''.padStart(columns, ' ') : String(from).padStart(columns, ' ');
    const nextText = String(total).padStart(columns, ' ');
    const fragment = document.createDocumentFragment(), reels = [];
    for (let i = 0; i < columns; i++) {
      if (i && (columns - i) % 3 === 0) fragment.append(span('', 'pc-gap'));
      const cell = span('', 'pc-digit' + (i >= columns - 3 ? ' pc-digit--tail' : ''));
      const reel = span('', 'pc-reel');
      const changed = moving && oldText[i] !== nextText[i];
      reel.append(span(changed ? oldText[i] : nextText[i]));
      if (changed) { reel.append(span(nextText[i])); reels.push(reel); }
      cell.append(reel); fragment.append(cell);
    }
    figures.replaceChildren(fragment);
    return reels;
  }
  function finishMotion() {
    animations.forEach(animation => { try { animation.finish(); } catch (_) { animation.cancel(); } });
  }
  async function showTotal(total, animate) {
    const ticket = ++paintVersion, previous = value;
    animations.forEach(animation => animation.cancel()); animations = [];
    const moving = animate && previous !== null && previous !== total && !reduce.matches && typeof output.animate === 'function';
    const reels = layout(total, previous, moving);
    if (moving) {
      root.dataset.state = 'animating';
      // Carries move together. Staggering 9 984 -> 10 016 could show a bogus
      // intermediate decrease/overshoot; only the final full snapshot is read.
      reels.forEach(reel => animations.push(reel.animate(
        [{transform: 'translateY(0)'}, {transform: 'translateY(-50%)'}],
        {duration: 780, easing: 'cubic-bezier(.22,.8,.22,1)', fill: 'forwards'})));
      animations.push(sweep.animate(
        [{transform: 'scaleX(0)', opacity: 1}, {transform: 'scaleX(1)', opacity: 1, offset: .7}, {transform: 'scaleX(1)', opacity: 0}],
        {duration: 1000, easing: 'cubic-bezier(.22,.8,.22,1)'}));
      animations.push(delta.animate(
        [{transform: 'translateY(10px)', opacity: 0}, {transform: 'translateY(0)', opacity: 1}],
        {duration: 500, easing: 'ease-out'}));
      await Promise.all(animations.map(animation => animation.finished.catch(() => {})));
    }
    if (ticket !== paintVersion) return;
    animations.forEach(animation => animation.cancel()); animations = [];
    value = total; layout(total);
    root.dataset.value = String(total); root.dataset.state = 'ready';
    output.setAttribute('aria-label', readable(total) + ' защищённых значений' + (demo ? '. Демонстрация.' : '. По отчётам установок.'));
  }
  function controls() {
    // Final presentation has no service controls; keep them usable if a page
    // still renders them for the owner's testing.
    if (toggle) {
      toggle.disabled = false;
      toggle.replaceChildren(document.createTextNode(auto ? 'Пауза ' : 'Продолжить '), span(auto ? 'Ⅱ' : '▶'));
      toggle.setAttribute('aria-label', auto ? 'Приостановить обновления счётчика' : 'Продолжить обновления счётчика');
    }
    if (refresh) refresh.disabled = busy;
    if (reset) reset.disabled = busy;
    root.dataset.auto = String(auto);
  }
  function clearTimer() { clearTimeout(timer); timer = 0; }
  function schedule() {
    clearTimer();
    if (auto && visible && !document.hidden && !busy) timer = setTimeout(() => sync(false), pollMs);
  }
  function validate(data) {
    if (!data || !Number.isSafeInteger(data.total) || data.total < 0 ||
        data.mode !== (demo ? 'demo' : 'reported') || typeof data.revision !== 'string' ||
        !data.revision.length || typeof data.updated_at !== 'string' || !Number.isFinite(Date.parse(data.updated_at))) {
      throw new Error('invalid_snapshot');
    }
  }
  async function sync(manual, restart = false) {
    if (busy || !visible || document.hidden) return;
    clearTimer(); busy = true; controller = new AbortController(); controls();
    const requestController = controller;
    let timedOut = false;
    const requestTimer = setTimeout(() => { timedOut = true; requestController.abort(); }, 8000);
    root.classList.remove('is-error'); root.dataset.state = 'loading';
    try {
      const url = new URL(endpoint);
      if (demo) {
        if (restart) url.searchParams.delete('started');
        url.searchParams.set('advance', String(restart ? 0 : advance));
      }
      const response = await fetch(url, {signal: controller.signal, credentials: 'omit', cache: 'no-store', headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('snapshot_unavailable');
      const snapshot = await response.json(); clearTimeout(requestTimer); validate(snapshot);
      if (!restart && lastSnapshot && Date.parse(snapshot.updated_at) < Date.parse(lastSnapshot.updated_at)) {
        if (stamp) stamp.textContent = 'Ждём свежий снимок';
        root.dataset.state = value === null ? 'waiting' : 'ready'; return;
      }
      if (demo && Number.isSafeInteger(snapshot.demo_started_at)) {
        endpoint.searchParams.set('started', String(snapshot.demo_started_at));
        if (restart) advance = 0;
      }
      pollMs = Math.max(3000, Math.min(60000, Number(snapshot.poll_after_ms) || 5000));
      const previous = value, changed = previous !== snapshot.total;
      if (changed) {
        const difference = previous === null ? null : snapshot.total - previous;
        delta.textContent = difference === null || restart ? '—' : (difference >= 0 ? '+' : '−') + readable(Math.abs(difference));
        if (change) change.hidden = difference === null || restart;
        changeLabel.textContent = difference !== null && difference < 0 && !restart ? 'уточнение итога' : 'последний прирост';
      }
      lastSnapshot = snapshot;
      root.dataset.revision = snapshot.revision;
      const stale = !demo && Date.now() - Date.parse(snapshot.updated_at) > 300000;
      root.dataset.stale = String(stale);
      if (stamp) stamp.textContent = 'Снимок · ' + new Date(snapshot.updated_at).toLocaleTimeString('ru-RU');
      await showTotal(snapshot.total, changed);
      if (manual) announcement.textContent = (restart ? 'Демонстрация начата заново. ' : 'Получен снимок API. ') + readable(snapshot.total) + ' защищённых значений' + (demo ? ', синтетические данные.' : '.');
    } catch (error) {
      if (error.name !== 'AbortError' || timedOut) {
        root.classList.add('is-error'); root.dataset.state = 'error';
        if (stamp) stamp.textContent = 'Нет обновления · повторим';
        pollMs = 15000;
        if (manual) announcement.textContent = 'Снимок недоступен. Последнее значение сохранено.';
      } else root.dataset.state = value === null ? 'waiting' : 'ready';
    } finally {
      clearTimeout(requestTimer);
      controller = null; busy = false; controls(); schedule();
    }
  }
  function suspend() {
    clearTimer();
    if (controller) controller.abort();
    finishMotion();
  }
  if (toggle) toggle.addEventListener('click', () => {
    auto = !auto; controls();
    if (auto) sync(true); else suspend();
    announcement.textContent = auto ? 'Обновления продолжены.' : 'Обновления приостановлены.';
  });
  if (refresh) refresh.addEventListener('click', () => { if (busy) return; if (demo) advance++; sync(true); });
  if (reset) reset.addEventListener('click', () => sync(true, true));
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      if (visible) { if (auto || !entered) { entered = true; sync(false); } }
      else suspend();
    }, {threshold: .12}).observe(root);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) suspend(); else if (visible && auto) sync(false);
  });
  addEventListener('pagehide', suspend);
  addEventListener('pageshow', () => { if (visible && auto) sync(false); });
  reduce.addEventListener('change', () => {
    if (reduce.matches) { auto = false; suspend(); controls(); }
  });
  layout(value); controls(); root.dataset.value = value === null ? '' : String(value);
  if (visible) sync(false);
}());
